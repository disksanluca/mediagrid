import hashlib
import json
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from .config import get_settings

ROOT = Path(__file__).resolve().parents[2]


def narration_text(script: dict | None) -> str:
    return " ".join((script or {}).get("segments", []))


def voice_matches(project_id: str, script: dict | None) -> bool:
    directory = get_settings().mediagrid_data_dir / "voice"
    audio = directory / f"{project_id}.wav"
    manifest = directory / f"{project_id}.sha256"
    expected = hashlib.sha256(narration_text(script).encode("utf-8")).hexdigest()
    if not audio.is_file() or not manifest.is_file():
        return False
    parts = manifest.read_text(encoding="utf-8").split()
    if not parts or parts[0] != expected:
        return False
    configuration = voice_choice()
    if len(parts) == 3 and parts[2] not in {"RECORDED", voice_configuration_digest()}:
        return False
    if len(parts) in {1, 2} and configuration != (None, 0):
        return False
    if len(parts) == 1:
        # Existing desktop data used a script-only digest. Keep it readable.
        return True
    if len(parts) not in {2, 3}:
        return False
    digest = hashlib.sha256()
    with audio.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == parts[1]


@lru_cache(maxsize=1)
def windows_speech_features() -> tuple[bool, bool]:
    if sys.platform != "win32" or not shutil.which("powershell.exe"):
        return False, False
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Add-Type -AssemblyName System.Speech; "
                "$v=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "try { Write-Output $v.GetInstalledVoices().Count } finally { $v.Dispose() }; "
                "try { Write-Output "
                "([System.Speech.Recognition.SpeechRecognitionEngine]::"
                "InstalledRecognizers().Count) "
                "} catch { Write-Output 0 }",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        counts = [
            int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()
        ]
        return len(counts) >= 2 and counts[0] > 0, len(counts) >= 2 and counts[1] > 0
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False, False


def voice_available() -> bool:
    selected, _ = voice_choice()
    voices = installed_portuguese_voices()
    return bool(voices) and (selected is None or selected in voices)


@lru_cache(maxsize=1)
def installed_portuguese_voices() -> tuple[str, ...]:
    if sys.platform != "win32" or not shutil.which("powershell.exe"):
        return ()
    try:
        result = subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "try { $s.GetInstalledVoices() | Where-Object { "
            "$_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | "
            "ForEach-Object { $_.VoiceInfo.Name } } finally { $s.Dispose() }",
        ], check=True, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ()
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def voice_choice() -> tuple[str | None, int]:
    path = get_settings().mediagrid_data_dir / "settings.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, 0
    if not isinstance(saved, dict):
        return None, 0
    voice = saved.get("voice_name")
    rate = saved.get("voice_rate", 0)
    if not isinstance(voice, str) or not voice:
        voice = None
    if type(rate) is not int or not -5 <= rate <= 5:
        rate = 0
    return voice, rate


def voice_configuration_digest() -> str:
    voice, rate = voice_choice()
    value = json.dumps({"voice": voice, "rate": rate}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def transcription_available() -> bool:
    settings = get_settings()
    whisper = shutil.which(settings.whisper_cli_path) or Path(settings.whisper_cli_path).is_file()
    if whisper and settings.whisper_model_path and settings.whisper_model_path.is_file():
        return True
    return windows_speech_features()[1]


def synthesize_voice(text: str, output: Path) -> None:
    if not voice_available():
        raise RuntimeError("Windows speech synthesis is unavailable")
    output.parent.mkdir(parents=True, exist_ok=True)
    source = output.with_suffix(".txt")
    source.write_text(text, encoding="utf-8")
    selected, rate = voice_choice()
    try:
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts" / "speak.ps1"),
                str(source),
                str(output),
                "-VoiceName",
                selected or "",
                "-Rate",
                str(rate),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("Speech synthesis produced no audio")
    finally:
        source.unlink(missing_ok=True)


def transcribe_media(source: Path, output: Path) -> None:
    if not transcription_available():
        raise RuntimeError(
            "Install whisper.cpp with a local model or a Windows speech language pack"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    wav = output.with_suffix(".input.wav")
    try:
        ffmpeg = get_settings().mediagrid_ffmpeg_path or "ffmpeg"
        subprocess.run(
            [str(ffmpeg), "-y", "-i", str(source), "-ac", "1", "-ar", "16000", str(wav)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        settings = get_settings()
        whisper = shutil.which(settings.whisper_cli_path) or (
            str(settings.whisper_cli_path) if Path(settings.whisper_cli_path).is_file() else None
        )
        if whisper and settings.whisper_model_path and settings.whisper_model_path.is_file():
            prefix = str(output.with_suffix(""))
            subprocess.run(
                [
                    whisper,
                    "-m",
                    str(settings.whisper_model_path),
                    "-f",
                    str(wav),
                    "-otxt",
                    "-of",
                    prefix,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
        else:
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "scripts" / "transcribe.ps1"),
                    str(wav),
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
        if not output.is_file():
            raise RuntimeError("Transcription produced no text")
    finally:
        wav.unlink(missing_ok=True)
