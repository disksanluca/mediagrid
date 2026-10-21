# MediaGrid

O [plano e a auditoria do Atelier Premium v3](docs/ATELIER-PREMIUM-V3.md)
documentam a branch visual atual e seus limites funcionais.

MediaGrid V1 is being built as a local **Windows desktop application**. Tauri hosts the
React panel in its own window and starts the FastAPI Core and worker on the same computer.
See [DESKTOP-PLAN.md](DESKTOP-PLAN.md) for the delivery gates. The Windows CI installs the
desktop package and renders a short MP4 with video and audio. A hands-on check on a clean
Windows PC remains required before treating this as a finished V1. The localhost script
remains a development fallback.
The panel logo is an original SVG based on the supplied MediaGrid visual reference.

The first pilots are YouTube Football, TikTok Geography and Instagram Music. The core stays
independent of niches: niches are engines, platforms are connectors, and visual styles are
template packs.

The renderer uses text cards or a selected local image/video behind the scene text. Windows offline speech synthesis can add narration to the MP4;
transcription uses Windows speech recognition or an optional local whisper.cpp model. The
Politics Radar can read public Câmara dos Deputados PL records with no account or API key.
Other research, fact verification, licensed asset sourcing, and direct publishing are still
manual.

## Creating a useful first script

Create a channel, then a project. In **Pauta / briefing**, enter three to five concrete
statements on separate lines (20–300 characters each). The local plan copies those statements
into editable scene narration without adding facts. Review and save the script in the Editor,
generate local voice if available, then render and review the MP4. A short topic instead
produces an editorial outline. Voice and render stay blocked until the narration of every
outline scene has been edited and saved.
The Editor identifies whether the plan came from the brief, an official source, local AI,
or manual edits. For a Politics channel, open **Radar**, search Câmara PLs by year and
optional ementa term, inspect the source link, and choose **Criar roteiro**. MediaGrid
fetches the selected PL again, stores the official source URL and retrieval time in the
project plan, and creates an editable vertical script from the identifier, ementa, and last
recorded status. The API is online and may be unavailable; the saved project remains local.
The source is evidence to review, not proof that a proposal became law. Check the current
tramitação, context, and media rights before approving the manual export. In **Biblioteca**,
import your own JPEG, PNG, WebP or MP4, or record its license; then choose it in each scene's
**Mídia da biblioteca** field in the Editor and save. Unknown/restricted rights block saving
or rendering. Licensed media needs a recorded license name. Selected MP4s are muted under
the narration and repeat if a scene is longer than the source clip. A rendered MP4 can be
reviewed and downloaded, then packaged for manual publication after human approval.
When a generated WAV lasts longer than the estimated scene times, the renderer extends the
video scenes to keep the full narration audible. Generating a new voice or render after review
invalidates the old approval until the new video is reviewed.

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
