# Creative M0 — congelamento e auditoria da base

Data da auditoria: **25/10/2026 (America/Sao_Paulo)**. Este documento registra
somente o estado observado. Nenhum componente do M1 foi implementado.

## Fontes e limite desta auditoria

Foram lidos `README.md`, `ARCHITECTURE.md`, o código atual, as migrações,
`MediaGrid_SRS_Completo_v3.md` e `MediaGrid_Codex_Execute_M0_v3.txt` fornecidos
separadamente em Downloads. Após a primeira redação da auditoria, o usuário
enviou `MediaGrid_Kit_v3_REENVIO.zip` (SHA-256
`B934E86CE191DFE19D084C8E1806B972362B9777263B10F0EE30A5CFA7BD4FF1`).
O `MANIFEST.sha256` interno confere para **70/70 arquivos**. Foram lidos,
na ordem solicitada, `START_HERE.md`, `srs/SRS_MASTER.md`,
`architecture/CURRENT_VS_TARGET.md`, `integration/EXACT_FILES_AND_ROUTES.md`
e `prompts/00_FREEZE_AND_BASELINE.txt`; também a matriz de aceite, o plano
de migração, dependências/licenças e o snapshot GitHub. O ZIP menor
`MediaGrid_M0_Auditoria_Leitura.zip` (SHA-256
`EBF719FDA29DEDD8AE7A345C88F8BE44411A42910FB117650CD16B68D0572118`)
tem oito arquivos, todos idênticos aos correspondentes no kit completo. Os
arquivos avulsos `MediaGrid_v3_START_HERE.md` e `MediaGrid_v3_M0_Prompt.txt`
também são idênticos aos respectivos arquivos do kit. Os anexos são
especificações e código de referência isolado, não recursos integrados nem
instruções para expandir esta rodada além da M0.

## Git e instalação congelados

| Item | Estado verificado |
| --- | --- |
| Remoto | `origin = https://github.com/disksanluca/mediagrid.git` |
| Branch de código auditada | `feat/rea-scheduled-music-drafts`, HEAD `69185e81175a5848364a1a9549d9cb20b8ed4ece`; `origin` aponta ao mesmo SHA |
| Branch desta documentação | `codex/creative-m0-baseline`, criada a partir do HEAD acima, sem alterar a branch do PR existente |
| Principal | `main`/`origin/main` em `7dcc7d7b06691ded644f8b13bdc042779ff724c6`; HEAD auditado está 77 commits à frente, em cadeia de branches ainda não integrada |
| Referência no kit/TXT M0 | PR #26 / `feat/rea-voice-audio-hash` está defasada; a branch existe em `a1b43c9`, mas não é o HEAD atual |
| Árvore antes da documentação | Limpa; nenhum arquivo de código alterado nesta auditoria |
| CI do HEAD auditado | [PostgreSQL migration smoke](https://github.com/disksanluca/mediagrid/actions/runs/40048375652) e [Windows desktop build](https://github.com/disksanluca/mediagrid/actions/runs/40048375653) concluíram com sucesso; o job Windows incluiu smoke do aplicativo instalado no runner descartável |

A instalação principal registrada no Windows é **MediaGrid 0.1.0**; os binários
em `%LOCALAPPDATA%\MediaGrid` datam de 05/10/2026. Ela não foi atualizada. Seu
SQLite está em `%LOCALAPPDATA%\MediaGrid\Data\Database\mediagrid.db`, ainda
com as seis tabelas legadas e sem `alembic_version`. No momento da leitura:
3 canais, 1 projeto, 0 assets e 1 job. `PRAGMA quick_check` retornou `ok`.
Nenhuma consulta gravou nesse banco. Seu SHA-256 antes e depois da prova de
migração foi idêntico.

## Arquitetura real no HEAD

- **Desktop:** Tauri 2 inicia um sidecar Python FastAPI e o worker local, com
  frontend Next/React embutido e SQLite em pasta de dados do aplicativo.
  `apps/desktop/src-tauri/src/service_manager.rs` escolhe e conserva essa pasta;
  `tauri.conf.json` empacota runtime e instalador NSIS. A instalação do usuário
  continua antiga; CI Windows testa a branch nova em ambiente descartável.
- **Core e dados:** `apps/api/main.py` registra rotas versionadas `/api/v1` e
  executa a migração na inicialização. `apps/api/models.py` já contém canais,
  projetos, revisões EDL, assets, uploads, transcrições, cortes, sequências de
  futebol, alegações, jobs, eventos, 3D e agendamentos musicais. Alembic vai de
  `0001_legacy_baseline` a `0011_music_draft_schedule`. PostgreSQL é exercitado
  em CI; modo servidor está marcado experimental e requer configuração própria.
- **Editor/render:** `apps/api/edl_v2.py` valida trilhas e alguns presets
  delimitados; `GET/PUT /projects/{id}/edl-v2` usa revisão e recusa conflito.
  `GET /projects/{id}/preview` prepara props para o Player; o mesmo conjunto
  Remotion é usado no render local. `workers/render/main.py` usa jobs com lease,
  hash e FFprobe; voz Windows e FFmpeg geram MP4. Há revisão factual/direitos e
  exportação manual, distinta do render técnico.
- **Modos existentes:** cortes de fala, Football Edit manual, Motion Ad por
  briefing, alegações/explicadores de Geo/Política/Trends, diálogos 2D e
  narrativa 3D opcional. A documentação existente e testes mostram recortes
  técnicos, sem certificar qualidade artística de todos os modos ou material
  publicável. O `README.md` ainda descreve o limite de cartões/texto.

## Diferenças entre o kit v3 e o código real

| SRS | Estado no HEAD | Diferença para o M1 criativo |
| --- | --- | --- |
| FR-001, FR-006, FR-019, FR-021 | **Parcialmente implementado:** EDL v1/v2, `project_revisions`, `409`, leases e backups; migração de cópia legada passou nesta auditoria | Fixar teste de compatibilidade e restauração como gate do novo fluxo, sem segunda timeline |
| FR-002 `CreativeBrief` | **Ausente como contrato persistido próprio:** projetos guardam `topic`/`plan`; Motion Ad tem briefing específico | Definir schema versionado, migração e CRUD sem quebrar briefs/projetos anteriores |
| FR-003 `CreativeDNA` | **Parcial:** `Channel.brand_profile` e `editorial_profile` são JSON sem versão do contrato proposto | Versionar DNA por canal, defaults explícitos e regras negativas; mapear dados legados |
| FR-004 três direções | **Ausente:** nenhum `CreativeDirection` ou seleção persistida | Gerar três opções reais e distintas com justificativa e proveniência; marcar algoritmo determinístico inicial |
| FR-005 storyboard criativo geral | **Ausente:** há cenas/EDL e storyboard próprio do 3D | Persistir shots em ms inteiros e edição concorrente ligada à revisão do projeto |
| FR-007 animatic do storyboard | **Parcial:** Player/Remotion já compartilham props de cenas e EDL | Ligar o storyboard aprovado à composição e ao MP4, sem prévia ilustrativa separada |
| FR-008–009 revisão criativa exata e invalidação | **Ausente como gate geral:** revisão final do MP4, alegações, Football e blocking 3D têm aprovações específicas | Registrar hash de storyboard/animatic e revogar a aprovação quando qualquer dependência mudar |
| FR-010–011 `MotionPreset` / `sports_reveal_v1` | **Ausente:** EDL aceita `kinetic_title_v1`, `motion_card_v1`, `flow_path_v1` e `character_dialogue_v1`; não há registry de preset esportivo | Novo preset deve usar a timeline existente e renderizar prova 12 s 9:16 com áudio, preview e FFprobe |
| FR-012–015 editor, cortes, fontes, reuse | **Parcial:** edição EDL, clips, alegações e alguns motions já funcionam; não há Library de motions aprovados nem Content Brain com evidência/uncertainty completa | Integrar incrementalmente após o núcleo M1, sem apresentar recomendação como decisão editorial |
| FR-017–018 autopilot/publisher | **Parcial/futuro:** agendamento local de rascunho Música existe, `DRY_RUN=true`; postagem externa não está ativa | Não incluir em M1 nem ativar publicação/serviço pago |
| FR-020, FR-023 qualidade/status | **Parcial:** `QC` significa MP4 pronto para conferência e há bloqueio de exportação; não existe registry transversal `CONCEPT/BETA/READY/BLOCKED` com prova | Separar status técnico de aprovação artística antes de qualquer rótulo READY |
| FR-024 direitos | **Implementado em parte:** assets guardam hash, origem e licença; seleção de mídia sem direitos é bloqueada | O novo briefing e storyboard devem referenciar assets existentes por ID/hash |

O kit foi escrito para `a1b43c9` (PR #26), com Alembic em `0009_job_leases`.
O checkout auditado está em `69185e8`, com `0010_geo_claim_source_dates` e
`0011_music_draft_schedule` já aplicáveis. Por isso, o arquivo
`integration/0010_creative_direction_REFERENCE.py` **não pode** ser copiado
como a próxima migração: seu número/parent conflitaria com a história real.
Uma futura migração criativa deve partir de `0011`, em novo ID, após rever o
schema atual. `apps/api/routes/creative.py`, `apps/api/creative/` e
`apps/web/components/creative/` são caminhos **propostos** pelo kit; não
existem nesta branch. As rotas criativas listadas em
`integration/EXACT_FILES_AND_ROUTES.md` também ainda não existem. O router
atual é registrado em `apps/api/main.py` sob `/api/v1`; as rotas reais
`GET/PUT /projects/{id}/edl-v2` e `GET /projects/{id}/preview` vivem em
`apps/api/routes/projects.py`. M1 deve integrá-las sem criar outro app ou
timeline.

O kit propõe serviço SQLAlchemy no lugar de seu `SandboxCreativeService`,
revisões imutáveis de brief/DNA/storyboard, `expected_revision`/409,
invalidação por hash e aprovação de animatic exato. Nada disso foi importado
do código de referência. Os modelos, schemas JSON, UI e Remotion do ZIP são
exemplos isolados; o próprio `VALIDATION_REPORT.md` informa que o typecheck
completo, o MP4 12 s, a paridade Player/render e a revisão audiovisual desse
protótipo ainda não foram demonstrados. A prova de 31 s abaixo verifica o
pipeline **existente**, não os novos critérios QA-02/03/08/09/10 do kit.

## Versões e dependências observadas

No ambiente de desenvolvimento: Python **3.12.10**, `uv` **0.13.0**,
FastAPI **0.142.2**, Starlette **1.7.0**, SQLAlchemy **2.1.3**, Alembic
**1.20.0**, Pydantic **2.13.5**, httpx **0.28.1**, psycopg **3.3.6**,
faster-whisper **1.2.1**, pytest **8.4.2**, Ruff **0.16.10**, Node **24.19.0**,
Next **16.3.8**, React **19.3.0**, Remotion **4.0.532**, TypeScript **5.9.3**,
Tauri CLI **2.12.1** e FFmpeg/FFprobe do PATH **9.0.2**. `npm`, `cargo`,
`rustc` e `blender` não foram encontrados no PATH desta sessão; a CI Windows
instala Node/Rust para o build. O Blender não foi executado neste M0. O
`pyproject.toml`, `uv.lock`, `package-lock.json` e `Cargo.lock` existem.
Os intervalos em `pyproject.toml`/Cargo podem diferir das versões efetivamente
instaladas; não foram atualizados.

O kit aponta conflito potencial de versões Remotion. Ele se confirma nos
manifestos: `apps/renderer/package.json` declara `^4.0.365`, enquanto
`apps/web/package.json` fixa `4.0.532`; o `package-lock.json` resolve
`remotion` e `@remotion/cli` para **4.0.532**. Nenhuma dependência foi alterada
na M0. Antes de integrar a composição do kit, M1 deve fixar a versão e revisar
licença/uso oficial vigente, sem atualização ampla automática. Não foi feita
mudança em API, protocolo, licença ou provedor externo nesta rodada.

## Testes e prova executados nesta rodada

| Comando/prova | Resultado |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest -q tests` | **129 passed, 1 skipped**, em 134,77 s; skip é Blender opt-in |
| `.venv\Scripts\python.exe -m ruff check .` | Passou |
| `node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json` | Passou |
| `node node_modules/typescript/bin/tsc --noEmit -p apps/renderer/tsconfig.json` | Passou |
| `node node_modules/next/dist/bin/next build apps/web` | Passou, Next 16.3.8, rota `/` estática |
| `scripts/prove_video_pipeline.py` | Jobs VOICE/RENDER `SUCCEEDED`; MP4 H.264/AAC 1080×1920 de 31,0 s, SHA-256 `2c0b0a85a733a25293716c9610555abccea4816fa2717987ea91f3558e620a48`; `data/rea-proof/20261025T093648Z` |
| Mesmo script com `--edl-v2-roundtrip` | Revisão EDL v2 `2` persistida; jobs passaram; MP4 com mesmo SHA-256 e duração; `data/rea-proof/20261025T093811Z` |
| Migração da **cópia** do SQLite instalado | `apps.api.migrate` chegou a `0011`; 16 tabelas; `quick_check=ok`; IDs/contagens originais preservados; backup pré-migração criado em `data/creative-m0-proof`; banco instalado não mudou |
| Backup e restore da **cópia isolada** já migrada | `sqlite3.Connection.backup` para `data/creative-m0-proof/backups/m0-isolated-backup.db` e restauração para `m0-isolated-restored.db`; os três bancos deram `quick_check=ok`, 16 tabelas e mesmo SHA-256 do dump lógico `e48aa827614e543bc564c06909f641571d830e3826dd616708e8dc3700358eef` |

As provas de MP4 confirmam pipeline e compatibilidade para o caso sintético.
Não houve escuta integral ou aprovação estética nesta rodada. Nenhum teste
alterou a instalação principal. O banco de testes `data/mediagrid-test.db`
estava sem tabelas antes da suíte. Custo de API paga: zero; energia/CPU não
foram convertidas em valor financeiro não medido.

### Leitura dos critérios de aceite do kit

| Critério | Estado nesta M0 |
| --- | --- |
| QA-06 EDL legado e QA-13 backup | **Parcial:** migração de cópia 0.1.0, EDL v2 roundtrip e restore lógico passaram. Falta teste de restore de assets e comparação de hash de revisões antigas; o banco instalado tem 0 assets e 0 `project_revisions`. |
| QA-07 TS/Windows e QA-11 instalador | **Parcial:** typecheck/build do produto e CI Windows no runner passaram; o protótipo Remotion do kit não foi integrado, typechecked ou instalado no PC do usuário. |
| QA-08/09/10 novo MP4 12 s, paridade e qualidade | **Pendente:** só há prova técnica do render existente de 31 s. Sem prova audiovisual ou aprovação humana para a nova direção criativa. |
| QA-01–05, QA-12, QA-15–16 criativo, crash e segurança novos | **Pendente:** exigem implementação, testes específicos e revisão em marcos seguintes. O resultado `8 passed` informado pelo kit para seu código isolado não foi contado como teste do MediaGrid integrado. |
| QA-14 custos/publicação | **Passou como restrição M0:** nenhum provedor pago, deploy ou publicação foi ativado; custos financeiros de CPU/disco não foram medidos. |

## Entrada segura para M1 — **não iniciada**

1. Criar **somente numa rodada de M1 autorizada** a branch proposta
   `codex/creative-m1-foundation` a partir de
   `feat/rea-scheduled-music-drafts@69185e81175a5848364a1a9549d9cb20b8ed4ece`
   (ou revalidar seu novo HEAD antes de criá-la). Não construir sobre a
   migração `0010` de referência do kit nem mexer na cadeia de PRs existente.
2. Definir migração aditiva posterior a `0011` para
   brief/DNA/direções/storyboard/aprovação sem
   alterar `projects.id`, EDL v1, `project_revisions` ou bancos já instalados;
   provar upgrade/rollback em cópia, inclusive com projeto legado e assets.
3. Fazer primeiro o corte M1 de modelos/DB/API autenticada, concorrência 409,
   reinício e testes; em marcos seguintes, conectar UI, animatic/worker,
   revisão e preset no EDL v2, seguindo a ordem dos prompts do kit. O escopo
   vertical de cada entrega só será considerado READY após prova de ponta a
   ponta pertinente; não anunciar qualidade artística sem revisão humana.
4. Registrar material licenciado ainda não fornecido, Blender opcional,
   servidor/VPS experimental e instalação principal antiga como limites. Para
   política no Instagram sem fontes, nenhum fato deve ser fabricado ou
   publicado sem fonte e aprovação editorial.

**Estado M0: PASS para auditoria e freeze, com limites explícitos acima.** O
kit foi conciliado com o checkout real; as provas técnicas existentes não
equivalem a aceitação de vídeo novo nem a software 100% pronto. M1 não foi
iniciado. Nenhum merge, upgrade do banco do usuário, instalação, VPS,
cobrança ou publicação foi executado.
