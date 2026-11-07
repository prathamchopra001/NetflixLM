"""Corpus downloader: fetch a manifest title into data/corpus/<id>/, verify or record sha256."""

import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

import typer
import yaml

MANIFEST = Path(__file__).with_name("manifest.yaml")
DATA_DIR = Path("data/corpus")
app = typer.Typer(no_args_is_help=True)


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def assets(title: dict[str, Any]) -> dict[str, str]:
    """Downloadable files of a title as {key: url}; keys are picture, script, <lang>."""
    src = title["source"]
    out = {k: src[k] for k in ("picture", "script") if src.get(k)}
    out.update(src.get("subtitles") or {})
    return out


def filename(key: str, url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    return name if key in ("picture", "script") else f"{key}_{name}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    """GET url to dest, resuming a partial `.part` file; atomic rename at the end."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "nip-corpus/0.1"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=60) as r:
        # 206 = server honoured the range; 200 = restart from zero
        mode = "ab" if have and r.status == 206 else "wb"
        with part.open(mode) as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    part.replace(dest)


def record_sha256(manifest: Path, title_id: str, sums: dict[str, str]) -> None:
    """Rewrite the `sha256:` line of one title in place (keeps the file's comments)."""
    lines = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(
        i for i, ln in enumerate(lines) if re.match(rf"- id: {re.escape(title_id)}\s*$", ln)
    )
    j = next(i for i in range(start, len(lines)) if lines[i].startswith("  sha256:"))
    lines[j] = f"  sha256: {json.dumps(sums)}\n"
    manifest.write_text("".join(lines), encoding="utf-8")


def fetch_title(
    title: dict[str, Any], data_dir: Path = DATA_DIR, manifest: Path | None = MANIFEST
) -> dict[str, str]:
    """Download every asset, verify against recorded sha256 (mismatch raises), record new ones."""
    out_dir = data_dir / title["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    known: dict[str, str] = dict(title.get("sha256") or {})
    sums = dict(known)
    for key, url in assets(title).items():
        dest = out_dir / filename(key, url)
        t0 = time.monotonic()
        if not dest.exists():
            download(url, dest)
            with dest.open("rb") as f:
                is_zip = f.read(2) == b"PK"
            if is_zip and not url.endswith(".zip"):
                dest.unlink()  # some mirrors serve a zip under the plain file name
                raise ValueError(f"{url} returned a zip archive")
        digest = sha256_file(dest)
        if key in known and known[key] != digest:
            raise ValueError(f"{title['id']}/{key}: sha256 {digest} != manifest {known[key]}")
        sums[key] = digest
        typer.echo(
            f"{title['id']}/{key}: {dest.stat().st_size} bytes, {time.monotonic() - t0:.1f}s"
        )
    if manifest is not None and sums != known:
        record_sha256(manifest, title["id"], sums)
    return sums


@app.callback()
def _group() -> None:
    """Corpus manifest tools."""


@app.command()
def fetch(
    set_: str = typer.Option(None, "--set", help="Set name from the manifest (smoke, mvp)."),
    title: str = typer.Option(None, "--title", help="Single title id."),
    no_media: bool = typer.Option(False, "--no-media", help="Skip the large picture file."),
) -> None:
    """Download corpus titles and verify (or record) checksums."""
    m = load_manifest()
    by_id = {t["id"]: t for t in m["titles"]}
    ids = [title] if title else m["sets"][set_] if set_ else []
    if not ids:
        raise typer.BadParameter("give --set or --title")
    for i in ids:
        t = by_id[i]
        if no_media:
            t = {**t, "source": {**t["source"], "picture": None}}
        fetch_title(t, manifest=MANIFEST)
