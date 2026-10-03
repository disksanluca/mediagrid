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

SQLite is supported for zero-friction single-user development. PostgreSQL is the deployment
database and the job reservation implementation uses `FOR UPDATE SKIP LOCKED` there.

