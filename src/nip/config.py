"""Where the repo's `config/` directory is (catalog, pipeline thresholds, language rule packs)."""

import os
from pathlib import Path
from typing import Any

import yaml

_SOURCE_TREE = Path(__file__).resolve().parents[2] / "config"  # src/nip/config.py -> repo/config


def config_dir() -> Path:
    """`$NIP_CONFIG_DIR`; else `config/` of the source tree (editable install); else `./config`.

    The nip image installs the package non-editable and copies `config/` to `/app/config`
    (WORKDIR `/app`, and the image sets NIP_CONFIG_DIR), so the source-tree path is not used there.
    """
    if env := os.environ.get("NIP_CONFIG_DIR"):
        return Path(env)
    if (_SOURCE_TREE / "pipeline.yaml").is_file():
        return _SOURCE_TREE
    return Path.cwd() / "config"


def pipeline_config() -> dict[str, Any]:
    """`config/pipeline.yaml` (thresholds and policies), read on every call."""
    cfg: dict[str, Any] = yaml.safe_load((config_dir() / "pipeline.yaml").read_text("utf-8"))
    return cfg
