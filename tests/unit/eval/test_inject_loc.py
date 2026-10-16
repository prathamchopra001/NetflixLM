"""loc.term / loc.shot_change / loc.drift / loc.offset injectors (deliverable 2.9A)."""

import re
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from eval.injectors import get
from eval.injectors.common import Srt
from eval.injectors.loc_drift import confusions
from eval.injectors.loc_term import variants
from eval.metrics import load_labels, match
from nip.agents.base import run_check
from nip.agents.localization.readability import Readability
from nip.contracts import Flag
from nip.contracts.flag import ProducedBy
from nip.ingest import GlossaryEntry, parse_glossary, parse_srt
from nip.ingest.media import MediaInfo
from nip.ingest.script import Element, Scene, Script
from nip.timecode import ms_to_frame
from nip.timeline.estimate import build_timeline

FPS = Fraction(24)


def tc(ms: int) -> str:
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def make_srt(n: int = 30, numbering: int = 1) -> str:
    """n cues, 2.4 s long, 10 s apart; every third mentions Scales, every fifth Sintel."""
    out = []
    for i in range(n):
        t = 10_000 * (i + 1)
        text = f"Estoy buscando a {'Scales' if i % 3 == 0 else 'alguien'}"
        if i % 5 == 0:
            text += ", dice Sintel."
        else:
            text += " ahora."
        out.append(f"{i + numbering}\n{tc(t)} --> {tc(t + 2400)}\n{text}\n\n")
    return "".join(out)


GLOSSARY = (
    "term,lang,approved_rendering,notes\n"
    "Scales,es,Scales,Never translate\n"
    "Sintel,es,Sintel,variants: Cintel | Zintela\n"
    "Scales,fr,Scales,\n"
)


@pytest.fixture
def title(tmp_path: Path) -> Path:
    d = tmp_path / "film"
    d.mkdir()
    (d / "es_film.srt").write_text(make_srt(), encoding="utf-8")
    (tmp_path / "glossary.csv").write_text(GLOSSARY, encoding="utf-8")
    return d


def inject(name: str, title: Path, seed: int, **kw: Any) -> tuple[Path, list]:
    dst = title.parent / f"out-{name}-{seed}" / "es_film.srt"
    labels = get(name).inject(title / "es_film.srt", dst, seed, fps=FPS, **kw)
    return dst, labels


def test_srt_roundtrip_is_exact_and_matches_the_parser() -> None:
    text = make_srt(5, numbering=0)  # the file's own numbers start at 0
    srt = Srt(text)
    assert srt.render() == text
    track = parse_srt(text).data
    assert track and [c.idx for c in track.cues] == [1, 2, 3, 4, 5]
    assert len(srt.cues) == 5


def test_srt_refuses_what_the_parser_refuses(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Srt("1\nnot a timing line\nHello\n")


def test_variant_from_notes_or_misspelling() -> None:
    listed = variants(GlossaryEntry("Sintel", "es", "Sintel", "variants: Cintel | Zintela"))
    assert listed == [("Cintel", "variant"), ("Zintela", "variant")]
    ((miss, kind),) = variants(GlossaryEntry("Scales", "es", "Scales", ""))
    assert kind == "misspelling" and miss != "Scales" and sorted(miss) == sorted("Scales")
    assert variants(GlossaryEntry("x", "es", "aaa", "")) == []  # nothing to swap


def test_term_replaces_the_approved_rendering_and_labels_the_cue(title: Path) -> None:
    dst, labels = inject("loc.term.v1", title, 3, glossary=title.parent / "glossary.csv", k=5)
    assert len(labels) == 5
    old = parse_srt((title / "es_film.srt").read_bytes()).data
    new = parse_srt(dst.read_bytes()).data
    assert old and new and len(old.cues) == len(new.cues)
    changed = {o.idx for o, n in zip(old.cues, new.cues, strict=True) if o.text != n.text}
    assert changed == {int(lb.target.refs[0].rsplit("/", 1)[1]) for lb in labels}
    for lb in labels:
        i = int(lb.target.refs[0].rsplit("/", 1)[1])
        o, n = old.cues[i - 1], new.cues[i - 1]
        term = lb.description.split("'")[1]  # the approved rendering the label names
        word = re.compile(f"(?<![A-Za-z]){term}(?![A-Za-z])")
        assert word.search(o.text) and not word.search(n.text)
        assert lb.target.frames == (ms_to_frame(n.start_ms, FPS), ms_to_frame(n.end_ms, FPS))
        assert (lb.check, lb.lang, lb.episode, lb.title) == ("loc.term", "es", "S01E01", "film")


def test_term_uses_every_term_before_repeating(title: Path) -> None:
    _, labels = inject("loc.term.v1", title, 1, glossary=title.parent / "glossary.csv", k=2)
    assert {lb.description.split("'")[1] for lb in labels} == {"Scales", "Sintel"}


def test_term_only_uses_the_tracks_language(title: Path) -> None:
    (title / "fr_film.srt").write_text(make_srt(), encoding="utf-8")
    dst = title.parent / "o" / "fr_film.srt"
    labels = get("loc.term.v1").inject(
        title / "fr_film.srt", dst, 1, fps=FPS, glossary=title.parent / "glossary.csv", k=6
    )
    assert labels and all("'Scales'" in lb.description for lb in labels)  # fr has only Scales


def test_term_respects_avoid_and_is_deterministic(title: Path) -> None:
    g = title.parent / "glossary.csv"
    d1, l1 = inject("loc.term.v1", title, 9, glossary=g, k=4)
    d2, l2 = inject("loc.term.v1", title, 9, glossary=g, k=4)
    assert l1 == l2 and d1.read_bytes() == d2.read_bytes()
    taken = {int(lb.target.refs[0].rsplit("/", 1)[1]) for lb in l1}
    _, l3 = inject("loc.term.v1", title, 9, glossary=g, k=4, avoid=taken)
    assert not taken & {int(lb.target.refs[0].rsplit("/", 1)[1]) for lb in l3}


def test_term_reads_the_default_sidecar_glossary(tmp_path: Path) -> None:
    # sidecar glossaries ship with the repo and must parse
    from eval.injectors.common import SIDECAR

    files = list(SIDECAR.glob("*/glossary.csv"))
    assert files
    for f in files:
        assert parse_glossary(f.read_bytes()).ok


# -- shot change -------------------------------------------------------------


def cut_near(cue_ms: int, frames: int) -> int:
    return ms_to_frame(cue_ms, FPS) + frames


def test_shot_change_moves_one_edge_to_1_to_11_frames_from_a_cut(title: Path) -> None:
    src = parse_srt((title / "es_film.srt").read_bytes()).data
    assert src
    # a cut 20 frames after (or before) the edge of each cue
    cuts = sorted(
        {ms_to_frame(c.start_ms, FPS) + (20 if c.idx % 2 else -20) for c in src.cues}
        | {ms_to_frame(c.end_ms, FPS) + 20 for c in src.cues}
    )
    dst, labels = inject("loc.shot_change.v1", title, 4, cuts=cuts, k=4)
    assert len(labels) == 4
    new = parse_srt(dst.read_bytes()).data
    assert new
    for lb in labels:
        i = int(lb.target.refs[0].rsplit("/", 1)[1])
        c = new.cues[i - 1]
        a, b = ms_to_frame(c.start_ms, FPS), ms_to_frame(c.end_ms, FPS)
        assert lb.target.frames == (a, b)
        near = [abs(e - cut) for e in (a, b) for cut in cuts if 1 <= abs(e - cut) <= 11]
        assert len(near) >= 1  # one end is 1-11 frames from a cut
        assert lb.check == "loc.shot_change"
    # untouched cues are byte-identical
    touched = {int(lb.target.refs[0].rsplit("/", 1)[1]) for lb in labels}
    assert all(
        (o.start_ms, o.end_ms) == (n.start_ms, n.end_ms)
        for o, n in zip(src.cues, new.cues, strict=True)
        if o.idx not in touched
    )


def test_shot_change_leaves_readability_clean(title: Path) -> None:
    src = parse_srt((title / "es_film.srt").read_bytes()).data
    assert src
    cuts = sorted({ms_to_frame(c.start_ms, FPS) + 18 for c in src.cues})
    dst, labels = inject("loc.shot_change.v1", title, 2, cuts=cuts, k=5)
    assert labels
    track = parse_srt(dst.read_bytes()).data
    assert track
    media = MediaInfo("x.mkv", FPS, 100_000, 1920, 1080, "h264", "yuv420p", 0, False, 1)
    script = Script(None, [Scene("1", "INT. ROOM - DAY", [Element("action", "x")])])
    tl = build_timeline("S01E01", script, media, {"es": track})
    assert (
        run_check(Readability(["es"]), tl, "r", ProducedBy(model_variant=None, plan_id="p")) == []
    )


def test_shot_change_without_cuts_near_does_nothing(title: Path) -> None:
    dst, labels = inject("loc.shot_change.v1", title, 1, cuts=[5_000_000])
    assert labels == [] and dst.read_bytes() == (title / "es_film.srt").read_bytes()


# -- drift and offset --------------------------------------------------------


def test_drift_ratios_are_relative_to_the_probed_rate() -> None:
    assert [r for r, _ in confusions(Fraction(24000, 1001))] == [
        Fraction(25025, 24000),
        Fraction(1001, 1000),
    ]
    assert [r for r, _ in confusions(Fraction(24))] == [Fraction(25, 24), Fraction(1000, 1001)]
    assert [r for r, _ in confusions(Fraction(25))] == [Fraction(1)]


@pytest.mark.parametrize("seed", range(6))
def test_drift_rescales_every_cue_and_labels_the_whole_track(title: Path, seed: int) -> None:
    dst, (lb,) = inject("loc.drift.v1", title, seed)
    old = parse_srt((title / "es_film.srt").read_bytes()).data
    new = parse_srt(dst.read_bytes()).data
    assert old and new
    ratio = Fraction(
        *[int(x) for x in lb.description.split("rescaled by ")[1].split(" ")[0].split("/")]
    )
    assert ratio in (Fraction(25, 24), Fraction(1000, 1001))
    for o, n in zip(old.cues, new.cues, strict=True):
        assert n.start_ms == round(o.start_ms * ratio) and n.end_ms == round(o.end_ms * ratio)
    assert lb.target.refs == [f"S01E01/es/{i}" for i in range(1, 31)]
    assert lb.target.frames is None and lb.check == "loc.drift"


def test_offset_never_makes_a_time_negative(tmp_path: Path) -> None:
    d = tmp_path / "film"
    d.mkdir()
    (d / "es_film.srt").write_text("1\n00:00:00,500 --> 00:00:02,000\nHi\n", encoding="utf-8")
    for seed in range(30):
        dst = tmp_path / f"o{seed}.srt"
        get("loc.offset.v2").inject(d / "es_film.srt", dst, seed, fps=FPS)
        assert parse_srt(dst.read_bytes()).data  # a negative start would not parse


# -- the labels score ---------------------------------------------------------


def flag(check: str, ref: str, frames: tuple[int, int]) -> Flag:
    return Flag.model_validate(
        {
            "run_id": "r",
            "episode": "S01E01",
            "agent": "localization_auditor",
            "check": check,
            "category": "localization",
            "lang": "es",
            "severity": 3,
            "confidence": 0.9,
            "tier": "must_review",
            "title": "t",
            "explanation": "e",
            "evidence": [
                {
                    "kind": "subtitle_cue",
                    "ref": ref,
                    "role": "claim",
                    "frames": frames,
                    "lang": "es",
                }
            ],
            "produced_by": {"model_variant": None, "plan_id": "p"},
            "verification": {},
        }
    )


def test_hand_made_flags_match_the_planted_labels(title: Path, tmp_path: Path) -> None:
    from eval.injectors import write_labels

    src = parse_srt((title / "es_film.srt").read_bytes()).data
    assert src
    cuts = sorted({ms_to_frame(c.start_ms, FPS) + 18 for c in src.cues})
    _, term = inject("loc.term.v1", title, 5, glossary=title.parent / "glossary.csv", k=2)
    _, shot = inject("loc.shot_change.v1", title, 5, cuts=cuts, k=2)
    _, drift = inject("loc.drift.v1", title, 5)
    write_labels([*term, *shot, *drift], tmp_path / "l.jsonl")
    labels = load_labels(tmp_path / "l.jsonl")
    flags = [
        flag(lb.check, lb.target.refs[0], lb.target.frames or (0, 1))
        for lb in labels
        if lb.target.frames
    ]
    flags.append(flag("loc.drift", "S01E01/es/1", (240, 300)))  # claims the track's first cue
    pairs = match(flags, labels)
    assert len(pairs) == len(labels)  # every planted error found, one to one
    assert {labels[j].check for _, j in pairs} == {"loc.term", "loc.shot_change", "loc.drift"}
