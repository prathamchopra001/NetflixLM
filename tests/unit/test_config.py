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
