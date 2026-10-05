# Architecture

The control panel calls the versioned FastAPI core. SQLAlchemy persists channels, projects,
assets, jobs and audit events. Engines supply niche-specific editorial behavior through a
shared contract. Platform connectors expose capabilities and connection state. Content
creation produces a validated Content Plan, Scene Plan and Edit Decision List before the
renderer receives any work.

```text
Web -> Core API -> Database
                  |      |
                Jobs   Storage
                  |
        Engines -> Pipeline -> Renderer -> QC -> Review -> Connectors
```

V1 runs as a single-user Windows application on loopback. The Next.js panel proxies to
FastAPI on `127.0.0.1`; SQLite, the worker, library, FFmpeg, Windows speech services and
optional Ollama/whisper.cpp models are all local. The worker performs automatic daily SQLite
backups. No external infrastructure is required. The API and storage abstractions allow a
future server migration, including PostgreSQL, as a separate phase.
