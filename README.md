# MediaGrid

MediaGrid V1 is being built as a local **Windows desktop application**. Tauri hosts the
React panel in its own window and starts the FastAPI Core and worker on the same computer.
See [DESKTOP-PLAN.md](DESKTOP-PLAN.md) for the delivery gates. The desktop installer is not
yet validated on Windows; the existing localhost script remains a development fallback.
The panel logo is an original SVG based on the supplied MediaGrid visual reference.

The first pilots are YouTube Football, TikTok Geography and Instagram Music. The core stays
independent of niches: niches are engines, platforms are connectors, and visual styles are
template packs.

The renderer uses text cards. Windows offline speech synthesis can add narration to the MP4;
transcription uses Windows speech recognition or an optional local whisper.cpp model. Research,
fact verification, licensed asset sourcing, and direct publishing are still manual.

## Current development fallback on Windows

See [SETUP.md](SETUP.md) for installation and troubleshooting. On Windows, double-click
`Iniciar-MediaGrid.cmd`. Or, in PowerShell from the project folder:

```powershell
.\scripts\bootstrap.ps1
.\scripts\dev.ps1
```

Keep the PowerShell window open and visit **http://localhost:3000**. The API docs are at
**http://localhost:8000/docs**. Files and automatic daily SQLite backups live under `data/`.

## Other development systems

```bash
cp .env.example .env
./scripts/bootstrap.sh
./scripts/dev.sh
```

Open the web app at `http://localhost:3000`. The API documentation is available at
`http://localhost:8000/docs`.

The default database is SQLite. A future server migration may use PostgreSQL, but no VPS,
cloud service or account is required for V1. Paid AI and cloud integrations are off by default.

## Principles

- Local services are the default; paid AI is disabled by default.
- Ollama on localhost can improve narration in the plan; a built-in plan works without it.
- The worker renders media, generates local speech, transcribes locally and backs up SQLite.
- Every external publisher defaults to dry-run.
- Assets retain rights metadata; unknown or restricted assets require review.
- Work is persisted as observable, retryable jobs.
