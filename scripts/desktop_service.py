"""Entry point bundled by PyInstaller for the Tauri desktop application."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="MediaGrid local desktop services")
    parser.add_argument("service", choices=("api", "worker"))
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.service == "api":
        import uvicorn

        from apps.api.main import app

        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    else:
        from workers.render.main import main as worker_main

        worker_main()


if __name__ == "__main__":
    main()
