from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MediaGrid Core"
    mediagrid_mode: str = "LOCAL"
    mediagrid_local_web_port: int = Field(default=3000, ge=1, le=65535)
    mediagrid_server_experimental: bool = False
    allow_paid_ai: bool = False
    database_url: str = "sqlite:///./data/mediagrid.db"
    mediagrid_data_dir: Path = Path("./data")
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
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
