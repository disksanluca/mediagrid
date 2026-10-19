from subprocess import CompletedProcess

from apps.api import local_media


def test_installed_voice_remains_available_without_speech_recognizer(monkeypatch) -> None:
    monkeypatch.setattr(local_media.sys, "platform", "win32")
    monkeypatch.setattr(local_media.shutil, "which", lambda name: "powershell.exe")
    monkeypatch.setattr(
        local_media.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args=[], returncode=0, stdout="2\n0\n"),
    )
    local_media.windows_speech_features.cache_clear()
    try:
        assert local_media.windows_speech_features() == (True, False)
    finally:
        local_media.windows_speech_features.cache_clear()
