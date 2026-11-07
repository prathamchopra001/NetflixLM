"""EXP-008: keyframe density for on-screen text (docs/experiments.md), and the shared bench the
clearance experiments (EXP-017, the end-to-end run) use.

    uv run python -m eval.exp.exp008_keyframes scan  --seeds 1,2,3 [--cpu]
    uv run python -m eval.exp.exp008_keyframes score --seeds 1,2,3
    nip eval compare --exp EXP-008 --md --tracking-uri sqlite:///data/mlflow/mlflow.db

Set: the two films' clr.text injections (`nip eval inject --set mvp --seed N --only clr --out
data/inject-clr`), 3 seeds. Variants differ ONLY in which frames are read:
  1-per-shot     the middle frame of every shot
  1-per-shot+2s  + one every 2 s in shots longer than 4 s (the B-027 policy)
  1-per-shot+1s  + one every 1 s in shots longer than 1 s
The arms are nested (frames of an arm are among the next one's), so each distinct frame is read
once and an arm takes its frames from that cache. Everything after the read is production code:
`stage.scan_image` (OCR reader + TextScanner), the six `ClearanceText` checks, `verify`.

The two films are scored as episodes S01E01 (Sintel) and S01E02 (Tears of Steel) of one benchmark
run, so one flags file and one label file go to `nip eval run` (their labels all say S01E01).
Extra metrics (keyframes per minute, reading seconds per content hour) are logged to the same
MLflow run so `nip eval compare` prints them.
"""

import json
import os
import pickle
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import typer

from eval.corpus.downloader import load_manifest
from eval.injectors import Label, write_labels
from eval.injectors.base import Target
from nip.agents.base import run_check
from nip.agents.clearance import TEXT_CHECKS
from nip.agents.clearance.matching import Item, Registry
from nip.agents.clearance.occurrences import Hit, analyze
from nip.agents.clearance.ocr_text import TextScanner
from nip.agents.clearance.stage import Scan, confidence, scan_image, with_ocr
from nip.config import pipeline_config
from nip.contracts import refs
from nip.contracts.flag import EvidenceKind, Flag, ProducedBy
from nip.contracts.timeline import Span, Timeline
from nip.ingest import parse_bible, parse_clearance_log
from nip.ingest.media import MediaInfo, probe
from nip.timecode import frame_to_smpte
from nip.timeline.keyframes import extract_keyframes, keyframe_frames
from nip.verification.verify import verify

ROOT = Path("data/exp008")
INJECT = Path("data/inject-clr/mvp")
SIDECAR = Path("eval/corpus/sidecar")
NATIVE = Path("eval/labels/exp008")  # agent-provisional labels of text the films already had
TRACKING = "sqlite:///data/mlflow/mlflow.db"
LOCK = Path("data/gpu.lock")
# film -> (picture.json with the shots, episode ref in the benchmark run)
FILMS = {
    "sintel": ("data/runs/1.10/sintel/picture.json", "S01E01"),
    "tears-of-steel": ("data/runs/2.5/tears-of-steel/picture.json", "S01E02"),
}
# arm -> (long_shot_s, interval_s) of `keyframe_frames`
ARMS: dict[str, tuple[float, float]] = {
    "1-per-shot": (1e9, 2.0),
    "1-per-shot+2s": (4.0, 2.0),
    "1-per-shot+1s": (1.0, 1.0),
}
UNION = ARMS["1-per-shot+1s"]
CHECK_OF = {
    "phone": "clr.phone", "url": "clr.url", "email": "clr.email",
    "address": "clr.address", "plate": "clr.plate",
    "brand": "clr.brand_text",
}  # fmt: skip
app = typer.Typer(no_args_is_help=True)


# ---- the GPU mutex (phased-plan.md > GPU contention) -------------------------------------------
@contextmanager
def gpu_lock(
    purpose: str, poll_s: float = float(os.environ.get("GPU_LOCK_POLL_S", "60"))
) -> Iterator[None]:
    """`mkdir data/gpu.lock` (atomic) + owner.txt; polls until it is free; removes it on exit."""
    while True:
        try:
            LOCK.mkdir()
            break
        except FileExistsError:
            print(
                f"gpu.lock held ({(LOCK / 'owner.txt').read_text().strip()}); waiting", flush=True
            )
            time.sleep(poll_s)
    (LOCK / "owner.txt").write_text(
        f"2.7 {purpose} {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n", encoding="utf-8"
    )
    try:
        yield
    finally:
        (LOCK / "owner.txt").unlink(missing_ok=True)
        LOCK.rmdir()


# ---- one film, one seed ------------------------------------------------------------------------
@dataclass
class Film:
    name: str
    seed: int
    episode: str
    video: Path
    info: MediaInfo
    shots: list[tuple[int, int]]
    items: list[dict[str, Any]]  # what the injector rendered (`<video>.clr.json`)
    registry: Registry
    deny: tuple[str, ...]
    deny_addresses: tuple[str, ...]
    fictional: tuple[str, ...]
    labels: list[Label] = field(default_factory=list)
    natives: list[Label] = field(default_factory=list)
    title: str = ""

    @property
    def hours(self) -> float:
        return float(self.info.duration_frames / self.info.fps) / 3600

    @property
    def lang(self) -> str:
        return "en"


def load_film(name: str, seed: int) -> Film:
    pic_json, episode = FILMS[name]
    folder = INJECT / f"seed{seed}" / name
    video = next(
        p for p in sorted(folder.iterdir()) if p.suffix.lower() in (".mkv", ".mov", ".mp4")
    )
    info = probe(video)
    shots = [tuple(s) for s in json.loads(Path(pic_json).read_text("utf-8"))["shots"]]
    items = json.loads(video.with_name(video.name + ".clr.json").read_text("utf-8"))["items"]
    log = parse_clearance_log((SIDECAR / name / "clearance_log.csv").read_bytes()).data
    bible = parse_bible((SIDECAR / name / "bible.yaml").read_bytes()).data
    assert log is not None and bible is not None
    reg_items = tuple(
        Item(i, e.item, e.kind, e.status, e.scope or None) for i, e in enumerate(log, 1)
    )
    title = next(t["title"] for t in load_manifest()["titles"] if t["id"] == name)
    # What the production invented is not a clearance item, and neither is its own title
    # (the show row carries it in the store: `load_registry`).
    fictional = tuple(
        [title, *bible.fictional.brands, *bible.fictional.orgs, *bible.fictional.places]
    )
    deny = tuple(i.name for i in reg_items if i.kind in ("brand", "logo", "product", "artwork"))
    addresses = tuple(i.name for i in reg_items if i.kind in ("address", "location"))
    labels = [
        lb.model_copy(update={"episode": episode})
        for lb in _read_labels(INJECT / f"seed{seed}" / "labels" / f"{name}.jsonl")
    ]
    native_file = NATIVE / f"{name}.native.jsonl"
    natives = (
        [lb.model_copy(update={"episode": episode}) for lb in _read_labels(native_file)]
        if native_file.exists()
        else []
    )
    return Film(name, seed, episode, video, info, shots, items, Registry(reg_items, fictional),
                deny, addresses, fictional, labels, natives, title)  # fmt: skip


def _read_labels(path: Path) -> list[Label]:
    return [Label.model_validate_json(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


def all_positive_labels(film: Film) -> list[Label]:
    """A label per rendered positive, cleared ones too: the audit trail must hold them (they are
    suppressed, not unseen), so this scores detection recall independent of routing."""
    out = []
    for n, it in enumerate(film.items, 1):
        if it["negative"]:
            continue
        a, b = it["frames"]
        out.append(
            Label(
                label_id=f"{film.name}-clr-s{film.seed}-all-{n}", title=film.name,
                episode=film.episode, check=CHECK_OF[it["kind"]],
                target=Target(kind="frame_range", frames=(a, b)),
                description=f"{it['kind']} {it['text']!r} ({it['status']})",
                injector="clr.text.v1", seed=film.seed,
            )
        )  # fmt: skip
    return out


# ---- frames and scans --------------------------------------------------------------------------
def policy(film: Film, arm: str) -> list[tuple[int, int, int]]:
    """(shot, n, frame) of the arm's keyframes (n counts within the shot as `extract_keyframes`)."""
    long_s, every = ARMS[arm]
    out = []
    for i, shot in enumerate(film.shots):
        for n, f in enumerate(keyframe_frames(shot, film.info.fps, long_s, every)):
            out.append((i, n, f))
    return out


def extract(film: Film) -> dict[int, Path]:
    """frame -> jpg of every frame any arm reads, decoded from the injected picture once."""
    folder = ROOT / "frames" / f"{film.name}-s{film.seed}"
    index = folder / "frames.json"
    if not index.exists():
        long_s, every = UNION
        recs = extract_keyframes(
            film.video, film.shots, film.info.fps, folder, long_shot_s=long_s, interval_s=every
        )
        index.write_text(json.dumps({r["frame"]: r["file"] for r in recs}), encoding="utf-8")
    return {int(f): folder / name for f, name in json.loads(index.read_text("utf-8")).items()}


def scan_union(
    film: Film, reader: Any, scanner: TextScanner, tag: str, only: set[int] | None = None
) -> dict[int, tuple[Scan, float]]:
    """frame -> (its Scan, seconds the read + scan took), cached on disk per reader `tag`;
    `only`: just these frames (default: every frame any arm reads)."""
    cache = ROOT / "scans" / f"{tag}-{film.name}-s{film.seed}.pkl"
    done: dict[int, tuple[Scan, float]] = pickle.loads(cache.read_bytes()) if cache.exists() else {}
    frames = extract(film)
    by_frame = {f: (i, n) for i, n, f in policy(film, "1-per-shot+1s")}
    todo = [f for f in sorted(frames) if f not in done and (only is None or f in only)]
    cache.parent.mkdir(parents=True, exist_ok=True)
    for k, f in enumerate(todo, 1):
        shot, n = by_frame[f]
        data = frames[f].read_bytes()
        t = time.perf_counter()
        scan = scan_image(shot, n, data, reader, scanner, film.lang)
        done[f] = (scan, time.perf_counter() - t)
        if k % 100 == 0 or k == len(todo):
            cache.write_bytes(pickle.dumps(done))
            print(f"  {film.name} s{film.seed} {tag}: {k}/{len(todo)} frames", flush=True)
    return done


# ---- flags of one arm --------------------------------------------------------------------------
def timeline(film: Film, kfs: Sequence[tuple[int, int, int]]) -> Timeline:
    """The stored timeline of a picture: shots, single-frame keyframes, the clearance items."""
    fps, start, drop = film.info.fps, film.info.start_tc_frames, film.info.drop_frame

    def span(kind: EvidenceKind, ref: str, a: int, b: int) -> Span:
        t = [frame_to_smpte(x + start, fps, drop) for x in (a, b)]
        return Span(kind=kind, ref=ref, frames=(a, b), tc_in=t[0], tc_out=t[1])

    spans = [span(EvidenceKind.SHOT, refs.shot(film.episode, i), a, b)
             for i, (a, b) in enumerate(film.shots)]  # fmt: skip
    spans += [span(EvidenceKind.KEYFRAME, refs.keyframe(film.episode, i, n), f, f + 1)
              for i, n, f in kfs]  # fmt: skip
    spans += [Span(kind=EvidenceKind.CLEARANCE_ITEM, ref=f"clr/{i.id}", text=i.name)
              for i in film.registry.items]  # fmt: skip
    return Timeline(episode=film.episode, fps=(fps.numerator, fps.denominator),
                    duration_frames=film.info.duration_frames, start_tc_frames=start,
                    drop_frame=drop, spans=tuple(spans))  # fmt: skip


def arm_scans(
    film: Film, arm: str, union: dict[int, tuple[Scan, float]]
) -> tuple[list[tuple[int, int, int]], dict[tuple[int, int], Scan], float]:
    """(keyframes of the arm, its Scans renumbered to the arm's keyframe numbers, seconds spent)."""
    kfs = policy(film, arm)
    scans: dict[tuple[int, int], Scan] = {}
    secs = 0.0
    for shot, n, f in kfs:
        s, took = union[f]
        secs += took
        scans[shot, n] = Scan(
            [replace(d, shot=shot, n=n) for d in s.lines],
            [replace(c, shot=shot, n=n) for c in s.candidates],
            s.sharpness,
        )
    return kfs, scans, secs


def hits_of(scans: dict[tuple[int, int], Scan], cfg: dict[str, Any]) -> list[Hit]:
    return [
        Hit(c.check, c.text, c.shot, c.n, c.box, confidence(c, cfg), c.model_variant, sharp)
        for k in sorted(scans)
        for c, sharp in zip(scans[k].candidates, scans[k].sharpness, strict=True)
    ]


def arm_flags(
    film: Film, kfs: list[tuple[int, int, int]], scans: dict[tuple[int, int], Scan], plan: str
) -> tuple[list[Flag], list[tuple[Flag, str]]]:
    """The six checks over the arm's detections, then verification (kept, dropped)."""
    cfg = pipeline_config()["clearance"]
    stored = timeline(film, kfs)
    occs = analyze(hits_of(scans, cfg), film.registry, stored, cfg, kfs)
    tl = with_ocr(stored, scans, occs)
    checks = [
        c(hits=hits_of(scans, cfg), registry=film.registry, keyframes=kfs, cfg=cfg)
        for c in TEXT_CHECKS
    ]
    pb = ProducedBy(model_variant="pp-ocrv6-medium", plan_id=plan)
    flags = [f for c in checks for f in run_check(c, tl, f"bench_{film.name}", pb)]
    kept, dropped = verify(flags, tl, checks)
    return kept, dropped


# ---- scoring through `nip eval run` ------------------------------------------------------------
def nip_eval_run(
    flags: list[Flag], labels: list[Label], *, exp: str, variant: str, seed: int, out: Path,
    content_hours: float, gpu_seconds: float, extra: dict[str, float], params: dict[str, str],
    natives: Sequence[Label] = (),
) -> str:  # fmt: skip
    """Write the files, call `nip eval run`, add `extra` metrics to its MLflow run; its output."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "flags.jsonl").write_text("".join(f.model_dump_json() + "\n" for f in flags), "utf-8")
    write_labels(labels, out / "labels.jsonl")
    label_args = ["--labels", str(out / "labels.jsonl")]
    if natives:  # `*.native.jsonl`: a flag on text the film already had is a native TP, not a FP
        write_labels(list(natives), out / "text.native.jsonl")
        label_args += ["--labels", str(out / "text.native.jsonl")]
    cmd = [str(Path(sys.executable).with_name("nip")), "eval", "run", "--set", "mvp",
           "--flags", str(out / "flags.jsonl"), *label_args,
           "--exp", exp, "--variant", variant, "--seed", str(seed),
           "--content-hours", f"{content_hours:.6f}", "--gpu-seconds", f"{gpu_seconds:.3f}",
           "--tracking-uri", TRACKING, "--out-dir", str(out / "eval")]  # fmt: skip
    for k, v in params.items():
        cmd += ["--param", f"{k}={v}"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    line = res.stdout.strip().splitlines()[-1]
    run_id = line.split("mlflow_run_id=")[1].split()[0]
    from mlflow import MlflowClient

    client = MlflowClient(TRACKING)
    for name, value in extra.items():
        client.log_metric(run_id, name, value)
    return line


def score_arm(
    films: Sequence[Film], unions: dict[tuple[str, int], dict[int, tuple[Scan, float]]],
    arm: str, exp: str, seed: int, root: Path, extra_params: dict[str, str] | None = None,
    arm_name: str | None = None, prefix: str = "exp008",
) -> dict[str, Any]:  # fmt: skip
    """Flags of every film for one arm and seed, scored against the official (injected) labels,
    again with the agent-provisional native labels (`+native`) and against every rendered positive
    (detection recall; `@all-positives`, read with `--subset all`)."""
    flags: list[Flag] = []
    n_kf = 0
    secs = 0.0
    for film in (f for f in films if f.seed == seed):
        kfs, scans, took = arm_scans(film, arm, unions[film.name, seed])
        kept, dropped = arm_flags(film, kfs, scans, f"bench-{arm}")
        flags += kept
        n_kf += len(kfs)
        secs += took
        if dropped:
            print(f"  {film.name} s{seed} {arm}: dropped {[(f.title, r) for f, r in dropped]}")
    sel = [f for f in films if f.seed == seed]
    hours = sum(f.hours for f in sel)
    extra = {
        f"{prefix}/keyframes": float(n_kf),
        f"{prefix}/keyframes_per_min": n_kf / (hours * 60),
        f"{prefix}/read_s_per_content_hour": secs / hours,
    }
    name = arm_name or arm
    params = {"arm": arm, **(extra_params or {})}
    official = [lb for f in sel for lb in f.labels]
    allpos = [lb for f in sel for lb in all_positive_labels(f)]
    natives = [lb for f in sel for lb in f.natives]
    runs: list[tuple[str, list[Label], list[Label]]] = [
        (name, official, []),  # precision against the injected labels only
        (f"{name}@all-positives", allpos, []),
    ]
    if natives:  # plus the film's own real third-party text (agent-provisional native labels)
        runs.insert(1, (f"{name}+native", official, natives))
    for variant, labels, nat in runs:
        line = nip_eval_run(flags, labels, exp=exp, variant=variant, seed=seed,
                            out=root / f"{variant}-s{seed}", content_hours=hours, gpu_seconds=secs,
                            extra=extra, params=params, natives=nat)  # fmt: skip
        print(line, flush=True)
    return {"flags": flags, "keyframes": n_kf, "secs": secs, "hours": hours}


# ---- commands ----------------------------------------------------------------------------------
def _scanner(cuda: bool) -> tuple[Any, Any, Callable[[Film], TextScanner]]:
    from nip.runtime.clients.ner import GlinerBackend
    from nip.runtime.clients.ocr import RapidOcrBackend

    ner = GlinerBackend(cuda=cuda)
    reader = RapidOcrBackend(cuda=cuda)
    return (
        reader,
        ner,
        lambda film: TextScanner(
            ner, deny_brands=film.deny, deny_addresses=film.deny_addresses, fictional=film.fictional
        ),
    )


@app.command("collisions")
def collisions_cmd(
    tag: str = "cpu4", seeds: str = "1,2,3", arm: str = "1-per-shot+2s",
    films: str = "sintel,tears-of-steel",
) -> None:  # fmt: skip
    """R13: how many flags of one run share a fingerprint with another (must be 0)."""
    from collections import Counter

    from nip.store.runs import fingerprint

    for seed in map(int, seeds.split(",")):
        for name in films.split(","):
            film = load_film(name, seed)
            union = pickle.loads((ROOT / "scans" / f"{tag}-{name}-s{seed}.pkl").read_bytes())
            kfs, scans, _ = arm_scans(film, arm, union)
            kept, _ = arm_flags(film, kfs, scans, "collisions")
            c = Counter(fingerprint(f) for f in kept)
            dup = sum(v for v in c.values() if v > 1)
            print(f"{name} s{seed}: {len(kept)} flags, {len(c)} fingerprints, {dup} colliding")


@app.command("natives")
def natives_cmd(
    tag: str = "cpu4", seed: int = 1, accept: bool = False, films: str = "sintel,tears-of-steel"
) -> None:
    """Unknown clr.url flags on text the film already had (outside every injected window), of the
    `1-per-shot+2s` flags of one seed. Without --accept: list them. With --accept: write
    `eval/labels/exp008/<film>.native.jsonl` for the texts of `accepted_urls.yaml` there
    (a person-or-agent decision per text: a real third-party web address printed in the credits is a
    correct `unknown` flag). The labels are agent-provisional: `injector` clr.native.agent.v1,
    `reviewed` false, frames = the flag's occurrence range."""
    import yaml

    accepted: dict[str, list[str]] = {}
    if accept:
        accepted = yaml.safe_load((NATIVE / "accepted_urls.yaml").read_text("utf-8"))
    for name in films.split(","):
        film = load_film(name, seed)
        union = pickle.loads((ROOT / "scans" / f"{tag}-{name}-s{seed}.pkl").read_bytes())
        kfs, scans, _ = arm_scans(film, "1-per-shot+2s", union)
        kept, _ = arm_flags(film, kfs, scans, "natives")
        wins = [tuple(it["frames"]) for it in film.items]
        labels: list[Label] = []
        for f in kept:
            if str(f.check) != "clr.url" or "not in the clearance log" not in f.explanation:
                continue
            claim = next(e for e in f.evidence if e.role.value == "claim")
            a, b = claim.frames or (0, 1)
            if any(min(b, y) > max(a, x) for x, y in wins):
                continue  # on an injected overlay
            text = claim.quote or ""
            if not accept:
                print(f"{name}: {a}-{b} {text}")
            elif text in accepted.get(name, []):
                labels.append(
                    Label(
                        label_id=f"{name}-native-url-{len(labels) + 1}", title=name,
                        episode=film.episode, check="clr.url",
                        target=Target(kind="frame_range", frames=(a, b)),
                        description=f"labeller: agent (provisional): third-party web address "
                        f"{text!r} printed in the film's own credits",
                        injector="clr.native.agent.v1", seed=0, reviewed=False,
                    )
                )  # fmt: skip
        if accept:
            write_labels(labels, NATIVE / f"{name}.native.jsonl")
            print(f"{name}: {len(labels)} native labels")


@app.command("dense-cost")
def dense_cost_cmd(
    seed: int = 2, src: str = "cpu", films: str = "sintel,tears-of-steel", lo: int = 8
) -> None:
    """What the credits-card rule costs: GLiNER address / brand candidates on keyframes with `lo` or
    more OCR lines that the rule removes, split into 8-11 lines (text in a scene) and 12 or more
    (credits). Same cached OCR lines, the scanner with and without the rule."""
    from nip.runtime.clients.ner import GlinerBackend

    ner = GlinerBackend(cuda=False)
    for name in films.split(","):
        film = load_film(name, seed)
        old = pickle.loads((ROOT / "scans" / f"{src}-{name}-s{seed}.pkl").read_bytes())
        off = TextScanner(
            ner, deny_brands=film.deny, deny_addresses=film.deny_addresses,
            fictional=film.fictional, dense_lines=10**6,
        )  # fmt: skip
        on = TextScanner(
            ner, deny_brands=film.deny, deny_addresses=film.deny_addresses,
            fictional=film.fictional,
        )  # fmt: skip
        gone: dict[str, list[str]] = {"8-11": [], "12+": []}
        n_frames = {"8-11": 0, "12+": 0}
        for f, (scan, _) in sorted(old.items()):
            n = len(scan.lines)
            if n < lo:
                continue
            band = "8-11" if n < 12 else "12+"
            n_frames[band] += 1
            kept = {(c.check, c.text) for c in on.candidates(scan.lines, film.lang)}
            for c in off.candidates(scan.lines, film.lang):
                if (c.check, c.text) not in kept:
                    gone[band].append(f"{f}:{c.check}:{c.text}")
        print(f"{name} s{seed}: frames with 8-11 lines {n_frames['8-11']}, 12+ {n_frames['12+']}")
        for band, items in gone.items():
            print(f"  removed in {band}: {len(items)}")
        for it in gone["8-11"]:
            print("   ", it)


@app.command("rescan")
def rescan_cmd(
    seeds: str = "1,2,3", src: str = "cpu", dst: str = "cpu2", cpu: bool = True,
    films: str = "sintel,tears-of-steel",
) -> None:  # fmt: skip
    """New candidates from the cached OCR lines of tag `src` (a scanner change needs no new OCR);
    the sharpness of each candidate is measured again on the cached keyframe image."""
    from nip.agents.clearance.occurrences import sharpness
    from nip.runtime.clients.ner import GlinerBackend

    ner = GlinerBackend(cuda=not cpu)
    for seed in map(int, seeds.split(",")):
        for name in films.split(","):
            film = load_film(name, seed)
            frames = extract(film)
            scanner = TextScanner(
                ner,
                deny_brands=film.deny,
                deny_addresses=film.deny_addresses,
                fictional=film.fictional,
            )
            old = pickle.loads((ROOT / "scans" / f"{src}-{name}-s{seed}.pkl").read_bytes())
            new = {}
            for f, (scan, took) in old.items():
                cands = scanner.candidates(scan.lines, film.lang)
                data = frames[f].read_bytes() if cands else b""
                new[f] = (Scan(scan.lines, cands, [sharpness(data, c.box) for c in cands]), took)
            (ROOT / "scans" / f"{dst}-{name}-s{seed}.pkl").write_bytes(pickle.dumps(new))
            print(
                f"{name} s{seed}: {sum(len(s.candidates) for s, _ in new.values())} candidates "
                f"(was {sum(len(s.candidates) for s, _ in old.values())})",
                flush=True,
            )


@app.command("scan")
def scan_cmd(
    seeds: str = "1,2,3", cpu: bool = typer.Option(False, help="No GPU (no lock): slower"),
    films: str = "sintel,tears-of-steel", arm: str = typer.Option("", help="Only this arm"),
) -> None:  # fmt: skip
    """Read every frame any arm needs, once, and cache the scans (GPU lock unless --cpu)."""

    def work() -> None:
        reader, _, make = _scanner(cuda=not cpu)
        for seed in map(int, seeds.split(",")):
            for name in films.split(","):
                film = load_film(name, seed)
                only = {f for _, _, f in policy(film, arm)} if arm else None
                scan_union(film, reader, make(film), "cpu" if cpu else "gpu", only)

    if cpu or os.environ.get("GPU_LOCK_HELD"):  # a driver (exp017_session) holds the lock
        work()
    else:
        with gpu_lock("EXP-008 OCR keyframe scans"):
            work()


@app.command("score")
def score_cmd(
    seeds: str = "1,2,3", tag: str = "gpu", exp: str = "EXP-008",
    films: str = "sintel,tears-of-steel",
) -> None:  # fmt: skip
    """Flags + `nip eval run` for every arm and seed, from the cached scans."""
    sel = [load_film(n, s) for s in map(int, seeds.split(",")) for n in films.split(",")]
    unions = {
        (f.name, f.seed): pickle.loads(
            (ROOT / "scans" / f"{tag}-{f.name}-s{f.seed}.pkl").read_bytes()
        )
        for f in sel
    }
    for seed in map(int, seeds.split(",")):
        for arm in ARMS:
            score_arm(sel, unions, arm, exp, seed, ROOT / "runs", {"reader": tag})


if __name__ == "__main__":
    app()
