"""`nip eval inject --set S --seed N`: write injected copies and ground-truth labels for a set.

Wire into the root CLI with:  eval_app.command("inject")(inject)  (from eval.inject import inject).

Output: `<out>/<set>/seed<N>/<title>/` holds the title's subtitle tracks (injected or copied), for
titles with a picture the re-encoded copy plus its `*.clr.json` item list, and for the synthetic
show the clean show (`clean/`) and the injected show (`injected/`); labels go to
`<out>/<set>/seed<N>/labels/<title>.jsonl`. Same set and seed give byte-identical output.
"""

import json
import shutil
import tempfile
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Any

import typer

from eval.corpus.downloader import DATA_DIR, load_manifest
from eval.injectors import Label, get, write_labels
from eval.injectors.common import FILM_EPISODE, PICTURE_SUFFIXES, SIDECAR, picture_fps
from eval.synthetic import build, write_show

SYNTHETIC = "synthetic-show"
# Which injectors run on which track. Text injectors are stacked on one track (each skips the cues
# an earlier one edited); drift and offset own a whole track, because both move every cue.
PLANS: dict[str, dict[str, tuple[str, ...]]] = {
    "sintel": {
        "es": ("term", "shot_change", "readability"),
        "fr": ("drift",),
        "de": ("offset",),
    },
    "tears-of-steel": {
        "es": ("term", "shot_change", "readability"),
        "fr": ("term", "shot_change"),
        "de": ("drift",),
        "it": ("offset",),
    },
}
PLOT = (
    "plot.knowledge_order.v1",
    "plot.dead_acts.v1",
    "plot.two_places.v1",
    "plot.prop_provenance.v1",
)
SHOTS = Path("data/exp002/runs/picture")  # <title>/picture.json from 1.10 / EXP-002

Step = Callable[[Path, Path, set[int]], list[Label]]


def _inj(injector_id: str) -> Any:
    """The registered injector; typed Any because each one adds its own keyword arguments."""
    return get(injector_id)


def _cue_numbers(labels: list[Label]) -> set[int]:
    return {int(r.rsplit("/", 1)[1]) for lb in labels for r in lb.target.refs}


def _cuts(title: str, shots_dir: Path) -> list[int] | None:
    """First frame of every shot after the first, from the cached picture analysis."""
    f = shots_dir / title / "picture.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())  # EXP-002 writes "cuts", `nip timeline picture` writes "shots"
    return [int(c) for c in d["cuts"]] if "cuts" in d else [s[0] for s in d["shots"][1:]]


def _stack(src: Path, dst: Path, steps: list[Step]) -> list[Label]:
    """Run `steps` one after another (each reads the previous output)."""
    labels: list[Label] = []
    with tempfile.TemporaryDirectory() as tmp:
        cur = src
        for i, step in enumerate(steps):
            nxt = dst if i == len(steps) - 1 else Path(tmp) / f"{i}" / src.name
            labels += step(cur, nxt, _cue_numbers(labels))
            cur = nxt
    return labels


def _track_steps(
    names: tuple[str, ...], title: str, lang: str, seed: int, fps: Fraction, cuts: list[int] | None
) -> tuple[list[Step], list[str]]:
    """One step per injector name. `episode`/`title`/`lang` are passed explicitly because a
    stacked step reads a temporary file whose folder is not the title."""
    who = {"episode": FILM_EPISODE, "title": title, "lang": lang}
    steps: list[Step] = []
    skipped: list[str] = []
    for name in names:
        if name == "shot_change" and cuts is None:
            skipped.append("loc.shot_change (no cached shots: run EXP-002's picture stage)")
            continue
        injector = _inj("loc.offset.v2" if name == "offset" else f"loc.{name}.v1")
        by_name: dict[str, dict[str, Any]] = {
            "shot_change": {"cuts": cuts, "fps": fps},
            "term": {"fps": fps, "glossary": SIDECAR / title / "glossary.csv"},
            "drift": {"fps": fps},
            "offset": {"fps": fps},
            "readability": {},
        }
        steps.append(_step(injector, seed, {**who, **by_name[name]}, name in AVOIDING))
    return steps, skipped


AVOIDING = ("term", "shot_change", "readability")  # injectors that skip cues already edited


def _step(injector: Any, seed: int, kw: dict[str, Any], takes_avoid: bool) -> Step:
    def run(src: Path, dst: Path, avoid: set[int]) -> list[Label]:
        extra = {"avoid": avoid} if takes_avoid else {}
        labels: list[Label] = injector.inject(src, dst, seed, **kw, **extra)
        return labels

    return run


def _title(
    title: str, corpus: Path, out: Path, seed: int, only: set[str], shots: Path
) -> list[Label]:
    if not only & {"loc", "clr"}:
        return []
    src = corpus / title
    dst = out / title
    labels: list[Label] = []
    tracks = sorted(src.glob("*.srt"))
    if not tracks:
        typer.echo(f"{title}: no data under {src} (run `nip eval corpus fetch`): skipped")
        return labels
    dst.mkdir(parents=True, exist_ok=True)
    plan = PLANS.get(title, {}) if "loc" in only else {}
    fps = picture_fps(tracks[0])
    cuts = _cuts(title, shots)
    for t in tracks:
        lang = t.name.split("_", 1)[0]
        steps, skipped = _track_steps(plan.get(lang, ()), title, lang, seed, fps, cuts)
        for s in skipped:
            typer.echo(f"{title}/{lang}: skipped {s}")
        if steps:
            labels += _stack(t, dst / t.name, steps)
        else:
            shutil.copy2(t, dst / t.name)
    if "clr" in only:
        picture = next(p for p in sorted(src.iterdir()) if p.suffix.lower() in PICTURE_SUFFIXES)
        labels += _inj("clr.text.v1").inject(picture, dst / picture.name, seed)
    return labels


def _synthetic(out: Path, seed: int) -> list[Label]:
    show = build(seed)
    write_show(show, out / SYNTHETIC / "clean")
    labels: list[Label] = []
    cur = out / SYNTHETIC / "clean"
    with tempfile.TemporaryDirectory() as tmp:
        for i, name in enumerate(PLOT):
            nxt = out / SYNTHETIC / "injected" if i == len(PLOT) - 1 else Path(tmp) / str(i)
            labels += _inj(name).inject(cur, nxt, seed)
            cur = nxt
    return labels


def inject(
    set_: Annotated[str, typer.Option("--set", help="Set name from the corpus manifest (mvp).")],
    seed: Annotated[int, typer.Option(help="Seed: same seed, byte-identical output.")] = 1,
    out: Annotated[Path, typer.Option(help="Output root.")] = Path("data/inject"),
    only: Annotated[str, typer.Option(help="Comma list of loc, clr, plot.")] = "loc,clr,plot",
    corpus: Annotated[Path, typer.Option(help="Corpus root.")] = DATA_DIR,
    shots: Annotated[Path, typer.Option(help="Cached shot analysis root.")] = SHOTS,
) -> None:
    """Inject errors into every title of a set and write labels (docs/evaluation.md > Injectors)."""
    titles = load_manifest()["sets"].get(set_)
    if titles is None:
        raise typer.BadParameter(f"unknown set {set_!r}", param_hint="--set")
    kinds = set(only.split(","))
    root = out / set_ / f"seed{seed}"
    for title in titles:
        if title == SYNTHETIC:
            labels = _synthetic(root, seed) if "plot" in kinds else []
        else:
            labels = _title(title, corpus, root, seed, kinds, shots)
        if labels:
            write_labels(labels, root / "labels" / f"{title}.jsonl")
        by_check: dict[str, int] = {}
        for lb in labels:
            by_check[lb.check] = by_check.get(lb.check, 0) + 1
        typer.echo(f"{title}: {len(labels)} labels {dict(sorted(by_check.items()))}")


app = typer.Typer(add_completion=False)
app.command()(inject)
