# MediaGrid REA — execução no repositório principal

## Escopo e estado

Base: `disksanluca/mediagrid` em `4b0d246`, branch `feat/atelier-premium-v3`.
Trabalho novo: `feat/rea-edl-v2`. O pacote `MediaGrid-REA-transfer` é uma
especificação e contém código de referência isolado; não foi copiado para o
aplicativo como se os seis modos já estivessem operacionais. O repositório trAIde
e a instalação do usuário não foram alterados.

Objetivo: seis modos — cortes longos, Football Edit, Motion Ad,
Explainer/Conhecimento, Humor 2D e Narrativa 3D — sobre projetos, assets,
direitos, EDL, jobs, revisão e exportação comuns. Desktop Windows continua
funcionando offline. O VPS Linux sem GPU é uma topologia planejada para API,
banco, fila e web; render/ASR/Blender ficam no desktop. Nenhum VPS foi escolhido
ou implantado. Serviços pagos e publicação automática seguem desligados.

## Marco 0 — baseline reproduzido

- `uv run pytest -q`: 42 testes passaram na base, com um aviso de depreciação
  Starlette/httpx. `uv run ruff check .` e TypeScript Web/Renderer passaram.
- `scripts/prove_video_pipeline.py` foi incorporado como prova repetível em
  SQLite isolado em `data/rea-proof`. Usa a API, jobs VOICE/RENDER, síntese
  Windows, Remotion e FFmpeg existentes; exige Node e FFmpeg instalados. A
  primeira execução desta branch gerou 31 s, 1080×1920, H.264/AAC, SHA-256
  `57ee11c5c4259e59d97b01979fc18a477c9fd75a52bc1664f20dfe465822eaec`.
  Ambos os jobs terminaram `SUCCEEDED`; projeto em `QC`, não aprovado. Um quadro
  em 3 s mostrou texto legível, porém composição simples. O áudio foi
  confirmado por FFprobe e duração da voz, não por audição humana integral.
- CI Windows da base `4b0d246` passou ao compilar, instalar em runner
  descartável, iniciar API/worker, renderizar e testar exportação e backup.
  Isso não equivale a atualizar o PC do usuário.

## Marco 1 — migração iniciada, entrega vertical pendente

- Alembic `1.20.0` instalado pelo `uv.lock`, com baseline `0001_legacy` e revisão
  `0002_revisions`. O bootstrap valida todas as tabelas/colunas legadas antes
  de carimbar a base; faz snapshot SQLite antes da primeira migração. Novo
  banco recebe as tabelas legadas e depois a migração versionada. A tabela
  `project_revisions` guarda EDL JSON, número de revisão e SHA, sem tocar no
  campo `projects.edl` v1 nem no render atual.
- Teste de upgrade/rollback usa cópia de banco legado com projeto e confirma
  preservação do EDL e do projeto. A mesma migração foi exercitada numa cópia
  do banco da prova audiovisual. O serviço PyInstaller inclui as migrações;
  sidecar empacotado iniciou API e SQLite em pasta isolada na revisão
  `0002_revisions`.
- **Ainda não concluído:** conversor v1→v2 com preservação do comportamento de
  clipes em loop, API de revisão concorrente (`409`), Editor multifaixa,
  waveform/keyframes, preview e render a partir do mesmo EDL v2, invalidação de
  aprovação por hash e teste de MP4 legado após salvar uma revisão v2. A tabela
  nova não é apresentada como funcionalidade pronta.

## Ordem restante e gates

1. Fechar Marco 1: definir contrato v2 que preserve voz local, cartões e
   recortes/loop do v1; converter sem mutar projeto legado; persistir revisão
   com concorrência otimista; adaptar Editor, worker, preview e testes de
   render/rollback. Só então permitir edição v2 pelo usuário.
2. Ingestão longa com hash, probe, direitos, proxy e retomada.
3. Voz humana/local, ASR por palavra e captions corrigíveis.
4. Máquina de cortes com contexto e seleção humana; depois Motion Ad,
   Explainer, Football Edit, conhecimento com evidências, Humor 2D e 3D.
5. Web/VPS apenas depois de auth por recurso, PostgreSQL, fila com leases,
   worker Windows de saída e backup testados. Sem worker, o estado deverá ser
   `WAITING_FOR_WORKER` real.

Cada marco requer API, dados, worker, UI, testes, FFprobe, revisão visual e
auditiva, documentação e bloqueios honestos. Referências de terceiros não são
assets licenciados. Fatos e direitos exigem aprovação humana; IA não publica.

## Dependências e documentação oficial verificadas

Alembic `1.20.0` no ambiente desta branch; guia oficial atual consultado em
22/10/2026: [tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
e [batch migrations no SQLite](https://alembic.sqlalchemy.org/en/latest/batch.html).
A documentação online estava em `1.20.1`; não se usa autogenerate como migração
final. A migração atual só cria/remove tabela nova, sem alterar colunas SQLite
existentes. Remotion, FFmpeg, Câmara, IBGE e provedores de ASR não tiveram
protocolos alterados nesta etapa.

## Operação, integrações e custos

`uv run python -m apps.api.migrate` atualiza um banco configurado em
`DATABASE_URL`; faça backup e use uma cópia para validar antes de atualizar a
instalação. Para provar o pipeline, execute `uv run python
scripts/prove_video_pipeline.py` no Windows com Node/FFmpeg/voz disponíveis.
Saídas ficam em `data/rea-proof` e são ignoradas pelo Git.

REAL local: FastAPI, SQLite, jobs, voz Windows, Remotion/FFmpeg e ZIP manual.
PAPER/MOCK: nenhum resultado desta etapa foi contabilizado como produção.
Bloqueados/pendentes: ASR integrado, Blender instalado/testado, VPS, OAuth de
publicação, mídia autorizada para provas criativas e revisão humana final.
Custo de API paga nesta etapa: zero. Tempo/custo de GPU, VPS e provedores não
foram medidos; não há estimativa fictícia.
