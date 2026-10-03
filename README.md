# MediaGrid

MediaGrid is a local-first content operating system for researching, creating, reviewing,
rendering and publishing media across multiple brands and platforms.

The first pilots are YouTube Football, TikTok Geography and Instagram Music. The core stays
independent of niches: niches are engines, platforms are connectors, and visual styles are
template packs.

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

