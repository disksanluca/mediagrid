from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MediaGrid Core"
    mediagrid_mode: str = "LOCAL"
    mediagrid_server_experimental: bool = False
    allow_paid_ai: bool = False
    database_url: str = "sqlite:///./data/mediagrid.db"
    mediagrid_data_dir: Path = Path("./data")
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    mediagrid_agents_enabled: bool = False
    mediagrid_agents_model: str = "qwen3:4b-instruct"
    mediagrid_agents_min_free_ram_mb: int = Field(default=4096, ge=1024, le=32768)
    mediagrid_agents_min_free_vram_mb: int = Field(default=1800, ge=0, le=16384)
    mediagrid_tts_provider: str = "windows"
    mediagrid_kokoro_python: Path | None = None
    mediagrid_kokoro_model_dir: Path | None = None
    mediagrid_kokoro_voice: str = "pm_alex"
    mediagrid_kokoro_speed: float = Field(default=1.0, ge=0.75, le=1.35)
    mediagrid_kokoro_offline: bool = True
    whisper_model_path: Path | None = None
    mediagrid_asr_model_dir: Path | None = None
    whisper_cli_path: str = "whisper-cli"
    mediagrid_renderer_root: Path | None = None
    mediagrid_node_path: Path | None = None
    mediagrid_ffmpeg_path: Path | None = None
    mediagrid_ffprobe_path: Path | None = None
    mediagrid_browser_path: Path | None = None
    mediagrid_render_concurrency: int = Field(default=4, ge=1, le=16)
    mediagrid_blender_path: Path | None = None
    dry_run: bool = True
    mediagrid_admin_password: str | None = None
    mediagrid_session_secret: str | None = None
    mediagrid_public_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
