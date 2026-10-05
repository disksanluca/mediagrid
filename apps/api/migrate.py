from . import models  # noqa: F401
from .config import get_settings
from .database import Base, engine


def main() -> None:
    settings = get_settings()
    settings.mediagrid_data_dir.mkdir(parents=True, exist_ok=True)
    for directory in ("assets", "exports", "renders", "temp", "voice", "transcripts", "backups"):
        (settings.mediagrid_data_dir / directory).mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()
