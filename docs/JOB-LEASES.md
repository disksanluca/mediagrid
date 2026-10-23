# Lease local de jobs — etapa do Marco 10

Esta etapa conserva a fila SQLite do desktop e prepara a transição para uma
fila PostgreSQL. Não oferece ainda worker remoto ou VPS utilizável.

- Migração `0009_job_leases` acrescenta `lease_owner`, `lease_expires_at` e
  `heartbeat_at` nullable em `jobs`, sem reescrever payload/result nem alterar
  projetos. O bootstrap de banco novo cria o schema atual e carimba o head;
  o upgrade de cópia legada cria as colunas por Alembic e preserva o EDL v1.
- `RENDER` e os jobs de mídia usam o mesmo claim transacional, ordenado por
  prioridade/criação, seguido de `UPDATE` condicional sobre o estado `QUEUED`.
  PostgreSQL recebe `FOR UPDATE SKIP LOCKED`, conforme
  [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update).
  SQLite ignora esse lock; o `UPDATE` impede um segundo claim do mesmo estado,
  mas o desktop ainda opera com um worker local e não foi testado entre hosts.
- Cada claim recebe token novo associado ao processo, início, heartbeat e lease de cinco
  minutos. Uma thread daemon renova o lease a cada 30 segundos durante
  subprocessos longos. Renovação só ocorre para o mesmo proprietário, job
  `RUNNING` e lease ainda válido. Na inicialização, apenas jobs sem lease
  legado ou com lease expirado são reencaminhados, respeitando `max_attempts`.
- Antes do commit final, o worker faz atualização condicional pelo token, status
  e prazo da lease na mesma transação. Se outro claim assumiu o job, descarta as
  alterações de estado e evento da transação antiga. O arquivo de render pode
  ter sido gravado antes desse fence; reconciliação de artefatos ainda é
  necessária para operação remota segura.
- Os testes cobrem claim distinto por dois workers, rejeição de renovação por
  proprietário errado, heartbeat real, recuperação seletiva e migração
  SQLite de base legada e nova, inclusive rejeição de conclusão após reclaim.
  PostgreSQL real e concorrência entre hosts
  seguem pendentes porque nenhum servidor PostgreSQL foi disponibilizado.

Ainda faltam idempotency key persistida, token de dispositivo, escopo por dono,
cancelamento do subprocesso, reconciliação de artefato após lease perdido e
prova ponta a ponta com worker Windows conectado de saída. Não promover este
marco como web funcional até esses contratos passarem no PostgreSQL real.
