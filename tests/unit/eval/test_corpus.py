import hashlib
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eval.corpus.downloader import (
    MANIFEST,
    app,
    assets,
    fetch_title,
    filename,
    load_manifest,
    record_sha256,
)

LICENSES = {"CC-BY-2.5", "CC-BY-3.0", "CC-BY-4.0", "Public-Domain-US"}


def test_manifest_shape() -> None:
    m = load_manifest()
    ids = [t["id"] for t in m["titles"]]
    assert len(ids) == len(set(ids))
    for t in m["titles"]:
        assert t["license"] in LICENSES and t["attribution"] and "restrictions" in t
        assert "ND" not in t["license"]  # CC BY-ND titles are excluded (derivatives)
    # YAML reads a bare `no:` (Norwegian) as False
    assert all(isinstance(k, str) for t in m["titles"] for k in assets(t))
    assert all(i in ids for s in m["sets"].values() for i in s)
    sintel = next(t for t in m["titles"] if t["id"] == "sintel")
    assert {"picture", "en", "es", "fr", "de"} <= set(assets(sintel))


def test_manifest_sha256_are_hex() -> None:
    for t in load_manifest()["titles"]:
        assert all(re.fullmatch(r"[0-9a-f]{64}", v) for v in t["sha256"].values())


def test_filename() -> None:
    assert filename("picture", "https://x/y/Film.mkv") == "Film.mkv"
    assert filename("es", "https://x/TOS-es.srt") == "es_TOS-es.srt"


def make_title(tmp_path: Path) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    (src / "film.bin").write_bytes(b"picture-bytes")
    (src / "en.srt").write_text("1\n")
    return {
        "id": "t1",
        "source": {
            "picture": (src / "film.bin").as_uri(),
            "script": None,
            "subtitles": {"en": (src / "en.srt").as_uri()},
        },
        "sha256": {},
    }


def test_fetch_records_then_verifies(tmp_path: Path) -> None:
    man = tmp_path / "m.yaml"
    man.write_text("titles:\n- id: t1\n  title: T\n  sha256: {}\n- id: t2\n  sha256: {}\n")
    t = make_title(tmp_path)
    sums = fetch_title(t, tmp_path / "data", man)
    assert sums["picture"] == hashlib.sha256(b"picture-bytes").hexdigest()
    assert (tmp_path / "data/t1/film.bin").read_bytes() == b"picture-bytes"
    text = man.read_text()
    assert sums["picture"] in text and "- id: t2\n  sha256: {}" in text  # t2 untouched

    t["sha256"] = sums
    assert fetch_title(t, tmp_path / "data", man) == sums  # re-run verifies, no download needed
    t["sha256"] = {**sums, "picture": "0" * 64}
    with pytest.raises(ValueError, match="sha256"):
        fetch_title(t, tmp_path / "data", man)


def test_zip_under_plain_name_rejected(tmp_path: Path) -> None:
    import zipfile

    z = tmp_path / "film.mov"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("film.mov", b"x")
    t = {"id": "z", "source": {"picture": z.as_uri()}, "sha256": {}}
    with pytest.raises(ValueError, match="zip"):
        fetch_title(t, tmp_path / "data", None)
    assert not (tmp_path / "data/z/film.mov").exists()


def test_record_sha256_keeps_comments(tmp_path: Path) -> None:
    man = tmp_path / "m.yaml"
    man.write_text("# keep me\n- id: a\n  sha256: {}\n")
    record_sha256(man, "a", {"en": "ab"})
    assert man.read_text() == '# keep me\n- id: a\n  sha256: {"en": "ab"}\n'


def test_cli_requires_selector() -> None:
    r = CliRunner().invoke(app, ["fetch"])
    assert r.exit_code != 0
    assert MANIFEST.exists()
