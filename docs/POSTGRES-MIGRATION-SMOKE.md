# PostgreSQL em CI — migrações e claim, sem VPS

O workflow `postgres-migration.yml` inicia PostgreSQL 16 somente durante o
job Ubuntu do GitHub Actions. Ele não cria servidor permanente, expõe API ou
usa dados do usuário. O script de migração recusa qualquer banco que não seja
`postgresql+psycopg` em `localhost`/`127.0.0.1`, banco `mediagrid_ci`, com
`MEDIAGRID_ALLOW_EPHEMERAL_PG_SMOKE=1`. Ele também exige schema vazio. O
verificador de restauração aceita somente `mediagrid_restored` no mesmo host.

A prova cria o schema atual numa base descartável, grava canal, projeto e job
sintéticos, volta a Alembic `0001_legacy` e avança até `0009_job_leases`.
Confere que os dados baseline sobrevivem, que as colunas de lease aparecem,
que um segundo claim não rouba a linha bloqueada por `FOR UPDATE SKIP LOCKED`,
e que heartbeat e conclusão condicional funcionam em PostgreSQL.

Depois, o workflow usa o `pg_dump -Fc` do próprio contêiner para criar um dump
customizado. Restaura-o com `pg_restore --exit-on-error --no-owner` em
`mediagrid_restored`, outro banco vazio do mesmo serviço descartável. O
verificador exige o head Alembic, tabelas, canal, projeto e job concluído.
O SHA-256 do dump aparece no log do CI; o arquivo não é publicado como
artefato. Ver [pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
e [pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html).

O runtime local consultado em 23/10/2026 tem SQLAlchemy 2.1.3, psycopg 3.3.6
e Alembic 1.20.0; o CI instala versões fixadas por `uv.lock`. O formato
`postgresql+psycopg://...` segue a [documentação oficial do dialeto](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
O serviço PostgreSQL no runner Linux segue a
[documentação oficial do GitHub Actions](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers).

Isto testa backup/restauração somente do banco sintético; não inclui arquivos
de mídia, migração de uma base real do usuário, autenticação por proprietário,
worker remoto, transporte de mídia ou VPS. Esses gates permanecem necessários
antes de oferecer modo web.
O teste local `tests/test_postgres_smoke_guard.py` verifica a proteção do
alvo; a execução PostgreSQL verdadeira deve ser confirmada pelo CI da branch.
