"""The installed Windows worker may inherit a legacy-encoded or absent stdout."""
import io

import pytest

from workers.render.remotion_runtime import write_render_log


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
def test_remotion_unicode_progress_survives_windows_console(monkeypatch, encoding):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict", newline="")
    line = "╭ Rendered 30/360 — câmera ⚽\n"
    with monkeypatch.context() as patch:
        patch.setattr("workers.render.remotion_runtime.sys.stdout", stream)
        write_render_log(line)
    decoded = raw.getvalue().decode(encoding)
    assert "Rendered 30/360" in decoded
    assert "câmera" in decoded
    if encoding == "utf-8":
        assert decoded == line
    else:
        assert "\\u256d" in decoded and "\\u26bd" in decoded


def test_windowed_process_without_console_keeps_rendering(monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr("workers.render.remotion_runtime.sys.stdout", None)
        write_render_log("Rendered 1/30 ⚽")
