"""Entry point bundled by PyInstaller for the Tauri desktop application."""

import argparse
import json
import os
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="MediaGrid local desktop services")
    parser.add_argument("service", choices=("api", "worker", "backup", "restore"))
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--include-assets", action="store_true")
    parser.add_argument("--include-renders", action="store_true")
    parser.add_argument("--include-models", action="store_true")
    args = parser.parse_args()
    if args.service == "api":
        import uvicorn

        from apps.api.main import app

        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    elif args.service == "worker":
        from workers.render.main import main as worker_main

        worker_main([])
    else:
        from apps.api.backup import create_backup, restore_backup

        if args.path is None:
            parser.error("--path é obrigatório para backup e restauração")
        data_dir = Path(os.environ.get("MEDIAGRID_DATA_DIR", "./data"))
        try:
            if args.service == "backup":
                result = create_backup(
                    data_dir,
                    args.path,
                    include_assets=args.include_assets,
                    include_renders=args.include_renders,
                    include_models=args.include_models,
                )
                print(json.dumps({"files": len(result["files"]), "path": str(args.path)}))
            else:
                previous = restore_backup(data_dir, args.path)
                print(json.dumps({"previous": str(previous) if previous else None}))
        except (ValueError, OSError, zipfile.BadZipFile) as error:
            parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
