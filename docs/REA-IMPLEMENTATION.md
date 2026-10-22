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

## Marco 1 — cenas, título animado, som, clipe local e prévia

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
- `apps/api/edl_v2.py` converte o EDL de cenas v1 em três trilhas v2 (imagem,
  voz, texto), preservando duração, ordem, texto, fonte, recorte e loop de MP4.
  A projeção para v1 recusa elementos fora do subconjunto de cenas, com uma
  exceção explícita: títulos locais `kinetic_title_v1` numa trilha `caption`
  são preservados no EDL canônico v2 e enviados ao renderer v2. Trilhas
  `music` e `sfx` aceitam WAV/MP3 locais com direitos OWNED/ LICENSED,
  ganho, fades, loop, início e duração. O worker confere hash e duração do
  arquivo, e mistura o som com a narração no MP4. O contrato
  valida texto, cor, posição, escala, opacidade, intervalos e keyframes; não
  aceita HTML ou presets arbitrários. Uma trilha extra `video` aceita MP4
  próprio/licenciado em `video_overlay_v1`, com início, duração, recorte de
  origem, foco e opacidade; velocidade diferente de 1 e outros keyframes
  continuam recusados. `GET/PUT
  /projects/{id}/edl-v2` expõe a revisão, hash da projeção legada e bloqueia
  edições concorrentes com `409`. O Editor v1 também avança a revisão e verifica
  hash. Regenerar o plano avança a revisão. Editar durante render ativo é recusado.
- O Editor React mostra as trilhas persistidas e a forma de onda decodificada
  do WAV real, com audição local. Continua editando cenas reais; título, duração,
  narração, mídia e ordem são salvos na API. Também adiciona, edita e remove
  títulos animados com três keyframes, adiciona/edita/remove música, efeitos
  e clipes MP4 da Biblioteca e persiste a revisão via API. A edição de cena preserva
  camadas válidas; alterações invalidam o vídeo anterior.
  O MP4 renderizado é a prévia fiel do subconjunto v2 implementado.
- Uma revisão invalida o estado de aprovação/saída. A revisão humana registra
  SHA-256 do EDL e do MP4; a exportação manual recusa alteração do arquivo
  aprovado. Teste de adulteração cobre este bloqueio.
- O worker compara o EDL salvo no job com o projeto antes do render e marca
  `FAILED` com evento `RENDER_STALE` se a timeline mudou após a fila. Um render
  concluído registra SHA-256 do EDL e do MP4 em `job.result`; teste de integração
  cobre o caso de job obsoleto sem iniciar Remotion.
- `uv run pytest -q`: **57 passaram**, um aviso Starlette/httpx.
  `uv run ruff
  check .` e TypeScript do Web passaram. `uv run python
  scripts/prove_video_pipeline.py --edl-v2-roundtrip` salvou revisão **2**,
  executou VOICE e RENDER (`SUCCEEDED`), gerou MP4 H.264/AAC 1080×1920 de 31 s
  em `data/rea-proof/20261022T224419Z`, SHA-256
  `57ee11c5c4259e59d97b01979fc18a477c9fd75a52bc1664f20dfe465822eaec`.
  Projeto permaneceu em `QC`, sem aprovação/publicação. O mesmo hash da prova
  anterior evidencia compatibilidade de conteúdo no caso testado.
- Após incluir o hash no worker, uma segunda prova em
  `data/rea-proof/20261022T225037Z` manteve os mesmos 31 s e SHA-256 do MP4;
  `job.result` contém também SHA-256 do EDL
  `cf3425b22322da77d64acf090332b688e083db43141ed3fce89f6940b83b7d71`.
  A prova repetida em `data/rea-proof/20261022T225159Z` conferiu em código
  ambos os hashes do job com os arquivos/projeto, com o mesmo resultado.
- Teste manual no navegador local com esta base isolada: timeline revisão 2,
  waveform e player WAV visíveis; edição do texto da primeira cena avançou a
  revisão para 3, mudou o estado para `SCRIPTED` e ocultou o MP4 anterior.
  Inspeção visual no navegador em 1440×900, 1280×800 e 1000×900 mostrou trilhas,
  waveform, player e painéis sem transbordamento visível. A audição humana
  integral do vídeo continua pendente.
- A composição `MediaGridTimelineV2` no Remotion renderizou uma camada local
  original fora das cenas, com opacidade/escala interpoladas em três keyframes.
  `uv run python scripts/prove_video_pipeline.py --kinetic-title` gerou o MP4
  `data/rea-proof/20261022T230258Z/renders/f861f294-93fc-412b-85f4-ebb49ec471f2.mp4`:
  31 s, 1080×1920, H.264/AAC, SHA-256
  `fad5ec257aa4f4e8052e99750c13b5ef72e675194697d57ba6f8f3fb108c9de6`.
  O worker registrou o hash da revisão v2, do EDL de cenas e do MP4.
  O quadro em 1,5 s foi inspecionado: título verde visível sobre a cena.
  A composição é prova técnica, ainda simples editorialmente. Em navegador,
  o texto do overlay foi editado e salvo (revisão 2→3), e um segundo título
  foi adicionado e salvo (revisão 3→4). Estado voltou a `SCRIPTED` e a saída
  anterior foi ocultada.
- A prova combinada `--kinetic-title --synthetic-sound` gerou MP4 H.264/AAC
  1080×1920 de 31 s em `data/rea-proof/20261022T231200Z`, SHA-256
  `fb2185e65314a5f5d270315bebbc090eadf7f448f22ea7ff9862125b2a176990`.
  O som foi criado matematicamente no teste, importado com hash/direitos e
  misturado à voz local. Entre 29–30 s, `scripts/check_sound_mix.py` mediu RMS
  0,000000 no render apenas com voz e 0,003569 no mix, confirmando presença
  do áudio no MP4. FFprobe confirmou H.264/AAC e 31 s; audição humana integral
  ainda não foi realizada. O navegador exibiu música/SFX persistidos; editar
  um SFX avançou revisão 4→5. A correção de recarga automática preservou a
  alteração por mais de 10 s; criar outro SFX pela UI avançou revisão 5→6.
- A prova combinada `--edl-v2-roundtrip --kinetic-title --synthetic-sound
  --synthetic-video-layer` importou um MP4 de padrão sintético original, salvou
  a trilha `video` sem transformá-la em cena e renderizou
  `data/rea-proof/20261022T232523Z/renders/7ca95a43-7336-457e-9c30-f1ea9bf54b6f.mp4`:
  31 s, 1080×1920, H.264/AAC, SHA-256
  `38862ebd38b2d0fe518350ff0c5215fa530799ffbee601589d8647da70424c88`.
  Os jobs VOICE/RENDER terminaram `SUCCEEDED`; o projeto ficou em `QC`, sem
  aprovação/publicação. O quadro de 4,5 s foi inspecionado e mostra o clipe
  sintético sobre a cena. Este é um teste de composição, não uma peça editorial.
  Na interface local, o clipe apareceu na trilha e no formulário; sua opacidade
  foi alterada de 1 para 0,5 e salva na revisão 2→3, invalidando a saída antiga.
- `GET /projects/{id}/preview` agora monta props da revisão salva com o mesmo
  gerador usado pelo worker. Verifica direitos/hash dos assets e usa FFprobe
  para checar duração e streams antes de expor a prévia. O Player React executa
  a composição `MediaGridTimelineV2` no editor antes do render, com cenas,
  camadas, som e voz local quando pronta; a voz final ainda passa pelo mix e
  limitador FFmpeg, portanto a audição decisiva é a do MP4. Uma revisão antiga
  incompatível usa as cenas atuais, como o worker, sem exibir camadas obsoletas.
  A API não salva um job nem finge que gerou MP4 ao abrir a prévia.
- A prova `data/rea-proof/20261022T233357Z/preview-props.json` validou a API de
  prévia após VOICE, incluindo as quatro cenas, título, música e clipe.
  O render seguinte manteve 31 s, H.264/AAC, 1080×1920 e SHA-256
  `38862ebd38b2d0fe518350ff0c5215fa530799ffbee601589d8647da70424c88`.
  No navegador local, o Player exibiu a revisão 3, iniciou a reprodução e
  avançou no tempo sem erro novo de console. `next build apps/web` passou.
- **Ainda pendente para concluir o Marco 1:** QA auditivo integral e teste
  de edição completa da composição no desktop empacotado. O contrato v2
  completo não está implementado.

## Marco 2 — ingestão longa local (prova técnica)

- MP4 de até 20 GiB usa sessão persistida em SQLite, partes de até 8 MiB e
  `Upload-Offset`. A biblioteca guarda o ID da sessão no navegador e, ao
  selecionar novamente o mesmo arquivo, consulta o deslocamento real antes de
  retomar. Repetir uma parte idêntica não duplica bytes; parte divergente ou
  fora de ordem retorna `409`. Outros formatos conservam a importação anterior
  de até 500 MB.
- A API registra direitos, criador/licença, URL de origem opcional, tamanho, SHA-256 do original,
  duração, dimensões, FPS e codecs após FFprobe. Hash declarado incompatível
  ou MP4 inválido impede a criação do asset. Duplicação por hash reutiliza o
  asset já registrado e seus direitos, sem sobrescrevê-los.
- O job `PROXY` roda no worker local e publica MP4 H.264/AAC de 640 px a
  12 fps após verificar o hash do original. Seu progresso vem do FFmpeg, não
  de um temporizador fictício. Uma forma de onda PNG é criada quando há áudio.
  A API entrega proxy/onda somente se o hash do artefato confere. A biblioteca
  mostra estado, duração e links reais. O editor usa o proxy para scrubbing,
  mantendo o original como fonte do render.
- Migração `0003_upload_sessions` cria `upload_sessions`; o rollback até
  `0001_legacy` remove apenas as tabelas novas. `data/uploads` e
  `data/proxies` são criadas pelo bootstrap. Nenhuma variável nova é necessária
  em `.env.example`; a importação usa `MEDIAGRID_DATA_DIR`, FFmpeg e FFprobe
  já configurados.
- `uv run pytest -q tests`: **60 passed**, 1 aviso de depreciação
  Starlette/httpx. `uv run ruff check .`: passou. TypeScript do web e renderer:
  passou. `node node_modules/next/dist/bin/next build apps/web`: passou.
- `uv run python scripts/prove_long_ingest.py` criou uma prova isolada com MP4
  sintético de 90 s em `data/rea-proof/20261022T234942Z-ingest`. Houve
  interrupção/reconexão entre partes, rejeição de trim além da fonte, salvamento na timeline e prévia pela
  API. O arquivo guardado reteve SHA-256
  `35414f624af521665782b638a34e38be70d979d393c4009aa11d6be76c9297f5`;
  proxy SHA-256
  `863070c71ffe4bcb65e2c72b6ef9450ae9c973fd2f0b0018811eb296684b2632`.
  FFprobe do proxy: H.264/AAC, 640×360, 90,166667 s. Frame de 12 s foi
  inspecionado; o proxy apareceu na biblioteca e no editor local.
- **Limites:** a prova sintética valida transporte, integridade, worker e
  interface, não qualidade editorial. Ainda falta teste com vídeo longo
  autorizado pelo usuário, avaliação auditiva completa, recuperação no
  instalador Windows e comportamento de espaço em disco quase esgotado.
  Sem mídia autorizada, cortes e Football Edit permanecem bloqueados para
  aceite criativo. Nenhum deploy, publicação ou custo de API paga ocorreu.

## Ordem restante e gates

1. Fechar Marco 1: validação visual/auditiva no desktop empacotado.
   Manter a projeção estrita enquanto o
   renderer v2 não suportar os novos elementos.
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
existentes. Remotion instalado `4.0.532`; composição e sequenciamento foram
conferidos na [documentação oficial](https://www.remotion.dev/docs/composition)
e no [guia de timing](https://www.remotion.dev/docs/timing) em 22/10/2026.
A API de [áudio do Remotion](https://www.remotion.dev/docs/html5-audio), a de
[OffthreadVideo](https://www.remotion.dev/docs/offthreadvideo), a do
[Player](https://www.remotion.dev/docs/player/player) e o
filtro [amix do FFmpeg](https://ffmpeg.org/ffmpeg-filters.html#amix) também
foram consultados nesta data. O código usa `Audio` do pacote `remotion` já
fixado, com render local; a documentação atual recomenda `@remotion/media`
para novos usos. A migração de pacote ficará para uma mudança versionada.
A [licença oficial](https://www.remotion.dev/docs/license/faq) depende do tipo
e porte da organização; nenhuma licença paga foi ativada. FFmpeg, Câmara,
IBGE e provedores de ASR não tiveram protocolos alterados nesta etapa.

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
