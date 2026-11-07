"""2.4 benchmark: 2.9A-injected Sintel / Tears of Steel copies through the store pipeline, scored.

Per title and seed: the injected copy (`nip eval inject --set mvp --seed N --only loc`, output under
data/inject/mvp) is ingested as a show of a throwaway Postgres database (`nip_loc_bench`, created
and dropped here; objects are NOT uploaded) with the sidecar bible and glossary and a picture.json
made from the EXP-002 cuts at the probed duration; `run_store` runs with the two 2.4 stages; the
flags are scored by `nip eval run` (MLflow, one run per title, seed and variant, tag exp).

    NIP_PROFILE=cpu NIP_DATABASE_URL=postgresql://nip:change_me@127.0.0.1:55432/nip \\
        uv run python -m eval.exp.loc_bench --seeds 1 2 3 [--exp 2.4r1] [--no-mlflow] \\
        [--checks loc.shot_change]
    uv run nip eval compare --exp 2.4r1 --md --tracking-uri sqlite:///data/mlflow/mlflow.db

Scoring scope:
- loc.term and loc.shot_change are scored on the languages whose track the injector edited (a
  stacked track: term + shot_change + readability); flags of the same check on the other tracks are
  left out (whole-track errors by construction: a drifted or shifted track has cues near cuts).
- loc.drift and loc.offset are scored on every track.
- Variant `regression-<title>`: the clean copy of each title is run too, and every flag a check
  raises on it becomes a "native" label (`clean-run.native.jsonl`). These natives are SELF-LABELLED:
  nobody triaged them, so precision with them is a regression check (the check adds nothing over the
  clean track), not precision. Variant `raw-<title>` scores without them: the honest precision.
- ToS `it` (the offset track) has no rule pack (not an MVP language), so the store run cannot take
  it: drift and offset run on it in-process.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, make_url, text

from eval.corpus.downloader import DATA_DIR
from eval.injectors.base import Label, Target
from eval.injectors.common import PICTURE_SUFFIXES, SIDECAR
from eval.metrics import load_labels
from nip import pipeline
from nip.agents.base import run_check
from nip.agents.localization import term
from nip.agents.localization.drift import Drift, Offset
from nip.contracts import (
    Autoscaling,
    HardwareInventory,
    Mode,
    Objective,
    Plan,
    StageGroup,
    refs,
)
from nip.contracts.flag import EvidenceKind, ProducedBy
from nip.contracts.timeline import Span, Timeline
from nip.ingest import parse_srt
from nip.ingest.media import probe
from nip.store.db import database_url
from nip.store.ingest import ingest_files
from nip.store.schema import metadata
from nip.timecode import ms_to_frame
from nip.timeline import cue_align

CHECKS = ("loc.term", "loc.shot_change", "loc.drift", "loc.offset")
WHOLE_TRACK = ("loc.drift", "loc.offset")
TITLES = ("sintel", "tears-of-steel")
MVP_LANGS = ("en", "es", "fr", "de")  # languages with a rule pack (D-011)
EPISODE = "S01E01"
DB = "nip_loc_bench"
INJECT = Path("data/inject/mvp")
CUTS = "data/exp002/runs/picture/{title}/picture.json"
TRACKING = "sqlite:///data/mlflow/mlflow.db"
OUT = Path("data/loc-bench")
SET = "loc-2.4"


class NullS3:
    def upload_file(self, *a: object) -> None: ...
    def put_object(self, **kw: object) -> None: ...


def stub_plan() -> tuple[Plan, HardwareInventory]:
    inv = HardwareInventory(
        fingerprint="f", nodes=[], autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0)
    )
    plan = Plan(
        inventory_fingerprint="f",
        catalog_sha256="c",
        objective=Objective.QUALITY,
        mode=Mode.RESIDENT,
        groups=[StageGroup(name="resident", slots=[])],
        decisions={},
    )
    return plan, inv


def scope_flags(
    flags: list[dict[str, Any]], injected: dict[str, set[str | None]]
) -> list[dict[str, Any]]:
    """The flags a check is scored on: drift/offset everywhere, term/shot_change on the languages
    in `injected[check]` (the languages whose labels the check has)."""
    return [
        f
        for f in flags
        if f["check"] in CHECKS
        and (f["check"] in WHOLE_TRACK or f["lang"] in injected.get(f["check"], set()))
    ]


def native_label(flag: dict[str, Any], title: str) -> Label:
    """A self-labelled native: the cue a clean-run flag claims."""
    claim = next(e for e in flag["evidence"] if e["role"] == "claim")
    frames = tuple(claim["frames"]) if claim.get("frames") else None
    return Label(
        label_id=f"{title}-{flag['lang']}-{flag['check']}-native-{claim['ref'].rsplit('/', 1)[1]}",
        title=title,
        episode=EPISODE,
        check=flag["check"],
        lang=flag["lang"],
        target=Target(kind="subtitle_cue", refs=[claim["ref"]], frames=frames),
        description=f"clean-run flag: {flag['title']}",
        injector="native-clean-run",
        seed=0,
    )


def video_of(title: str) -> Path:
    return next(p for p in sorted((DATA_DIR / title).iterdir()) if p.suffix in PICTURE_SUFFIXES)


def picture_json(title: str, video: Path, out: Path) -> Path:
    cuts = json.loads(Path(CUTS.format(title=title)).read_text())["cuts"]
    m = probe(video)
    edges = [0, *cuts, m.duration_frames]
    out.parent.mkdir(parents=True, exist_ok=True)
    pic = {
        "fps": [m.fps.numerator, m.fps.denominator],
        "duration_frames": m.duration_frames,
        "start_tc_frames": 0,
        "drop_frame": False,
        "shots": [[a, b] for a, b in zip(edges, edges[1:], strict=False)],
        "keyframes": [],
    }
    out.write_text(json.dumps(pic), encoding="utf-8")
    return out


def other_tracks(title: str, src: Path) -> list[dict[str, Any]]:
    """Drift/offset flags of the tracks the store run cannot take (no rule pack for `it`): the same
    checks on a Timeline built from the files, with the picture's shots and probed rate."""
    fps = probe(video_of(title)).fps
    langs = {p.name.split("_")[0]: p for p in sorted(src.glob("*.srt"))}
    extra = [lang for lang in langs if lang not in MVP_LANGS]
    if not extra:
        return []
    spans = [Span(kind=EvidenceKind.SHOT, ref=refs.shot(EPISODE, 0), frames=(0, 10**6))]
    for lang in ("en", *extra):
        track = parse_srt(langs[lang].read_bytes()).data
        assert track is not None, langs[lang]
        for c in track.cues:
            a = ms_to_frame(c.start_ms, fps)
            f = (a, max(ms_to_frame(c.end_ms, fps), a + 1))
            ref = refs.cue(EPISODE, lang, c.idx)
            spans.append(
                Span(kind=EvidenceKind.SUBTITLE_CUE, ref=ref, frames=f, lang=lang, text=c.text)
            )
    tl = Timeline(
        episode=EPISODE, fps=(fps.numerator, fps.denominator), duration_frames=10**6, spans=spans
    )
    pb = ProducedBy(model_variant=None, plan_id="none")
    out: list[dict[str, Any]] = []
    for chk in (Drift(extra, "en"), Offset(extra, "en")):
        out += [json.loads(f.model_dump_json()) for f in run_check(chk, tl, "run_bench", pb)]
    return out


def run_show(engine: Engine, title: str, src: Path, slug: str) -> list[dict[str, Any]]:
    """Ingest the MVP-language tracks of `src` (+ sidecars + picture) as show `slug`, run the
    stages, return the flags (plus `other_tracks`)."""
    video = video_of(title)
    pic = picture_json(title, video, OUT / "pictures" / f"{title}.json")
    files: list[tuple[str | None, Path]] = [
        (p.name.split("_")[0], p)
        for p in sorted(src.glob("*.srt"))
        if p.name.split("_")[0] in MVP_LANGS
    ]
    files += [
        (None, SIDECAR / title / "bible.yaml"),
        ("glossary", SIDECAR / title / "glossary.csv"),
    ]
    files += [(None, video)]
    with engine.begin() as conn:
        ingest_files(conn, NullS3(), show=slug, episode=EPISODE, files=files, picture=pic)
    plan, inv = stub_plan()
    out = OUT / slug
    summary = pipeline.run_store(
        engine, NullS3(), show=slug, episodes=[EPISODE], plan=plan, inventory=inv, out_dir=out
    )
    walls = {s["stage"]: s["wall_s"] for s in summary["episodes"][EPISODE]["stages"]}
    print(slug, summary["status"], walls)
    stored = [json.loads(x) for x in (out / EPISODE / "flags.jsonl").read_text().splitlines()]
    return stored + other_tracks(title, src)


def score(d: Path, variant: str, seed: int, exp: str, natives: bool) -> None:
    cmd = [
        sys.executable, "-c", "from nip.cli import app; app()", "eval", "run",
        "--set", SET, "--flags", str(d / "flags.jsonl"), "--labels", str(d / "injected.jsonl"),
        *(["--labels", str(d / "clean-run.native.jsonl")] if natives else []),
        "--exp", exp, "--variant", variant, "--seed", str(seed), "--tracking-uri", TRACKING,
        "--out-dir", str(d / "report"),
    ]  # fmt: skip
    subprocess.run(cmd, check=True)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--exp", default="2.4r1", help="MLflow tag exp (and the compare key)")
    ap.add_argument("--no-mlflow", action="store_true")
    ap.add_argument("--checks", nargs="+", default=list(CHECKS), help="score only these checks")
    args = ap.parse_args(argv)
    url = make_url(database_url())
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {DB}"))
    engine = create_engine(url.set(database=DB))
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION vector"))
        c.execute(text("CREATE EXTENSION btree_gist"))
        metadata.create_all(c)
    pipeline.add_stage("timeline.cue_align", cue_align.stage, before="checks")
    pipeline.add_stage("loc.observed", term.stage, before="checks")
    try:
        for title in TITLES:
            clean = run_show(engine, title, DATA_DIR / title, f"bench-{title}-clean")
            print(title, "clean flags:", {c: sum(f["check"] == c for f in clean) for c in CHECKS})
            for seed in args.seeds:
                labels = [
                    lb
                    for lb in load_labels(INJECT / f"seed{seed}" / "labels" / f"{title}.jsonl")
                    if lb.check in args.checks
                ]
                injected = {c: {lb.lang for lb in labels if lb.check == c} for c in CHECKS}
                flags = run_show(
                    engine, title, INJECT / f"seed{seed}" / title, f"bench-{title}-s{seed}"
                )
                d = OUT / "score" / title / f"seed{seed}"
                d.mkdir(parents=True, exist_ok=True)
                (d / "flags.jsonl").write_text(
                    "".join(
                        json.dumps(f) + "\n"
                        for f in scope_flags(flags, injected)
                        if f["check"] in args.checks
                    ),
                    encoding="utf-8",
                )
                (d / "injected.jsonl").write_text(
                    "".join(lb.model_dump_json() + "\n" for lb in labels), encoding="utf-8"
                )
                nat = [
                    native_label(f, title)
                    for f in scope_flags(clean, injected)
                    if f["check"] not in WHOLE_TRACK and f["check"] in args.checks
                ]
                (d / "clean-run.native.jsonl").write_text(
                    "".join(lb.model_dump_json() + "\n" for lb in nat), encoding="utf-8"
                )
                if not args.no_mlflow:
                    score(d, f"regression-{title}", seed, args.exp, natives=True)
                    score(d, f"raw-{title}", seed, args.exp, natives=False)
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)"))
        admin.dispose()


if __name__ == "__main__":
    main()
