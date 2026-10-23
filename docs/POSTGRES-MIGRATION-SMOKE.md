# PostgreSQL em CI — migrações e claim, sem VPS

O workflow `postgres-migration.yml` inicia PostgreSQL 16 somente durante o
job Ubuntu do GitHub Actions. Ele não cria servidor permanente, expõe API ou
usa dados do usuário. O script recusa qualquer banco que não seja
`postgresql+psycopg` em `localhost`/`127.0.0.1`, banco `mediagrid_ci`, com
`MEDIAGRID_ALLOW_EPHEMERAL_PG_SMOKE=1`. Ele também exige schema vazio.

A prova cria o schema atual numa base descartável, grava canal, projeto e job
sintéticos, volta a Alembic `0001_legacy` e avança até `0009_job_leases`.
Confere que os dados baseline sobrevivem, que as colunas de lease aparecem,
que um segundo claim não rouba a linha bloqueada por `FOR UPDATE SKIP LOCKED`,
e que heartbeat e conclusão condicional funcionam em PostgreSQL.

O runtime local consultado em 23/10/2026 tem SQLAlchemy 2.1.3, psycopg 3.3.6
e Alembic 1.20.0; o CI instala versões fixadas por `uv.lock`. O formato
`postgresql+psycopg://...` segue a [documentação oficial do dialeto](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
O serviço PostgreSQL no runner Linux segue a
[documentação oficial do GitHub Actions](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers).

Isto não testa backup/restauração de um banco com assets, migração de uma base
real do usuário, autenticação por proprietário, worker remoto, transporte de
mídia ou VPS. Esses gates permanecem necessários antes de oferecer modo web.
O teste local `tests/test_postgres_smoke_guard.py` verifica a proteção do
alvo; a execução PostgreSQL verdadeira deve ser confirmada pelo CI da branch.
