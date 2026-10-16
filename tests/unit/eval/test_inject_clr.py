"""Clearance text injector (deliverable 2.9A): overlay, re-encode, labels, determinism."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from eval.injectors import get, write_labels
from eval.injectors.clr_text import NEG_AREAS, low_motion_runs
from eval.metrics import load_labels, match
from nip.contracts import Flag
from nip.ingest import parse_bible, parse_clearance_log
from nip.ingest.media import probe

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")

LOG = (
    "item,kind,status,scope,notes\n"
    "(290) 482-7716,phone,pending,,injected\n"
    "https://velthorn.io,url,denied,,injected\n"
    "hello@velthorn.io,email,cleared,,injected\n"
    "7KLM482,plate,pending,,injected\n"
    "Veltrix Cola,brand,denied,,injected\n"
    "Other,phone,pending,,not injected\n"
)
BIBLE = "show: clip\nfictional:\n  brands: [Kappa Cola]\n"


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """4 s x 5 of flat colour at 24 fps: 4 still stretches, cuts between them."""
    d = tmp_path_factory.mktemp("clip") / "clip"
    d.mkdir()
    (d / "bible.yaml").write_text(BIBLE)
    (d / "clearance_log.csv").write_text(LOG)
    graph = "[0][1][2][3]concat=n=4:v=1:a=0,format=yuv420p"
    cols = ["0x808080", "0x203060", "0x806020", "0x40a040"]
    ins = [a for c in cols for a in ("-f", "lavfi", "-i", f"color=c={c}:s=320x180:r=24:d=5")]
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            *ins,
            "-filter_complex",
            graph,
            "-c:v",
            "libx264",
            str(d / "clip.mkv"),
        ],
        check=True,
    )
    return d


def run(clip: Path, tag: str, seed: int = 1, **kw: int) -> tuple[Path, list]:
    dst = clip.parent / tag / "clip.mkv"
    labels = get("clr.text.v1").inject(
        clip / "clip.mkv", dst, seed, sidecar=clip, k_pos=3, k_neg=1, **kw
    )
    return dst, labels


def gray_frame(path: Path, n: int) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"select=eq(n\\,{n}),format=gray",
         "-frames:v", "1", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return np.frombuffer(raw, np.uint8).reshape(180, 320)


def test_sidecars_of_the_corpus_titles_parse() -> None:
    root = Path(__file__).parents[3] / "eval" / "corpus" / "sidecar"
    titles = sorted(root.iterdir())
    assert {t.name for t in titles} >= {"sintel", "tears-of-steel"}
    for t in titles:
        log = parse_clearance_log((t / "clearance_log.csv").read_bytes())
        assert log.ok and log.data
        assert {e.status for e in log.data} == {"cleared", "pending", "denied"}  # a mix
        assert {e.kind for e in log.data} == {"phone", "url", "email", "address", "plate", "brand"}
        assert parse_bible((t / "bible.yaml").read_bytes()).ok


def test_phone_positives_are_valid_numbers_outside_the_fiction_range() -> None:
    """The detector (Presidio, leniency VALID) only sees numbers libphonenumber accepts; positives
    must be such numbers outside 555-0100..0199, negatives such numbers inside it."""
    import phonenumbers

    def valid(text: str) -> bool:
        return phonenumbers.is_valid_number(phonenumbers.parse(text, "US"))

    def fictional(text: str) -> bool:
        digits = "".join(c for c in text if c.isdigit())
        return digits[3:8] == "55501"

    root = Path(__file__).parents[3] / "eval" / "corpus" / "sidecar"
    n = 0
    for t in root.iterdir():
        for e in parse_clearance_log((t / "clearance_log.csv").read_bytes()).data or []:
            if e.kind == "phone":
                n += 1
                assert valid(e.item) and not fictional(e.item), e.item
    assert n == 4
    for area in NEG_AREAS:  # every negative the injector can draw
        for line in (0, 99):
            neg = f"({area}) 555-01{line:02d}"
            assert valid(neg) and fictional(neg), neg


def test_still_stretches_are_found_and_never_cross_a_cut(clip: Path) -> None:
    runs = low_motion_runs(clip / "clip.mkv", probe(clip / "clip.mkv"))
    # cuts at frames 120, 240, 360; the run from frame 0 is skipped as a fade-in
    assert all(a > 0 and b - a >= 84 for a, b in runs)
    assert runs and all(not (a < c < b) for a, b in runs for c in (120, 240, 360))


def test_overlay_is_on_exactly_the_labelled_frames(clip: Path) -> None:
    dst, labels = run(clip, "a")
    items = json.loads(dst.with_name("clip.mkv.clr.json").read_text())["items"]
    assert probe(dst).duration_frames == probe(clip / "clip.mkv").duration_frames
    assert labels and all(lb.target.frames for lb in labels)
    for it in items:
        a, b = it["frames"]
        x, y, w, h = it["box"]
        box = (
            slice(int(y * 180) + 2, int((y + h) * 180) - 2),
            slice(int(x * 320) + 2, int((x + w) * 320) - 2),
        )
        for n, shown in ((a - 3, False), (a + 2, True), (b - 2, True), (b + 2, False)):
            diff = np.abs(
                gray_frame(dst, n)[box].astype(int)
                - gray_frame(clip / "clip.mkv", n)[box].astype(int)
            ).mean()
            assert (diff > 5) == shown, (it["text"], n, diff)


def test_labels_negatives_and_cleared_items(clip: Path, tmp_path: Path) -> None:
    dst, labels = run(clip, "b", seed=2)
    items = json.loads(dst.with_name("clip.mkv.clr.json").read_text())["items"]
    assert sum(it["negative"] for it in items) == 1 and len(items) == 3  # 3 still stretches
    neg = next(it for it in items if it["negative"])
    assert neg["kind"] in ("phone", "url", "email", "brand")
    if neg["kind"] == "phone":
        assert neg["text"].split("-")[0].endswith("555") and 100 <= int(neg["text"][-4:]) <= 199
    labelled = {tuple(lb.target.frames or ()) for lb in labels}
    for it in items:
        is_labelled = tuple(it["frames"]) in labelled
        assert is_labelled == (not it["negative"] and it["status"] != "cleared")
    assert {lb.check for lb in labels} <= {
        "clr.phone",
        "clr.url",
        "clr.address",
        "clr.plate",
        "clr.brand_text",
    }
    write_labels(labels, tmp_path / "l.jsonl")
    assert load_labels(tmp_path / "l.jsonl") == labels


def test_same_seed_is_byte_identical(clip: Path) -> None:
    a, la = run(clip, "c1", seed=3)
    b, lb = run(clip, "c2", seed=3)
    assert la == lb and a.read_bytes() == b.read_bytes()
    assert (
        a.with_name("clip.mkv.clr.json").read_bytes()
        == b.with_name("clip.mkv.clr.json").read_bytes()
    )
    _, other = run(clip, "c3", seed=4)
    assert [x.target.frames for x in other] != [x.target.frames for x in la]


def test_a_hand_made_flag_over_the_planted_frames_matches(clip: Path) -> None:
    _, labels = run(clip, "d")
    flags = []
    for lb in labels:
        a, b = lb.target.frames or (0, 0)
        flags.append(
            Flag.model_validate(
                {
                    "run_id": "r", "episode": lb.episode, "agent": "clearance_scanner",
                    "check": lb.check, "category": "clearance", "lang": None, "severity": 4,
                    "confidence": 0.9, "tier": "must_review", "title": "t", "explanation": "e",
                    "evidence": [
                        {
                            "kind": "keyframe",
                            "ref": f"{lb.episode}/kf/1.0",
                            "role": "claim",
                            "frames": (a + 5, b),
                        }
                    ],
                    "produced_by": {"model_variant": None, "plan_id": "p"}, "verification": {},
                }
            )
        )  # fmt: skip
    assert len(match(flags, labels)) == len(labels)
