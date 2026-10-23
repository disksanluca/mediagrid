# Web/VPS sem GPU — auditoria de prontidão

Estado: **não implantável como produto web**. Esta branch inicia o Marco 10 com
um bloqueio de configuração explícito; ela não afirma que a fila remota ou a
autorização por recurso já funcionam. O desktop local continua em SQLite.

## O que existe

- FastAPI e Next compartilham a interface com o desktop. A API possui sessão
  de administrador e bloqueio de origem; isso é uma única conta, sem
  `owner_id` ou tenant por canal/projeto/asset.
- SQLAlchemy já aceita URL PostgreSQL e `psycopg[binary]>=3.2,<4` consta das
  dependências. As migrações Alembic foram verificadas até a revisão 0008 no
  SQLite. Não há PostgreSQL ou VPS disponível para teste de upgrade/backup.
- A fila atual usa a tabela `jobs` e `FOR UPDATE SKIP LOCKED` na consulta de
  claim. Não há lease, heartbeat, cancelamento de subprocesso remoto, token
  revogável de dispositivo nem transporte de artefatos/inputs. Os arquivos
  estão no disco local do host da API; o desktop não pode acessá-los de forma
  autenticada por saída.
- O worker local agora recusa modo não local. No modo servidor a API só inicia
  com credenciais, URL pública HTTPS, PostgreSQL explícito, `DRY_RUN=true` e
  IA paga desligada. A chave `MEDIAGRID_SERVER_EXPERIMENTAL=true` ainda é
  exigida para testes isolados; o padrão é falhar antes da migração. Isso evita
  executar um worker de mídia no VPS sem GPU ou expor o protótipo por acidente.

## Contrato necessário antes de um VPS

1. Autorizar cada rota e arquivo por proprietário. Migrar canais, projetos,
   assets, revisões e jobs com `owner_id` e testar acesso cruzado negado.
2. Migrar e testar PostgreSQL real, inclusive rollback e backup restaurável.
   Usar URL `postgresql+psycopg://...` conforme a
   [documentação oficial do dialeto](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
3. Registrar worker desktop com token revogável e capacidades. Claim atômico
   por capacidade com lease/heartbeat e idempotência; sem worker compatível,
   estado `WAITING_FOR_WORKER` em vez de sucesso ou fila sem consumidor.
4. Expor somente manifestos tipados e assets autorizados por download curto,
   verificar SHA-256 no desktop, executar localmente, carregar resultado com
   hash/FFprobe e confirmar no servidor antes de `SUCCEEDED`. Não aceitar
   comandos shell remotos.
5. Testar ponta a ponta sem GPU no servidor e com worker Windows de saída,
   inclusive perda de conexão, retry, conflito de revisão, cancelamento,
   vazamento entre usuários e restauração de DB+assets.

Nenhum host, conta, custo mensal, domínio ou armazenamento externo foi
escolhido ou ativado. Esta etapa não altera publicação manual nem instala uma
nova versão no PC do usuário.

Validação local deste gate: `uv run pytest -q tests` (73 passed, 1 skipped;
Blender opt-in não configurado nesta rodada) e `uv run ruff check .` passaram.
Não foi executado teste PostgreSQL ou web end-to-end nesta etapa.
