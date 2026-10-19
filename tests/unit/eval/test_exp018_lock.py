"""EXP-018 GPU session: an interrupt while another agent holds data/gpu.lock leaves its lock and its
Serve apps alone (2.1B re-review N1)."""

from pathlib import Path

import pytest

from eval.exp import exp018_kv as kv


def test_an_interrupt_while_waiting_never_touches_another_holders_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "gpu.lock"
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(kv, "LOCK", lock)
    monkeypatch.setattr(kv, "ray_head", lambda *a, **k: calls.append(a) or "")
    monkeypatch.setattr(kv, "host_used_mib", lambda: 5000)  # the desktop is busy: wait

    def other_agent_takes_the_lock_then_ctrl_c(_: float) -> None:
        lock.mkdir()
        (lock / "owner.txt").write_text("2.7 EXP-017 pid 1\n")
        raise KeyboardInterrupt

    monkeypatch.setattr(kv.time, "sleep", other_agent_takes_the_lock_then_ctrl_c)
    with pytest.raises(KeyboardInterrupt), kv.gpu_session("test"):
        pass
    assert (lock / "owner.txt").read_text() == "2.7 EXP-017 pid 1\n"  # theirs, untouched
    assert calls == []  # no `down`: their Serve apps stay up


def test_the_holder_tears_down_and_releases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "gpu.lock"
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(kv, "LOCK", lock)
    monkeypatch.setattr(kv, "ray_head", lambda *a, **k: calls.append(a) or "")
    monkeypatch.setattr(kv, "host_used_mib", lambda: 400)
    with kv.gpu_session("test"):
        assert kv.holds_lock()
    assert not lock.exists() and calls[-1][-1] == "down"
