"""Where the repo's `config/` directory is (catalog, pipeline thresholds, language rule packs).

Importing `nip` (its `__init__` imports this module) also defaults `HF_HOME`, before any Hugging
Face library is imported: `$NIP_MODEL_CACHE/hf` in the image (compose mounts the models dir at
`/models`), else `<repo>/models/hf`, so a run without the variable never downloads weights into
the user's home cache (W-int W-7).
"""

import os
from pathlib import Path
from typing import Any

import yaml

_SOURCE_TREE = Path(__file__).resolve().parents[2] / "config"  # src/nip/config.py -> repo/config


def default_hf_home() -> Path:
    if cache := os.environ.get("NIP_MODEL_CACHE"):
        return Path(cache) / "hf"
    return _SOURCE_TREE.parent / "models" / "hf"


os.environ.setdefault("HF_HOME", str(default_hf_home()))


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
