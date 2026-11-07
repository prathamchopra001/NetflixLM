"""EXP-004 inputs: as-broadcast scripts derived from the official English SRT (ruling R5).

    uv run python -m eval.exp.exp004_scripts derive   # eval/corpus/derived/<title>/script.fountain
                                                      # + eval/exp/exp004_labels/<title>.jsonl
    uv run python -m eval.exp.exp004_scripts real     # Sintel's real first-minute script labels

A derived line is one SRT cue (all its text lines joined) and its marked start is the cue's start
frame, so the labels are biased towards subtitle timing (R5). Scene breaks are synthetic: a silence
of at least GAP_S between two cues starts a new "SEQUENCE" scene. Every label is `labeller: agent`.
"""

import json
from fractions import Fraction
from pathlib import Path

import typer
from rapidfuzz import fuzz

from nip.ingest.media import probe
from nip.ingest.script import parse_fountain
from nip.ingest.subtitles import Cue, parse_srt
from nip.timecode import ms_to_frame

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "eval" / "corpus" / "derived"
LABELS = ROOT / "eval" / "exp" / "exp004_labels"
GAP_S = 10.0
TITLES = {
    "sintel": ("Sintel", "sintel/en_sintel_en.srt", "sintel/Sintel.2010.1080p.mkv"),
    "tears-of-steel": (
        "Tears of Steel",
        "tears-of-steel/en_TOS-en.srt",
        "tears-of-steel/tears_of_steel_720p.mov",
    ),
}
app = typer.Typer(no_args_is_help=True)


def _cues(rel: str) -> list[Cue]:
    p = parse_srt((ROOT / "data" / "corpus" / rel).read_bytes())
    if p.errors or p.data is None:
        raise ValueError(f"{rel}: {p.errors}")
    return p.data.cues


def _flat(c: Cue) -> str:
    return " ".join(c.text.split())


def fountain(title: str, cues: list[Cue]) -> tuple[str, list[tuple[int, int, Cue]]]:
    """Fountain text and, per cue, its (scene index, element index) in the parsed script."""
    out = [f"Title: {title} (as broadcast; derived from the official English SRT)\n"]
    keys: list[tuple[int, int, Cue]] = []
    scene, el, prev_end = -1, 0, -(10**9)
    for c in cues:
        if (c.start_ms - prev_end) / 1000 >= GAP_S or scene < 0:
            scene, el = scene + 1, 0
            out.append(f"INT. SEQUENCE {scene + 1} - {title.upper()}\n")
        out.append(f"UNKNOWN\n{_flat(c)}\n")
        keys.append((scene, el, c))
        el, prev_end = el + 1, c.end_ms
    return "\n".join(out), keys


@app.command()
def derive() -> None:
    for tid, (title, srt, video) in TITLES.items():
        fps = probe(ROOT / "data" / "corpus" / video).fps
        text, keys = fountain(title, _cues(srt))
        d = DERIVED / tid
        d.mkdir(parents=True, exist_ok=True)
        (d / "script.fountain").write_text(text, encoding="utf-8")
        script = parse_fountain(text)
        assert script.data and not script.errors, script.errors
        # The parsed script must hold exactly the cues, in order, one dialogue element each.
        for si, ei, c in keys:
            e = script.data.scenes[si].elements[ei]
            assert e.kind == "dialogue" and e.text.split() == _flat(c).split(), (tid, c)
        _write(tid, fps, [(si, ei, _flat(c), c.start_ms, "srt-cue-start") for si, ei, c in keys])
        print(f"{tid}: {len(keys)} lines, {len(script.data.scenes)} scenes, fps {fps}")


def _write(
    tid: str, fps: Fraction, rows: list[tuple[int, int, str, int, str]], suffix: str = ""
) -> None:
    LABELS.mkdir(parents=True, exist_ok=True)
    with (LABELS / f"{tid}{suffix}.jsonl").open("w", encoding="utf-8") as f:
        for si, ei, text, ms, basis in rows:
            f.write(json.dumps({
                "title": tid, "scene": si, "element": ei, "text": text, "start_ms": ms,
                "start_frame": ms_to_frame(ms, fps), "labeller": "agent", "basis": basis,
            }) + "\n")  # fmt: skip


@app.command()
def real(min_score: float = 60.0) -> None:
    """Labels for Sintel's real first-minute script: each dialogue line is paired with the official
    cue it best matches (rapidfuzz); the cue start is the marked start. Lines with no cue above
    `min_score` are absent from the film (the draft differs) and carry no label. Spot-check the
    printed pairs by eye: that is the agent's review."""
    from nip.ingest.pdf import parse_pdf

    sc = parse_pdf((ROOT / "data/corpus/sintel/1stminute_script_11-61.pdf").read_bytes()).data
    assert sc is not None
    cues = _cues(TITLES["sintel"][1])
    fps = probe(ROOT / "data" / "corpus" / TITLES["sintel"][2]).fps
    rows = []
    for si, s in enumerate(sc.scenes):
        for ei, e in enumerate(s.elements):
            if e.kind != "dialogue":
                continue
            best = max(cues, key=lambda c: fuzz.token_set_ratio(e.text.lower(), _flat(c).lower()))
            score = fuzz.token_set_ratio(e.text.lower(), _flat(best).lower())
            print(f"{score:5.1f} {si}.{ei} {e.text!r} <-> cue {best.idx} {_flat(best)!r}")
            if score >= min_score:
                rows.append((si, ei, e.text, best.start_ms, f"srt-cue-{best.idx}-start"))
    _write("sintel-real-script", fps, rows)
    print(f"{len(rows)} labelled")


if __name__ == "__main__":
    app()
