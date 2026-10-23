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
  alterações de estado e evento da transação antiga. O job `RENDER` escreve um
  MP4 temporário exclusivo por tentativa e só substitui o MP4 do projeto depois
  de passar esse fence. Render de legendas, cortes, Football Edit e narrativa 3D
  também usa tentativa exclusiva e promoção após o fence. Uma tentativa vencida
  apaga seu temporário. Falha na promoção marca o job como `FAILED`, sem devolver
  sucesso; no render do projeto também marca o projeto como `FAILED`.
- Se um computador Windows retomar após perder o lease durante Remotion, o
  artefato tardio continua descartado. Quando o loop do worker volta a ficar
  ocioso, ele recupera jobs expirados e os coloca novamente na fila, respeitando
  `max_attempts`. A prova Trends de 23/10/2026 observou uma tentativa vencida
  recusada e uma execução posterior bem-sucedida. O processo de Remotion limita
  concorrência a `MEDIAGRID_RENDER_CONCURRENCY` (padrão 4) e desativa codificação
  paralela; [opções oficiais](https://www.remotion.dev/docs/cli/render).
  Durante esse subprocesso, o Windows recebe um pedido temporário para evitar
  suspensão automática por ociosidade, limpo em `finally` conforme a
  [documentação da Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate).
- A voz local gera WAV e digest do roteiro em temporários exclusivos. O worker
  promove primeiro o WAV e depois o digest somente após o fence. Se o digest
  faltar, preserva o WAV anterior e falha o job. Uma queda entre as duas
  substituições pode deixar os arquivos desencontrados. O novo manifesto inclui
  hash do roteiro e do WAV; `voice_matches` rejeita áudio alterado. Manifestos
  antigos, que têm só o hash do roteiro, continuam legíveis por compatibilidade
  e não oferecem verificação do próprio WAV até que a voz seja regenerada.
- O proxy de ingestão gera MP4 e waveform em caminhos exclusivos, verifica seus
  hashes e só promove arquivos e metadados `READY` após o fence. O endpoint de
  download também confere o hash armazenado. Reclaim descarta temporários sem
  alterar o proxy anterior ou o estado do asset.
- A transcrição TXT legada usa arquivo temporário exclusivo e promove o texto
  somente após o fence. Uma tentativa vencida não troca a transcrição anterior.
- Os testes cobrem claim distinto por dois workers, rejeição de renovação por
  proprietário errado, heartbeat real, recuperação seletiva e migração
  SQLite de base legada e nova, inclusive rejeição de conclusão após reclaim.
  Também cobrem a preservação do MP4 anterior após reclaim para os cinco tipos
  de render, do TXT de transcrição e a falha de promoção do render principal.
  Para voz, cobrem reclaim e digest ausente sem sobrescrever o WAV anterior.
  Para proxy, cobrem reclaim
  sem sobrescrever o MP4 nem o estado de ingestão.
  A CI executa migração, concorrência de claim, dump e restore em PostgreSQL real
  com serviço temporário; concorrência entre hosts e worker remoto seguem sem prova.

Ainda faltam idempotency key persistida, token de dispositivo, escopo por dono,
cancelamento do subprocesso, reconciliação após queda entre promoção de arquivo
e commit SQL, e prova ponta a ponta com worker Windows conectado de saída. O rename do MP4 e o
commit do banco não formam uma transação atômica: uma queda nesse intervalo pode
deixar um arquivo novo sem estado terminal; falta recuperação/reconciliação para
esse caso. Não promover este marco como web funcional até fechar esses contratos.
