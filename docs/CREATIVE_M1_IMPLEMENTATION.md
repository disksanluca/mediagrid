# MediaGrid Creative M1 — fundação persistente

Data: **25/10/2026 (America/Sao_Paulo)**. Branch:
`codex/creative-m1-foundation`, criada da auditoria M0 `4916cf4`.
Escopo desta entrega: modelos, migração, lógica determinística, API e testes.
Nenhuma UI, composição Remotion, worker, render, IA remota ou publicação foi
alterada nesta etapa.

## Decisões e arquivos

| Arquivo | Decisão |
| --- | --- |
| `apps/api/creative/contracts.py` | Pydantic estrito, com versões `brief_v1`, `creative_dna_v1`, `directions_v1`, `storyboard_v1`; shots em milissegundos contíguos, IDs distintos e referências explícitas a assets/claims. |
| `apps/api/creative/director.py` | Três direções determinísticas, distintas, marcadas `deterministic_reference`; usam tópico, público, objetivo, tipografia e paleta do usuário, sem alegações factuais geradas. |
| `apps/api/creative/hashing.py`, `service.py` | Hash JSON canônico, revisões imutáveis, `expected_revision` e 409; dependências de brief, DNA, storyboard, direção, plano/EDL, marca do canal, direitos e claims recalculadas a cada leitura de review. |
| `apps/api/models.py`, `migrations/versions/0012_creative_direction.py` | Cinco tabelas aditivas ligadas a `Channel`/`Project`: DNA, brief, direction set, storyboard e review. Nenhuma coluna de EDL/projeto legado foi reescrita. |
| `apps/api/routes/creative.py`, `apps/api/main.py` | Router integrado sob `/api/v1`, protegido pela autenticação/origin middleware atual; sem segundo app FastAPI. |
| `tests/test_creative_m1.py`, `tests/test_migrations.py` | API, concorrência real entre duas requisições, reinício, invalidação, direitos/fatos e novo head. |
| `scripts/smoke_postgres_migrations.py`, `scripts/verify_postgres_restore.py` | Smoke PostgreSQL existente atualizado para head `0012` e presença das cinco tabelas. |

`CreativeReview` aprova **apenas o storyboard** (`APPROVED_STORYBOARD`). Esse
estado não aprova animatic, MP4, fatos para publicação ou postagem. O registro
de decisão é imutável; `GET review` devolve `STALE` se qualquer dependência
incluída no snapshot mudou. O hash atual é enviado como pré-condição da
decisão, com `expected_storyboard_revision` e `expected_revision` do review.
Uma colisão de escrita em `(owner_id, revision)` é capturada como HTTP 409.
Direções com os mesmos hashes de entrada são idempotentes. Revisar brief ou
DNA torna o conjunto anterior `STALE` até regenerar as propostas.

Assets referenciados precisam existir no registro; para aprovar, seus
metadados devem afirmar `OWNED` ou `LICENSED`, permitir uso comercial e, se
licenciados, nomear a licença. Alegações existentes do projeto precisam estar
`APPROVED`; um brief factual exige fontes marcadas como revisadas. Esses
campos são declarações e revisões do operador, não verificação independente
da veracidade ou dos direitos. O hash físico do arquivo é verificado pelo
pipeline existente antes de preview/render; M1 não autoriza produção pelo
estado criativo.

## Rotas criadas

Todas estão sob `/api/v1`. `GET` sem revisão retorna 404. Escritas usam JSON
estrito; payload inválido retorna 422 e revisão obsoleta, 409.

| Método e caminho | Função |
| --- | --- |
| `GET/PUT /channels/{channel_id}/creative-dna` | Ler/gravar DNA versionado. |
| `GET/PUT /projects/{project_id}/creative/brief` | Ler/gravar brief versionado. |
| `GET/POST /projects/{project_id}/creative/directions` | Ler/gerar três opções determinísticas com origem, hashes de entrada e status `CURRENT`/`STALE`. |
| `GET/PUT /projects/{project_id}/creative/storyboard` | Ler/gravar storyboard manual; exige direção atual e duração/FPS do brief. |
| `GET /projects/{project_id}/creative/review` | Consultar hash atual, bloqueios e validade da última decisão. |
| `POST /projects/{project_id}/creative/decision` | Registrar `APPROVE`, `REVISE` ou `REJECT` para a revisão e snapshot exatos. |

Não existe endpoint de animatic, aprovação de render nem conversão do
storyboard para uma segunda timeline. EDL v1/v2 e `GET /projects/{id}/preview`
continuam no fluxo existente.

## Migração, cópia e restauração

O único head inicial era `0011_music_draft_schedule`. A nova revisão é
`0012_creative_direction`, `down_revision=0011_music_draft_schedule`.
`alembic downgrade 0011` remove as cinco tabelas **somente se vazias**;
recusa downgrade que perderia dados criativos.

Foi usado exclusivamente o banco isolado criado na M0, já em `0011`, para
produzir `data/creative-m1-proof/before-0012.db`, `upgraded-0012.db` e
`restored-from-backup.db`. `sqlite3.Connection.backup` criou as cópias; a
migração foi executada em ambas as cópias de destino com
`python -m apps.api.migrate`. Ambas terminaram em `0012`, 21 tabelas e
`PRAGMA quick_check=ok`. O digest lógico das linhas originais em channels,
projects, jobs, assets, project_revisions e knowledge_claims permaneceu
`74c25b4ddcab0291b3d8b684cfbad7171128229f6fc509573b3a1309009f3c7c`.
Uma terceira cópia (`rollback-check.db`) foi rebaixada a `0011` e novamente
elevada a `0012`: respectivamente 16 e 21 tabelas, sempre `quick_check=ok`
e com o projeto legado preservado.
O banco instalado em `%LOCALAPPDATA%\MediaGrid` permaneceu em SHA-256
`D3A4268A84FC4271D6EBAB491A7D94C10081C680A51A23FA63E8393369EDBD21`.

## Validação realmente executada

| Comando | Resultado |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests` | **135 passed, 1 skipped**, 121,90 s na rodada final. Skip: Blender opt-in. |
| `.venv/Scripts/python.exe -m pytest -q tests/test_creative_m1.py tests/test_migrations.py` | **9 passed** na rodada final direcionada, incluindo recusa de downgrade, limites de entrada e mudança de formato. |
| `.venv/Scripts/python.exe -m ruff check .` | Passou. |
| `node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json` | Passou. |
| `node node_modules/typescript/bin/tsc --noEmit -p apps/renderer/tsconfig.json` | Passou. |
| `sqlite3.Connection.backup` + `python -m apps.api.migrate` em duas cópias | Passou, com quick_check e digest de dados legados idênticos. |
| `alembic downgrade 0011_music_draft_schedule` + `upgrade head` em terceira cópia | Passou, preservando projeto legado e integridade SQLite. |

As quatro provas REST incluem duas gravações simultâneas para a mesma revisão:
uma gravou e a outra recebeu 409; criação até aprovação com novo TestClient
(novo lifespan), edição de uma palavra gerando `STALE`, mudança de plano,
mudança de DNA, direitos `UNKNOWN`, fontes sem revisão e claim pendente.

## Estado de integração e limitações

- **REAL local:** FastAPI, SQLite, Pydantic, SQLAlchemy e revisão de metadados;
  as rotas persistem e foram testadas. Nenhuma API paga foi chamada.
- **PostgreSQL:** DDL/migração preparados e scripts de CI atualizados; o host
  local não dispõe de `psql`/Docker. O resultado do smoke PostgreSQL desta
  branch deve ser registrado após executar a CI em banco descartável.
- **PAPER/MOCK:** composição do animatic, UI do diretor e geração por LLM
  não foram integradas. O algoritmo determinístico é real e identificado
  como referência, não como IA ou parecer editorial.
- **Revisão humana:** `actor` é um nome declarado pelo operador autenticado
  no modo de conta única. Auditoria de identidade multiusuário/owner não
  está implementada no MediaGrid atual. O check de fonte/direitos é uma
  declaração humana; não há validação externa automática.
- **Instalação do usuário:** ainda versão 0.1.0, sem esta atualização. Não houve
  merge, deploy, VPS nem alteração de dados reais.

## Como verificar e preparar M2

Em banco **descartável**, configurar `DATABASE_URL` e `MEDIAGRID_DATA_DIR`,
executar `python -m apps.api.migrate` e iniciar a API normalmente. Criar
Channel e Project pelas rotas existentes; salvar DNA e brief com
`expected_revision: 0`, gerar direções, salvar storyboard e consultar
`creative/review` para obter o hash requerido na decisão. Toda atualização
subsequente precisa da revisão retornada pelo `GET` correspondente.

M2 poderá construir a UI de comparação/edição em cima dessas rotas e do
cliente API existente, sem tocar ainda em Remotion. Antes de qualquer status
de animatic aprovado ou exportação, serão necessários composição real,
verificação de mídia, QA audiovisual e integração explícita ao EDL v2.
