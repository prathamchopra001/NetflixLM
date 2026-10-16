"""Clearance, on-screen text: OCR keyframes, then typed candidates per check id.

architecture.md > Agent 2 "On-screen text": OCR on keyframes -> Presidio recognizers (phone, email,
plate formats; URLs via urlextract; addresses and brand names via GLiNER) with allow-lists for
fiction-reserved values (D-026). This module emits no flags: `ocr_detections` produces the
`detection` rows and `TextScanner.candidates` the candidates that 2.7 matches against the
clearance registry, groups into occurrences and turns into flags.

Switches 2.7 uses for EXP-008 / EXP-017:
  keyframe policy  `timeline.keyframes.{long_shot_s, interval_s}` (B-027) picks the frames;
                   this module reads whatever `Keyframe`s it is given.
  OCR vs vlm       any object with `read(image) -> list[OcrLine]` is a reader (`RapidOcrBackend`,
                   `ServeOCR`, `StubOCR`; the vlm re-read of low-confidence crops is Phase 3).
  NER              any object with `predict(text, labels) -> list[Entity]`; None turns the
                   GLiNER-backed address and brand_text candidates off.
"""

import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Presidio's email check uses tldextract, which downloads a domain list unless this is empty.
os.environ.setdefault("TLDEXTRACT_PUBLIC_SUFFIX_LIST_URLS", "")

import phonenumbers  # noqa: E402
import yaml  # noqa: E402
from presidio_analyzer import (  # noqa: E402
    AnalyzerEngine,
    EntityRecognizer,
    Pattern,
    PatternRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import SlimSpacyNlpEngine  # noqa: E402
from presidio_analyzer.predefined_recognizers import (  # noqa: E402
    EmailRecognizer,
    PhoneRecognizer,
)
from sqlalchemy import Connection, insert  # noqa: E402
from urlextract import URLExtract  # noqa: E402

from nip.config import config_dir  # noqa: E402
from nip.store.schema import detection  # noqa: E402

PHONE, EMAIL, URL, PLATE, ADDRESS, BRAND = (
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "URL",
    "LICENSE_PLATE",
    "ADDRESS",
    "BRAND",
)
CHECK = {
    PHONE: "clr.phone",
    EMAIL: "clr.email",
    URL: "clr.url",
    PLATE: "clr.plate",
    ADDRESS: "clr.address",
    BRAND: "clr.brand_text",
}
_MIN_KEY = {
    PHONE: "phone",
    EMAIL: "email",
    URL: "url",
    PLATE: "plate",
    ADDRESS: "address",
    BRAND: "brand",
}


def _config() -> dict[str, Any]:
    cfg: dict[str, Any] = yaml.safe_load(
        (config_dir() / "clearance" / "recognizers.yaml").read_text("utf-8")
    )
    return cfg


# ---- OCR -> detection rows -------------------------------------------------------------------
@dataclass(frozen=True)
class Keyframe:
    shot: int  # index of the shot in the timeline (the `<shot>_<n>.jpg` file name, B-027)
    n: int
    path: Path


@dataclass(frozen=True)
class Detection:
    """One `detection` row of channel ocr; the store step adds episode_id and shot_id."""

    shot: int
    n: int
    text: str
    box: tuple[float, float, float, float]  # normalized [x, y, w, h]
    confidence: float
    model_variant: str
    channel: str = "ocr"
    label: str = "text"


def ocr_detections(frames: Iterable[Keyframe], reader: Any) -> list[Detection]:
    """Read every keyframe; one Detection per recognized text line."""
    return [
        Detection(f.shot, f.n, line.text, line.box, line.confidence, reader.variant)
        for f in frames
        for line in reader.read(f.path)
    ]


def insert_detections(
    conn: Connection, episode_id: int, shot_ids: Mapping[int, int], rows: Iterable[Detection]
) -> int:
    """Persist `rows` into `detection`; `shot_ids` maps a shot index to its `shot.id`."""
    values = [
        {
            "episode_id": episode_id,
            "shot_id": shot_ids.get(d.shot),
            "keyframe_n": d.n,
            "channel": d.channel,
            "label": d.label,
            "text": d.text,
            "box": list(d.box),
            "confidence": d.confidence,
            "model_variant": d.model_variant,
        }
        for d in rows
    ]
    if values:
        conn.execute(insert(detection), values)
    return len(values)


# ---- Recognizers -----------------------------------------------------------------------------
class FictionAwarePhone(PhoneRecognizer):
    """libphonenumber matches (it thinks (212) 555-0123 is valid), minus fiction-reserved ranges."""

    def __init__(self, language: str, regions: Sequence[str]) -> None:
        super().__init__(supported_language=language, supported_regions=tuple(regions))
        ranges = yaml.safe_load(
            (config_dir() / "clearance" / "fiction_phone_ranges.yaml").read_text("utf-8")
        )
        self._reserved = {
            r: [re.compile(p) for p in v["national"]] for v in ranges.values() for r in v["regions"]
        }

    def reserved(self, span: str) -> bool:
        for region in self.supported_regions:
            try:
                num = phonenumbers.parse(span, region)
            except phonenumbers.NumberParseException:
                continue
            if not phonenumbers.is_valid_number(num):
                continue
            code = phonenumbers.region_code_for_number(num)
            return any(p.fullmatch(str(num.national_number)) for p in self._reserved.get(code, ()))
        return False

    def analyze(self, text: str, entities: list[str], nlp_artifacts: Any = None) -> Any:
        return [
            r
            for r in super().analyze(text, entities, nlp_artifacts)
            if not self.reserved(text[r.start : r.end])
        ]


# "www . site . com", "site .com", "site. com": OCR spaces dots out (D-026 cleanup). Only a TLD
# list may follow, or a sentence break ("Hello. It works") would become a host name.
_GTLD = "com|net|org|edu|gov|info|biz|app|dev|tv|io"
_DOT_BEFORE = re.compile(rf"(?i)(?<=\w)\s+\.\s*(?=(?:{_GTLD}|(?-i:co|de|es|fr|uk|us|eu))\b)")
_DOT_AFTER = re.compile(rf"(?i)(?<=\w)\.\s+(?=(?:{_GTLD})\b)")
_WWW = re.compile(r"(?i)\b(www\d?)\s*\.\s*")
_SCHEME = re.compile(r"(?i)\b(https?)\s*:\s*/\s*/\s*")


def clean_ocr_urls(text: str) -> str:
    text = _SCHEME.sub(r"\1://", _WWW.sub(r"\1.", text))
    return _DOT_AFTER.sub(".", _DOT_BEFORE.sub(".", text))


class UrlExtractRecognizer(EntityRecognizer):
    """URLs via urlextract (full TLD list); the text is expected to be `clean_ocr_urls`-ed."""

    def __init__(self, language: str) -> None:
        super().__init__(supported_entities=[URL], supported_language=language, name="urlextract")
        self._extract = URLExtract()  # bundled TLD list; never calls update()

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts: Any = None) -> Any:
        return [
            RecognizerResult(URL, s, e, 0.8)
            for _, (s, e) in self._extract.find_urls(text, get_indices=True)
        ]


class NerRecognizer(EntityRecognizer):
    """GLiNER spans (address, organization, product) behind the `ner` client."""

    def __init__(self, language: str, ner: Any, labels: Mapping[str, str]) -> None:
        super().__init__(
            supported_entities=sorted(set(labels.values())),
            supported_language=language,
            name="gliner",
        )
        self._ner, self._labels = ner, dict(labels)

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts: Any = None) -> Any:
        return [
            RecognizerResult(self._labels[e.label], e.start, e.end, e.score)
            for e in self._ner.predict(text, list(self._labels))
        ]


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", s.casefold()).split())


@dataclass(frozen=True)
class Candidate:
    check: str  # clr.phone | clr.url | clr.email | clr.address | clr.plate | clr.brand_text
    text: str  # the matched span
    line: str  # the whole OCR line it came from
    shot: int
    n: int
    box: tuple[float, float, float, float]  # of the line
    confidence: float  # OCR confidence x recognizer score
    score: float
    ocr_confidence: float
    model_variant: str


class TextScanner:
    """Presidio analyzer for on-screen text. Build once (spaCy loads), call `candidates` per line.

    deny_brands: extra real brand names (clearance-log items); always brand_text candidates.
    fictional:   bible fictional brands / organizations; never brand_text candidates.
    """

    def __init__(
        self,
        ner: Any = None,
        *,
        deny_brands: Iterable[str] = (),
        fictional: Iterable[str] = (),
    ) -> None:
        cfg = _config()
        langs = cfg["languages"]
        self._min = cfg["min_score"]
        self._reserved = tuple(cfg["reserved_domains"])
        self._fictional = [n for n in map(_norm, fictional) if n]
        brands = sorted({*cfg["brand_deny_list"], *deny_brands})
        # Models: the MIT spaCy en / de pipelines; es / fr (spaCy's are GPL / LGPL-LR) get
        # tokenizer-only blank pipelines, names come from GLiNER (tech-stack.md, Build notes).
        nlp = SlimSpacyNlpEngine(
            models=[
                {"lang_code": "en", "model_name": "en_core_web_sm"},
                {"lang_code": "de", "model_name": "de_core_news_sm"},
            ],
            auto_download=False,
        )
        nlp._blank_languages = {x for x in langs if x not in ("en", "de")}  # no public hook
        registry = RecognizerRegistry(supported_languages=langs)
        for lang in langs:
            registry.add_recognizer(FictionAwarePhone(lang, cfg["phone_regions"]))
            registry.add_recognizer(EmailRecognizer(supported_language=lang))
            registry.add_recognizer(UrlExtractRecognizer(lang))
            registry.add_recognizer(
                PatternRecognizer(
                    PLATE,
                    supported_language=lang,
                    global_regex_flags=re.DOTALL | re.MULTILINE,  # no IGNORECASE: caps only
                    patterns=[
                        Pattern(p["name"], p["regex"], p["score"]) for p in cfg["plate_patterns"]
                    ],
                    context=["plate", "license", "matricula", "matrícula", "kennzeichen", "plaque"],
                )
            )
            registry.add_recognizer(
                PatternRecognizer(
                    BRAND,
                    supported_language=lang,
                    deny_list=brands,
                    deny_list_score=0.85,
                    name="brand_deny_list",
                )
            )
            if ner is not None:
                registry.add_recognizer(NerRecognizer(lang, ner, cfg["ner_labels"]))
        self._engine = AnalyzerEngine(registry=registry, nlp_engine=nlp, supported_languages=langs)

    def _reserved_host(self, host: str) -> bool:
        host = host.lower().rstrip(".")
        return any(host == d or host.endswith("." + d) for d in self._reserved)

    def _dropped(self, entity: str, text: str, start: int, end: int) -> bool:
        span = text[start:end]
        if entity == EMAIL:
            return self._reserved_host(span.rsplit("@", 1)[-1])
        if entity == URL:
            host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", span, flags=re.I)
            host = re.split(r"[/?#:]", host, maxsplit=1)[0]
            return self._reserved_host(host.rsplit("@", 1)[-1])
        if entity in (ADDRESS, BRAND):  # a piece of a reserved host ("shop" of shop.test) is not
            token = text[text.rfind(" ", 0, start) + 1 :].split(" ")[0]  # a brand; urlextract
            if self._reserved_host(token.strip(".,;:!?()\"'")):  # does not know .test
                return True
        if entity == ADDRESS:  # GLiNER tags bare phone-number lines as addresses: needs a word
            return re.search(r"[^\W\d_]{3}", span) is None
        if entity == BRAND:
            n = _norm(span)
            return any(f == n or f" {f} " in f" {n} " for f in self._fictional)
        return False

    def candidates(self, detections: Iterable[Detection], lang: str = "en") -> list[Candidate]:
        """Typed candidates of the OCR `detections` (`lang`: the language of the on-screen text)."""
        out = []
        for d in detections:
            text = clean_ocr_urls(d.text)
            raw = [
                r
                for r in self._engine.analyze(text, lang, entities=list(CHECK))
                if r.score >= self._min[_MIN_KEY[r.entity_type]]
            ]
            # A phone, URL, email or plate is its own finding: GLiNER's address / brand reading of
            # the same characters ("acme-shop.com" as an organization) and the domain inside an
            # email are not second ones. Fiction-safe values count too: example.com is no brand.
            fixed = [r for r in raw if r.entity_type in (PHONE, URL, EMAIL, PLATE)]
            emails = [r for r in fixed if r.entity_type == EMAIL]

            def inside(r: RecognizerResult, spans: list[RecognizerResult]) -> bool:
                return any(e.start < r.end and r.start < e.end for e in spans)

            for r in raw:
                if self._dropped(r.entity_type, text, r.start, r.end):
                    continue
                if r.entity_type in (ADDRESS, BRAND) and inside(r, fixed):
                    continue
                if r.entity_type == URL and inside(r, emails):
                    continue
                out.append(
                    Candidate(
                        CHECK[r.entity_type],
                        text[r.start : r.end],
                        d.text,
                        d.shot,
                        d.n,
                        d.box,
                        round(d.confidence * r.score, 4),
                        r.score,
                        d.confidence,
                        d.model_variant,
                    )
                )
        return out
