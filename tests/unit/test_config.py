import os
import subprocess
import sys
from pathlib import Path

import pytest

from nip import config
from nip.agents.localization.readability import rule_pack
from nip.timeline.picture import timeline_config

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def test_source_tree_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NIP_CONFIG_DIR", raising=False)
    assert config.config_dir() == REPO_CONFIG


def test_installed_package_falls_back_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-editable install: site-packages has no config/ next to it (the image's WORKDIR /app)."""
    monkeypatch.delenv("NIP_CONFIG_DIR", raising=False)
    monkeypatch.setattr(config, "_SOURCE_TREE", tmp_path / "site-packages" / "config")
    monkeypatch.chdir(tmp_path)
    assert config.config_dir() == tmp_path / "config"


def test_env_var_wins_and_every_reader_follows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "languages").mkdir()
    (tmp_path / "languages" / "es.yaml").write_text("readability: {max_lines: 9}")
    (tmp_path / "pipeline.yaml").write_text("timeline: {shots: {threshold: 0.25}}")
    monkeypatch.setenv("NIP_CONFIG_DIR", str(tmp_path))
    assert config.config_dir() == tmp_path
    assert rule_pack("es")["readability"] == {"max_lines": 9}
    assert timeline_config() == {"shots": {"threshold": 0.25}}


def _hf_home(env: dict[str, str]) -> str:
    """HF_HOME as huggingface_hub sees it after `import nip` in a fresh interpreter."""
    code = "import nip, huggingface_hub.constants as c; print(c.HF_HOME)"
    clean = {k: v for k, v in os.environ.items() if k not in ("HF_HOME", "NIP_MODEL_CACHE")}
    out = subprocess.run([sys.executable, "-c", code], env=clean | env, capture_output=True,
                         text=True, check=True)  # fmt: skip
    return out.stdout.strip()


def test_hf_home_defaults_into_the_repo_or_the_mounted_models_dir(tmp_path: Path) -> None:
    """W-7: without HF_HOME, weights go to <repo>/models/hf (host) or $NIP_MODEL_CACHE/hf (the
    image mounts the models dir at /models), never to the user's ~/.cache."""
    assert Path(_hf_home({})) == REPO_CONFIG.parent / "models" / "hf"
    assert Path(_hf_home({"NIP_MODEL_CACHE": str(tmp_path)})) == tmp_path / "hf"
    assert Path(_hf_home({"HF_HOME": str(tmp_path / "mine")})) == tmp_path / "mine"
