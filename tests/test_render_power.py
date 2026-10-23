"""A local render's Windows power request must end with its subprocess."""

from types import SimpleNamespace

import pytest

from workers.render import power


def test_render_power_request_is_scoped_even_when_render_fails(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(power, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(power, "_set_thread_execution_state",
                        lambda flags: calls.append(flags) or power.ES_CONTINUOUS)

    with pytest.raises(RuntimeError, match="render failed"):
        with power.keep_system_awake():
            assert calls == [power.ES_CONTINUOUS | power.ES_SYSTEM_REQUIRED]
            raise RuntimeError("render failed")

    assert calls == [
        power.ES_CONTINUOUS | power.ES_SYSTEM_REQUIRED,
        power.ES_CONTINUOUS,
    ]


def test_non_windows_render_does_not_request_power(monkeypatch) -> None:
    monkeypatch.setattr(power, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(power, "_set_thread_execution_state",
                        lambda _: pytest.fail("unexpected Windows API call"))
    with power.keep_system_awake():
        pass
