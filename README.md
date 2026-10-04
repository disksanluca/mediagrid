# MediaGrid

MediaGrid is a content production panel for multiple channels. You can create channels and
projects, edit a five-scene plan, render a text-based MP4, and download it for review.
Public mode includes an administrator password. The logo in the panel is an original SVG
inspired by the visual reference supplied for MediaGrid.

The first pilots are YouTube Football, TikTok Geography and Instagram Music. The core stays
independent of niches: niches are engines, platforms are connectors, and visual styles are
template packs.

The current renderer uses text cards. Narration text is stored in the plan but is not yet
voiced in the video. Research, fact verification, licensed asset sourcing, and direct
publishing to YouTube, TikTok, or Instagram are not connected yet.

For public deployment with PostgreSQL and HTTPS, see [deploy/README.md](deploy/README.md).
The [Oracle Always Free guide](deploy/FREE-ORACLE.md) avoids a paid server when a free
instance is available.

## Start locally

```bash
cp .env.example .env
./scripts/bootstrap.sh
./scripts/dev.sh
```

Open the web app at `http://localhost:3000`. The API documentation is available at
`http://localhost:8000/docs`.

The default local database is SQLite so a new machine can start without infrastructure.
Set `DATABASE_URL=postgresql+psycopg://mediagrid:mediagrid@localhost:5432/mediagrid` to use
PostgreSQL, which is the deployment database.

## Principles

- Local services are the default; paid AI is opt-in and disabled by default.
- AI produces validated plans. Deterministic renderers produce media.
- Every external publisher defaults to dry-run.
- Assets retain rights metadata; unknown or restricted assets require review.
- Work is persisted as observable, retryable jobs.
