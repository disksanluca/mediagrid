# CREATIVE M0 — Freeze, baseline e plano seguro para M1

**Data:** 25/10/2026  
**Escopo:** somente auditoria/documentação. **Nenhum código, banco, VPS ou instalação do usuário foi alterado.**  
**Referência atual verificada na integração GitHub:** `disksanluca/mediagrid@69185e81175a5848364a1a9549d9cb20b8ed4ece`, branch `feat/rea-scheduled-music-drafts`, PR [#41](https://github.com/disksanluca/mediagrid/pull/41).  
**Fonte de requisitos:** `MediaGrid_Engineering_Implementation_Kit_v3.zip`, especialmente `START_HERE.md`, `srs/SRS_MASTER.md`, `architecture/CURRENT_VS_TARGET.md`, `integration/EXACT_FILES_AND_ROUTES.md`, `quality/ACCEPTANCE_TEST_MATRIX.md` e `prompts/00_FREEZE_AND_BASELINE.txt`.  
**Regra:** código real do HEAD + testes > suposições do kit. Materiais externos são benchmark funcional, não código-fonte do oDarkly.

## 1. Veredito executivo

**M0 DOCUMENTAL: PASS COM RESTRIÇÕES. M0 DE CHECKOUT/PC PESSOAL: PENDENTE. M1: NÃO AUTORIZADO / NÃO INICIADO.**

O kit v3 era baseado no PR #26 e revisão Alembic `0009_job_leases`. Há **quinze PRs posteriores (#27–#41)**, todos na mesma cadeia. Logo, **NÃO usar #26 como HEAD de implementação**, nem aplicar a migration de exemplo `0010_creative_direction_REFERENCE.py` com esse ID: o código vigente já usa `0010_geo_claim_source_dates` e `0011_music_draft_schedule`.

Nenhuma operação nesta auditoria tentou integrar o ZIP, instalar pacotes, iniciar M1, rodar modelos pagos, publicar conteúdo, fazer merge, implantar VPS ou modificar o SQLite do proprietário.

## 2. Estado Git e PRs — evidência remota

- Default branch: `main` (repositório público).
- PR #41: **OPEN / DRAFT / NÃO MERGED**. Head `feat/rea-scheduled-music-drafts` em `69185e81175a5848364a1a9549d9cb20b8ed4ece`; base `feat/rea-music-metadata` (PR #40).
- Listagem de PRs retornou **#1–#41 encadeados, abertos e em draft**. #1 tem base `main`; PRs seguintes partem do head do PR anterior. O conjunto ainda não foi incorporado à `main`.
- Comparação GitHub `main...feat/rea-scheduled-music-drafts`: **77 commits à frente, 0 atrás, 178 arquivos alterados**. São estatísticas do *diff acumulado*, não de um PR isolado.
- Esta auditoria é escrita em branch separada `docs/creative-m0-baseline-20261025`, criada diretamente do SHA do #41; não altera #41 e não move a `main`.
- **PENDENTE LOCAL:** `git status`, HEAD do checkout do Codex Desktop, branches locais, mudanças não commitadas, diferenças não enviadas ao GitHub e versão efetivamente instalada no PC. A integração GitHub não enxerga o Git de `C:\Users\...\work\mediagrid`.
- **PENDENTE LOCAL:** backup dos dados efetivos do usuário, path/versão do banco em uso, disco livre, restore de cópia real e validação da atualização da instalação 0.1.0.

### Desvio bloqueador entre o kit e o GitHub

| Premissa v3 | HEAD #41 observado | Ação antes de M1 |
|---|---|---|
| HEAD `feat/rea-voice-audio-hash` / PR #26 | `feat/rea-scheduled-music-drafts` / PR #41 | Rebasear *o plano*, não reescrever PRs |
| 53 commits / 141 arquivos | 77 commits / 178 arquivos | Atualizar baseline e matriz de conflitos |
| Alembic `0009_job_leases` | **`0011_music_draft_schedule`** | Próxima revisão criativa deve depender de `0011`; nome sugerido `0012_creative_direction`, após validar o grafo |
| Sem Motor de anúncio dedicado | `motion_ads` e `apps/api/motion_ad.py` existentes | Não duplicar brief/conversão de anúncios |
| Sem agendador musical | Agendamento local MusicBrainz com lease/cancelamento/retentativa | Aproveitar contratos; não chamar de Autopilot completo |
| Fonte geo sem revisão avançada | `0010_geo_claim_source_dates` + rastreio adicional | Preservar proveniência factual |
| Áudio apenas Windows TTS | Branches posteriores incluem voz gravada/escolha de voz | Integrar Creative Director sem recriar voz |
| 2D de um personagem | PRs #38–#39 adicionam segundo rig/dupla | Preservar overlays existentes |

## 3. CI, testes e execução disponíveis

| Verificação | Resultado | Evidência / limite |
|---|---|---|
| Kit v3: `python validate_kit.py` | **PASS** | Execução neste ambiente: 8 testes Python aprovados, 4 fixtures JSON validadas, WAV sintético 12 s |
| Kit: `PYTHONPATH=. python -m pytest -q tests` em `code/python` | **PASS (8/8)** | Código de referência isolado, NÃO integrado à API MediaGrid |
| Repositório HEAD #41: testes Python | **PASS via CI / relatório do PR** | PR reportou `129 passed, 1 skipped` (Blender opt-in); esta sessão não rodou a suíte completa no checkout Windows |
| Ruff / TypeScript / Next build | **PASS reportado pelo PR #41** | Não reexecutados localmente nesta sessão; verificar logs no checkout antes de M1 |
| CI Windows HEAD #41 | **PASS** | [Run 40048375653](https://github.com/disksanluca/mediagrid/actions/runs/40048375653): `npm ci`, testes locais, build Python, build Windows e smoke da aplicação instalada no runner concluídos |
| CI PostgreSQL HEAD #41 | **PASS** | [Run 40048375652](https://github.com/disksanluca/mediagrid/actions/runs/40048375652): migração, backup via dump, restore em segunda base descartável e verificação concluídos |
| Teste da instalação no PC do usuário | **NÃO EXECUTADO** | Runner descartável de CI não comprova atualização/UX real do PC |
| Backup/restore do SQLite real | **NÃO EXECUTADO** | Arquivo do usuário indisponível; CI PostgreSQL não substitui prova SQLite local |
| `git status` do Codex Desktop | **NÃO ACESSÍVEL** | Git remoto não informa alterações não commitadas |
| Remotion do kit / MP4 12 s / revisão artística | **PENDENTE** | Não houve npm build/render local do protótipo v3, nem audição, nem inspeção de MP4 final |
| Blender no host instalado | **PENDENTE** | Um teste opcional foi ignorado na suíte declarada |
| VPS / dois hosts / worker remoto | **NÃO EXECUTADO** | Modo servidor ainda experimental e com lacunas de isolamento/autenticação |
| Fetch/clone do Git neste ambiente | **BLOQUEADO** | `git ls-remote` não resolveu `github.com`; a inspeção remota usou o conector GitHub autenticado |

**Não converter `CI success` em `produção pronta`.** A saída MP4 técnica não prova direção de arte profissional nem licenças editoriais.

## 4. Estado existente x SRS v3

| SRS / recurso | Evidência em HEAD #41 | Estado para o novo escopo |
|---|---|---|
| FR-001: legado/EDL v1-v2 | `apps/api/edl_v2.py`, `ProjectRevision`, endpoints `GET/PUT /projects/{id}/edl-v2` e `GET /projects/{id}/preview` | **BASE EXISTENTE**; validação em clone de banco pessoal pendente |
| FR-002/003: CreativeBrief e CreativeDNA versionados | `Channel.brand_profile/editorial_profile`, novos `motion_ads` com brief próprio; sem `creative_dna_revisions` geral | **PARCIAL/PROPOSTO**; não sobrescrever brand profiles |
| FR-004: três direções criativas | Não comprovado no backend atual | **PROPOSTO**: serviço determinístico isolado no kit |
| FR-005/006: storyboard temporal + revisão concorrente | EDL/revision já existe; não há storyboard criativo genérico comprovado | **PROPOSTO**: snapshots/versionamento próprios, sem segunda EDL |
| FR-007/008/009: animatic e aprovação por hash | Player e pipeline de review/render existentes; sem fluxo criativo separado aprovado | **PARCIAL**: gates de aprovação criativa novos |
| FR-010/011: `sports_reveal_v1` + 12 s real | `kinetic_title_v1`, `motion_card_v1`, `flow_path_v1`, `character_dialogue_v1`; Motion Ad incremental | **PROPOSTO**; exemplo do kit não é preset instalado nem MP4 verificado |
| FR-012: editor multifaixa/Clip Lab | `EDLV2` com trilhas `video, voice, music, sfx, caption, graphic`; cortes, Football Edit, clips e revisão | **PARCIAL REAL**; não há NLE profissional completo |
| FR-013/014: clipping inteligente / cérebro factual | ASR/cortes, claims, Câmara/IBGE, Wikimedia Trends, MusicBrainz | **PARCIAL**; ranqueador/direção autônoma não demonstrados |
| FR-015/016: registry/bridges Motion Canvas, Cavalry e Jitter | Sem adapters de produção comprovados | **PROPOSTO**, pós-benchmark |
| FR-017: autopilot | Jobs com lease e schedule local de *rascunho* musical | **PARCIAL**; não confundir com geração/publicação end-to-end |
| FR-018: publisher | Export/review manuais e modos seguros | **NÃO IMPLEMENTADO** como publicação automática licenciada |
| FR-019/020/021: recovery, QC criativo, backup | Fencing/hash/CI Windows+PG, downloads validados; lacunas de reconciliação | **PARCIAL**; crash window e validação artística pendentes |
| FR-022/023/024: custo/estados/direitos | `ALLOW_PAID_AI=false`, `DRY_RUN=true`, rights gates existentes | **BASE EXISTENTE**; revisar propagação de hashes/rights ao módulo criativo |

**Importante:** `motion_ads` não substitui a especificação de Creative Director multi-nicho. Mas seu contrato deve ser reaproveitado quando fizer sentido.

## 5. Dependências e decisões de integração M1

### Camadas que devem ser preservadas

- Tauri/sidecar, `FastAPI` único e middleware em `apps/api/main.py`; novos routers devem herdar sessão/origin checks.
- `apps/api/edl_v2.py`, `apps/api/render_plan.py`, `apps/renderer/src/timeline-v2.tsx`, `root.tsx` e `apps/web/lib/api.ts`. **Não criar segunda timeline nem remover o Editor.**
- Contratos de fonte, direitos e aprovação nas rotas `projects`, `knowledge`, `motion_ads`, `music`.
- Alembic e bootstrap atuais; **NÃO** aplicar a migration `0010_creative_direction_REFERENCE.py` sem revisá-la e renomeá-la.
- Claim/lease/fence já existentes, registro de jobs e revisão. Não criar scheduler paralelo.
- Renderer `apps/renderer/package.json` usa `^4.0.365` para Remotion; `apps/web/package.json` fixa `4.0.532` para `remotion`/`@remotion/player`. **`npm ci` passou no CI**, mas conferir versões resolvidas via `npm ls` antes de adicionar novo pacote; não presumir uma única versão já instalada.

### Sequência exata sugerida para M1 (AINDA NÃO EXECUTAR)

1. **Preflight no Codex Desktop:** `git status`, HEAD e upstream; árvore atual de migrations; versão do app instalado; paths reais; cópia de segurança do SQLite **e assets** para outro diretório; hash e restauração em sandbox; execução da suíte de base.
2. Congelar `feat/rea-scheduled-music-drafts@69185e8` como base validada. Se HEAD mudar, **refazer M0 incremental**, não migrar cegamente.
3. Criar futura branch **`feat/creative-director-m1`** sobre o head validado, sem rebase/merge de PRs existentes e sem atualizar `main`.
4. Inspecionar `migrations/versions/0011_music_draft_schedule.py` e heads Alembic. Elaborar **`0012_creative_direction`** com `down_revision="0011_music_draft_schedule"`, se ainda for o único head. Testar esquema novo, SQLite copiado com EDLv1/v2 e PostgreSQL CI. Não tocar no banco real.
5. Introduzir schemas/services versionados para brief, Creative DNA, direção, storyboard e decisão, **reutilizando** `Channel`, `Project`, `ProjectRevision`, ledger de claims e direitos. Contratos do ZIP são referência, não copy-paste cego.
6. Adicionar só as rotas/API transacionais do M1, com `expected_revision`, proteção contra corrida (409), hash de snapshot, source/rights invariants, validação Pydantic e testes de invalidação.
7. Fechar M1 com testes/restart/migração rollback em clone, doc do estado e novo PR draft. **Sem UI de animação, Remotion do kit, 3-directions cinematográficas ou M2 nesta etapa.**
8. M2 será UI persistente; M3 será animatic Remotion de 12 s com MP4/FFprobe e comparação de quadros; M4 hash/approval; M5 preset EDL. Somente mediante autorização posterior.

### Critérios objetivos de aceite M1

- Criar/consultar/editar brief e DNA por projeto/canal; estado permanece após restart.
- Gerar 3 direções determinísticas **marcadas corretamente como referência**, sem alegações fictícias.
- Storyboard com tempos em milissegundos, ID único, validação de gaps/overlaps e snapshots imutáveis.
- PUT concorrente com `expected_revision` desatualizado → **HTTP 409**.
- Editar brief/storyboard ou alterar dependência com hash → revogar aprovação criativa antiga.
- Direito `UNKNOWN/RESTRICTED` não se torna publicável; claims não revisadas continuam bloqueadas.
- Suíte Python, lint, TypeScript, Windows CI e migração PostgreSQL passam; restore do SQLite clonado comprovado.
- Nenhuma regressão em edição, voz, clips, MusicBrainz/agenda, Motion Ad, Trends, 2D/3D ou preview do projeto existente.

## 6. Checklist de pendências que só o checkout Windows pode fechar

Executar **apenas quando houver acesso ao PC**, sem alterar o estado da instalação principal:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
git branch -vv
git diff --stat
git diff --cached --stat
# Ler o caminho de dados/configuração e conferir revisão Alembic do banco isolado.
# Não executar migração no banco em uso nem 'git reset --hard'.
.venv\Scripts\python.exe -m pytest -q tests
.venv\Scripts\python.exe -m ruff check .
node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json
node node_modules/typescript/bin/tsc --noEmit -p apps/renderer/tsconfig.json
npm ls remotion @remotion/player @remotion/cli --all
```

Executar `next build`, `git diff --check` e smoke do desktop isolado somente depois de conferir workspace e processos. Documentar comandos, hash do backup/restore, arquivos de log, paths de artefatos e motivo de qualquer `SKIPPED`.

## 7. Segurança, limites e decisão

- Nenhum dado, fonte, crédito, métrica, licença ou visual de terceiros foi inventado nesta auditoria.
- Nenhum artefato de demonstração se torna `APPROVED` sem revisão criativa/factual/direitos e hash correspondente.
- Modo VPS continua **NÃO PRONTO**, sem autenticação por dono e transporte de worker remoto.
- File rename + commit SQL não são transação atômica: falta reconciliador/recovery de crash.
- O local Windows do usuário não está disponível neste ambiente; portanto M0 integral de preflight **não pode ser marcado PASS** ainda.

**Decisão M0:** preservar PRs #1–#41 e fazer apenas este registro documental. **Próxima autorização exigida:** executar preflight local e revisão do plano M1; não implementar M1 automaticamente.
