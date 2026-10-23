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

## Marco 3 — ASR local e legendas corrigíveis (prova técnica)

- A migração `0004_transcripts` acrescenta `transcripts` e `transcript_words`.
  Cada transcrição guarda hash da mídia original, motor/versão/idioma, revisão,
  estado editorial, palavras com tempo/confiança e cues corrigíveis. A API
  rejeita tempos fora da mídia, sobreposição de legendas e salvamentos sobre
  revisão concorrente. Uma edição revoga a aprovação e o MP4 anterior.
- O job `ASR_WORDS` usa `faster-whisper==1.2.1` em CPU/int8 com modelo local,
  sem chamada de inferência à nuvem ou download em execução. Lê áudio em
  blocos de cinco minutos para conter memória. Sem fala, persiste
  `NO_SPEECH_DETECTED`; falhas são `FAILED` com erro real. A interface mostra
  player, forma de onda quando existe, palavras e cues editáveis, revisão e
  SRT/VTT só após aprovação humana.
- O job `CAPTION_RENDER` grava legendas aprovadas no MP4 local com FFmpeg/libass,
  preserva áudio quando presente e verifica duração, streams e SHA-256. O
  download é revogado se o original, a aprovação ou o arquivo gerado mudar.
  Direitos `OWNED`/`LICENSED` são exigidos antes de criar esse derivado.
- O instalador passa a incluir o motor ASR e o modelo MIT
  `Systran/faster-whisper-base` fixado em
  `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`. O build confere SHA-256
  `d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9`
  do `model.bin` e o filtro `subtitles` do FFmpeg portátil. O download do
  modelo ocorre somente no build do instalador; o aplicativo instalado
  executa offline. O CI Windows do PR #5, run `39876535393`, concluiu com
  sucesso, incluindo build do instalador e smoke de ASR/legendas no aplicativo
  instalado em runner descartável. Isso não instala a versão no PC do usuário
  nem substitui revisão humana completa do vídeo/áudio.
- `uv run python scripts/prove_word_asr.py --model-dir CAMINHO_DO_MODELO`
  executou o fluxo API → worker → SQLite → revisão → SRT → MP4 em banco
  isolado com vídeo e voz sintéticos. Em
  `data/rea-proof/20261023T000056Z-asr`, obteve 13 palavras, três cues,
  idioma `pt`, modelo `1.2.1`, MP4 de 6,772 s com SHA-256
  `a2f17454e434d0755b22d61ef5400a7eb6232120f21f79d8700cced48f7df4a5`.
  Um quadro em 2 s foi inspecionado e mostra a legenda sobre o vídeo.
  A audição humana completa e o teste com mídia autorizada ainda faltam.
- A mesma prova com o FFmpeg portátil `@ffmpeg-installer/win32-x64@4.1.0`
  gerou `data/rea-proof/20261023T000517Z-asr`: 13 palavras, três cues,
  MP4 com 7,533 s e SHA-256
  `7a3e52dc1e510fa86e7e39b1e9007c5f12b5b2ac40ffdbce65c09ccd9f3d4386`.
  `pwsh -NoProfile -File scripts/build-desktop-sidecar.ps1` concluiu o EXE
  local. A API congelada reportou `word_asr_available=true`; o worker EXE
  processou um WAV sintético em `ASR_WORDS` com `SUCCEEDED`, 13 palavras e
  três cues. O smoke do instalador Tauri também passou no CI citado acima.
- `uv run pytest -q tests`: **63 passed**. `uv run ruff check .`:
  passou. TypeScript do web/renderer e `next build apps/web`: passaram.
- Nenhuma API paga, VPS ou publicação foi ativada. O custo de inferência local
  foi zero em API; consumo elétrico e tempo em outras máquinas não foram medidos.

## Marco 4 — máquina de cortes (prova técnica local)

- A migração `0005_clip_candidates` persiste sugestões explicáveis por asset,
  SHA-256, revisão da transcrição e versão do algoritmo. Inclui contexto antes
  e depois, razões e pontuação, seleção/rejeição humana, limites e crop com
  revisão otimista. O baseline ordena janelas por cobertura de fala, pergunta,
  troca de falante e limites de frase; não promete achar os melhores momentos,
  detectar cenas ou prever alcance.
- A API exige vídeo com direitos `OWNED`/`LICENSED`, transcrição temporizada
  aprovada e áudio. Edição impede cortar palavra ou cue aprovado. Jobs
  `CLIP_ANALYSIS` e `CLIP_RENDER` usam SQLite e worker local. O download só
  aceita job concluído, seleção vigente e SHA-256 do MP4 intacto; editar a
  transcrição torna os candidatos anteriores obsoletos. A Biblioteca oferece
  player da fonte, contexto, entrada/saída, foco manual, seleção e download.
- O render FFmpeg preserva áudio, queima as legendas aprovadas e verifica
  duração, streams e hash. O formato vertical usa crop manual e recusa
  ampliação acima de 3×. O smoke do instalador foi ampliado para análise,
  seleção e MP4 vertical com mídia sintética; ainda aguarda execução no CI
  desta branch.
- `uv run pytest -q tests`: **65 passaram**. `uv run ruff check .`, TypeScript
  Web/Renderer, `next build apps/web` e análise sintática do smoke PowerShell:
  passaram. `uv run python scripts/prove_clips.py` executou upload, aprovação,
  análise, revisão e dois renders em banco isolado. Prova em
  `data/rea-proof/20261023T001742Z-clips`, fonte sintética de 32 s SHA-256
  `412ddaf885227a050c30c89308d1da064dcaec91e81697385345f0995b1b65b4`.
  Dois candidatos geraram MP4 distintos H.264/AAC: vertical 1080×1920,
  29,933 s, SHA-256
  `45333a579c40e5ce64b2e02d82de6c8270ae98195c90c080ab6d9193388b7b9f`;
  proporção da fonte, 19,933 s, SHA-256
  `73a6df4b3f884b60ae35a17f0fb40362774f4f06c7803fa3c9684c32c039500c`.
  FFprobe confirmou vídeo e áudio. Um quadro vertical foi inspecionado, com
  legenda legível e margem inferior. A interface foi inspecionada no navegador.
  O áudio sintético é um tom, portanto não comprova ritmo, fala natural ou
  qualidade editorial. Não há filmagem/trilha autorizada para o aceite criativo
  de podcast, debate ou futebol.
- No runner Windows, o teste Python que cria MP4 sintético registra `SKIP`
  explícito se FFmpeg/FFprobe ainda não estiverem instalados na etapa de testes.
  O smoke posterior usa os binários portáteis do instalador para testar análise,
  seleção e render real; sua execução e resultado são gate separado.
- Migração: tabela nova, sem modificar arquivos ou colunas legadas. `.env.example`
  não requer nova variável. REAL local: API, SQLite, worker, FFmpeg e UI.
  PAPER/MOCK: nenhum corte foi contabilizado como produto criativo. Custo de
  API paga: zero; tempo e energia de produção em outros PCs não foram medidos.

## Marco 5 — cartão de motion integrado (primeira entrega vertical)

- `motion_card_v1` é um preset fechado no EDL v2: etiqueta, título, mensagem,
  cor de marca, layout empilhado/dividido e keyframes de escala/opacidade.
  A API limita texto, duração mínima de 2,5 s e posição central segura. Não
  executa HTML/JS de usuário. O Editor salva o cartão em revisão persistida;
  prévia `Player` e render usam as mesmas props Remotion. Editar a timeline
  invalida saída/revisão anteriores. A narração local e faixas de som existentes
  permanecem disponíveis.
- `uv run pytest -q tests`: **66 passaram**; Ruff, TypeScript do renderer,
  `next build apps/web` e análise sintática do smoke PowerShell: passaram.
  `uv run python scripts/prove_video_pipeline.py --motion-card
  --synthetic-sound --format vertical` produziu MP4 1080×1920 H.264/AAC de
  31,0 s em `data/rea-proof/20261023T002624Z`, SHA-256
  `455b98209ede59fbfa2f5e89a7f4370ba0407efa5cda8eb682be85820f603ebf`.
  A mesma prova em `--format horizontal` produziu 1920×1080, 31,0 s,
  SHA-256 `01281728c91f5f1b9bf5840a85bddfbc16154275add8288392caf0b59c4b971e`
  em `data/rea-proof/20261023T002711Z`. Os jobs VOICE/RENDER terminaram
  `SUCCEEDED`, os projetos ficaram em `QC`, sem aprovação/publicação.
  FFprobe confirmou streams e dimensões; quadros em 5,5 s foram inspecionados
  nos dois formatos. O áudio completo e o ritmo ainda exigem audição humana.
- O smoke Windows do PR #7 salvou cartão, obteve prévia e renderizou MP4 com
  áudio no aplicativo instalado; CI Windows concluiu com sucesso. Sem migração
  de banco: o preset mora no JSON versionado do EDL v2.
  `.env.example` não precisa de variável nova. REAL local: API, EDL, SQLite,
  Remotion, FFmpeg e UI. PAPER/MOCK: nenhuma campanha concluída ou métrica
  de desempenho foi declarada. Custo de API paga: zero; energia/tempo de
  outras máquinas não medidos.
- Marco 5 ainda precisa de storyboard completo, mais famílias de presets,
  mapa vinculado a fontes, amostra de anúncio e explainer com mídia
  autorizada e revisão audiovisual integral. Este cartão não satisfaz sozinho
  o aceite criativo do marco.

## Marco 5 — diagrama de fluxo editável (segunda entrega vertical)

- `flow_path_v1` adiciona um diagrama conceitual de 2–4 etapas ao EDL v2,
  com título, rótulos curtos, cor, tempo, keyframes e crédito visível opcional.
  O esquema fechado recusa etapa vazia, texto excessivo, duração menor que 3 s
  e posição fora da área segura. O Editor salva revisões reais; `Player` e
  render usam as mesmas props. Sem crédito, o vídeo declara que o diagrama é
  conceitual e pede confirmação de fontes/alegações. A revisão humana da
  entrega continua exigindo URLs e confirmação factual/direitos.
- `uv run python scripts/prove_video_pipeline.py --motion-card --flow-diagram
  --synthetic-sound --format vertical` concluiu VOICE/RENDER em
  `data/rea-proof/20261023T003747Z`: H.264/AAC 1080×1920, 31,0 s, SHA-256
  `839ffa6ef72637d98052186b537a2e6c1171c666e33144f06cdbf6d35b752d1d`.
  A prova horizontal em `data/rea-proof/20261023T003912Z` produziu
  1920×1080, 31,0 s, SHA-256
  `cc1b46bff6bc9d728ac7eac100e6476aaa783b6d931202d29cf441432b25b484`.
  FFprobe e quadros em 12,5 s foram inspecionados; a primeira quebra ruim de
  rótulos no horizontal foi corrigida e os quadros finais mostram as etapas
  legíveis. Áudio sintético e voz local não constituem aceite editorial.
- O smoke do instalador desta branch inclui cartão e diagrama no mesmo projeto,
  prévia e MP4 com áudio; CI ainda pendente. Sem migração adicional de banco
  nem variável nova no `.env.example`. REAL local: EDL/API/SQLite/UI/Remotion.
  PAPER/MOCK: nenhum explainer factual concluído ou resultado de audiência.
  Custo de API paga: zero; tempo/energia de produção externa não medidos.

## Marco 6 — Football Edit manual (primeira entrega vertical)

- `football_sequences` guarda uma revisão por projeto de canal Football, com
  eventos marcados manualmente, intervalo original, papel no arco, foco de crop,
  hash da mídia e fonte do placar opcional. A migração `0006_football_sequences`
  só cria uma tabela; o projeto e o EDL existentes não são alterados. API e
  Editor recusam mídia sem direitos, intervalo fora da fonte, replay sem ação
  anterior com o mesmo ID e placar sem URL. Salvar uma nova revisão exige nova
  aprovação de eventos e direitos e invalida o download anterior.
- O worker `FOOTBALL_RENDER` revalida hash/direitos, recorta cada fonte com
  FFmpeg, conserva seu áudio, aplica rótulo `REPLAY` e placar revisado quando
  informado, concatena em MP4 e registra SHA-256/duração/fontes no job. A
  fila é idempotente para a mesma revisão com saída íntegra. Backup local
  inclui os derivados `caption-renders`, `clip-renders` e `football-renders`.
- Prova sintética local em `data/rea-proof/20261023T005032Z-football`:
  MP4 H.264/AAC 1920×1080, 4,516 s, SHA-256
  `98d88e61edd8687f46c927594b2d795a51d8c45b527ae66adc75e6f25078ea76`.
  FFprobe confirmou streams; o quadro em 3,7 s mostra o selo `REPLAY`.
  Não há gol, placar ou mídia esportiva real nessa amostra. O teste integrado
  cria fonte sintética com áudio, marca ação/replay, aprova, renderiza e prova
  que revisão nova bloqueia o MP4 antigo. O smoke Windows instalado repete
  o fluxo com mídia sintética; CI desta branch ainda pendente.
- QA visual do Editor com projeto e fonte sintéticos isolados: marcou ação e
  replay com o mesmo ID, salvou revisão 1, aprovou eventos/direitos e o worker
  concluiu o job `SUCCEEDED`; o link de MP4 apareceu. O export 9:16 tem
  H.264/AAC 1080×1920, 6,020 s, SHA-256
  `ec390f7fb219bbe2962ba4812fc123fce87ea23d05c30bcd818045d3de41ae16`.
  `football-editor-succeeded.png` e `football-ui-replay-frame.png` no mesmo
  diretório mostram a interface e o selo no quadro. O áudio é tom sintético;
  não foi feita avaliação de ritmo musical ou recepção humana.
- REAL local: API, SQLite, worker, FFmpeg, Editor e backup. PAPER/MOCK:
  detecção automática de eventos, trilha licenciada, edição em batida,
  speed ramp, atuação e qualidade editorial de um Football Edit real.
  Sem filmagem/trilha autorizada, o aceite criativo segue `BLOCKED`.
  Nenhuma variável nova em `.env.example`; API paga custa zero e consumo
  de energia de outras máquinas não foi medido.

O renderer de sequência usa FFmpeg 9.0.2 local. O
[demuxer concat oficial](https://ffmpeg.org/ffmpeg-formats.html)
exige streams compatíveis;
por isso cada lance é normalizado a H.264/AAC e 30 fps antes da junção. O
[filtro subtitles/libass](https://ffmpeg.org/ffmpeg-filters.html)
insere os rótulos revisados. Documentação conferida em 23/10/2026; nenhuma API
externa ou serviço pago foi acionado.

## Marco 7 — alegações com evidência por cena (primeira entrega vertical)

- A migração `0007_knowledge_claims` acrescenta um ledger de alegações por
  projeto/cena com URL, título da fonte, `published_at`, trecho de apoio,
  revisão e aprovação humana individual. O Editor permite adicionar, corrigir,
  consultar e retirar uma alegação sem apagar seu histórico. A primeira
  alegação ativa `content_type=knowledge`; projetos antigos sem alegações
  conservam o fluxo anterior.
- A API não baixa URLs arbitrárias e não afirma verificar fatos. A pessoa abre
  a fonte, confere trecho/contexto e aprova. O export manual exige ao menos
  uma alegação ativa, todas aprovadas, cenas válidas e URLs presentes na
  revisão final. O manifesto contém o ledger e `claim_digest` SHA-256;
  qualquer edição/remoção revoga a aprovação e bloqueia o pacote anterior.
  Salvar um novo roteiro ou EDL também exige nova conferência de todas as
  alegações aprovadas; o Editor inclui as URLs delas na revisão final.
  O worker de vídeo existente segue renderizando a cena; o ledger é o gate
  editorial do artefato, sem texto factual criado automaticamente.
- Teste de integração usa projeto e MP4 sintéticos: fonte ausente, alegação
  não revisada, URL omitida e revisão alterada bloqueiam o export; o pacote
  aprovado inclui digest e fonte. O smoke Windows instalado exercita o mesmo
  gate com dados explicitamente fictícios de CI. Isso não é prova de uma
  reportagem factual nem de qualidade da narração.
- Validação local desta etapa: `uv run pytest -q tests` (69 passaram),
  `uv run ruff check .`, TypeScript e build Next passaram; o parser do script
  PowerShell passou. Uma alegação sintética foi salva pelo Editor e voltou
  após recarga, ainda em `REVIEW_REQUIRED`; a captura está em
  `data/rea-proof/20261023T003747Z/knowledge-claim-persisted.png` (ignorada
  pelo Git). Não houve revisão factual humana da alegação de teste.
- REAL local: API, SQLite, Editor, revisão/export e worker de vídeo existente.
  PAPER/MOCK: checagem factual automática, captura/arquivo da página de fonte,
  base de fontes por domínio e explainer jornalístico aprovado. O aceite
  criativo depende de fontes e revisão humanas. Nenhuma variável nova em
  `.env.example`, serviço pago, VPS ou publicação externa.

## Marco 8 — rig original e boca marcada manualmente (primeira entrega vertical)

- `character_dialogue_v1` é um item de caption no EDL v2. Pydantic aceita
  somente o rig original `migo_v1`, expressões/poses fechadas e 1–64 marcas
  de boca ordenadas, sem sobreposição e dentro da duração. Revisões do EDL
  continuam concorrentes e invalidam o MP4 anterior.
- O Editor permite escrever o balão, escolher expressão, pose e cor, e editar
  `start_ms`, `end_ms` e forma da boca por marca. Nenhum algoritmo afirma
  deduzir fonemas; a pessoa deve alinhar as marcas ao WAV e revisar o filme.
  O componente SVG/React de Remotion é compartilhado entre Player e MP4.
- API, banco de revisões existente, worker de render e smoke do instalador
  Windows exercitam o preset. Não houve migração de banco nem variável nova em
  `.env.example`. O rig é código vetorial original e não depende de baixar
  stickers, personagens, música ou conteúdo de terceiros.
- Prova técnica local `--character-2d`: MP4 vertical (`data/rea-proof/20261023T011556Z`,
  SHA-256 `538db26b0af324877289f5b9812678b82c7fb1a02539483fd7d4ba7498e84b4f`)
  e horizontal (`data/rea-proof/20261023T011844Z`, SHA-256
  `3ff985223e870d9373a324f7249f65099bd8134da2d00964f825fdcf6ba4885b`).
  Ambos têm voz Windows, H.264/AAC, 31 s e jobs VOICE/RENDER `SUCCEEDED`.
  Quadros em 0,8 e 1,3 s mostraram estados diferentes da boca; o layout
  horizontal foi corrigido após inspeção para preservar palavras inteiras.
  Os cues desta prova não foram
  calibrados foneticamente; atuação, piada, tempo de punchline e continuidade
  de uma cena dialogada permanecem pendentes de revisão humana.
- REAL local: Editor, API/EDL, Player, worker Remotion, MP4 e prova FFprobe.
  PAPER/MOCK: direção dramática, lip sync automático, segundo personagem,
  biblioteca de efeitos licenciados e aceitação criativa da sequência 2D.
  Custo de API paga: zero; nenhum VPS, postagem ou instalação no PC do usuário.
- Validação local desta entrega: `uv run pytest -q tests` (70 passed),
  `uv run ruff check .`, TypeScript de `apps/web` e `apps/renderer`, build
  Next.js e parser do smoke PowerShell. No aplicativo em execução, o Editor
  salvou três marcas de boca e recarregou a revisão 2; o Player exibiu o
  personagem e o balão no primeiro trecho, como no MP4. A verificação
  audiovisual permanece técnica: a voz sintética da prova não foi escrita
  para o personagem nem alinhada aos cues.

## Marco 9 — narrativa 3D original (primeira entrega vertical)

- Branch `feat/rea-narrative-3d`, sobre o Marco 8. Migração Alembic
  `0008_narrative_3d` cria uma tabela nova para storyboard, revisão, hashes do
  rig/mundo e áudio, job de blocking e aprovação. Não altera projetos ou EDL
  existentes. O backup local inclui `narrative-renders/`; a migração de cópia
  legada foi coberta no teste de migrações. `.env.example` documenta o caminho
  opcional do Blender.
- API e Editor salvam três a oito tomadas com duração, beat, ação, câmera e luz.
  A API rejeita formatos 3D fora de 9:16/16:9 e mantém a orientação do projeto
  igual à revisão salva do storyboard.
  Revisão concorrente é rejeitada; editar invalida aprovação e downloads antigos.
  O worker valida o hash do storyboard e do script, direitos e hash de áudio,
  espaço em disco, versão do Blender e cada sequência de PNG. Produz blocking
  de 12 fps e final de 24 fps, H.264/AAC; áudio não fornecido vira silêncio
  identificado. A aprovação exige atestar visualização integral, continuidade
  e ritmo. Na ausência de Blender o job fica `WAITING_FOR_WORKER` e pode ser
  reativado após configurar o executável. O smoke Windows instalado verifica
  storyboard/migração e o estado de dependência; seu resultado no CI ainda será
  registrado após a branch ser publicada.
- Runtime testado: Blender portable oficial `4.5.14 LTS` (SHA-256 do ZIP
  `b9533d2397ac1984db4466fb23a7a4649391cca93f6e84209f9bcc60d071c8b9`),
  sem cópia no Git ou instalador. A licença é GPL. Fontes oficiais:
  [download 4.5](https://download.blender.org/release/Blender4.5/),
  [linha de comando](https://docs.blender.org/manual/en/4.5/advanced/command_line/index.html)
  e [licença](https://www.blender.org/about/license/).
- Prova local sintética: `MEDIAGRID_TEST_BLENDER=<blender.exe> uv run pytest -q
  tests/test_narrative_3d.py` passou (2 testes em 80,92 s). O arquivo final
  ignorado pelo Git em `data/narrative-renders/800421a2-529a-4b6f-9286-62e882213da2-r1-final.mp4`
  tem 4,5 s, 1280×720, H.264/AAC, 24 fps, 293049 bytes e SHA-256
  `6d52207a2639ed9c64e913b0dd796b813a661f73a3d4e2db31e49c6d6249785f`.
  O quadro da última tomada foi inspecionado após corrigir o enquadramento da
  antena do personagem. A faixa AAC é silêncio, não som autoral aprovado.
  Uma tentativa anterior após suspensão prolongada do PC estourou o timeout
  do Blender; a repetição acordada passou. Não há validação criativa humana.
- Validação da branch: `uv run pytest -q tests` (71 passed, 1 skipped porque o
  teste Blender é opt-in), `uv run ruff check .`, `tsc --noEmit` de `apps/web`,
  `next build` 16.3.8, `git diff --check` e parser PowerShell passaram. O
  teste Blender opt-in passou separadamente. A validação visual do React em
  navegador local foi impedida pela política da superfície de automação; o
  build e os testes de API não substituem essa verificação. O smoke do
  instalador ainda precisa do CI desta branch.
- REAL local: banco, API, Editor React, worker Blender/FFmpeg, blocking,
  aprovação, hash e MP4 técnico. PAPER: atuação, desenho de som, narrativa
  longa, prova audiovisual com mídia autorizada e execução em PC instalado.
  MOCK: nenhum resultado desta etapa é apresentado como produção. Custo de API
  paga zero; tempo de render desta prova foi medido pelo teste, sem previsão de
  custo operacional em máquinas diferentes. Sem VPS, deploy ou publicação.

## Ordem restante e gates

1. Fechar Marco 1: validação visual/auditiva no desktop empacotado.
   Manter a projeção estrita enquanto o
   renderer v2 não suportar os novos elementos.
2. Ingestão longa com hash, probe, direitos, proxy e retomada.
3. Fechar Marco 3 no instalador Windows e fazer QA auditivo/visual humano.
4. Fechar Marco 4 com filmagem autorizada, revisão integral de dois cortes e
   smoke do instalador. Fechar Motion Ad no desktop instalado e continuar Explainer, Football Edit,
   conhecimento com evidências, Humor 2D e 3D.
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
IBGE não tiveram protocolos externos alterados nesta etapa. Para as legendas,
foram verificados o filtro [subtitles/libass](https://ffmpeg.org/ffmpeg-filters.html#subtitles),
o [código e licença MIT do faster-whisper](https://github.com/SYSTRAN/faster-whisper),
o [modelo MIT fixado](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66)
e o [download por revisão do Hugging Face Hub](https://huggingface.co/docs/huggingface_hub/main/en/guides/download)
em 22/10/2026. A versão de runtime é `faster-whisper 1.2.1`; modelo de 148 MB.

## Operação, integrações e custos

`uv run python -m apps.api.migrate` atualiza um banco configurado em
`DATABASE_URL`; faça backup e use uma cópia para validar antes de atualizar a
instalação. Para provar o pipeline, execute `uv run python
scripts/prove_video_pipeline.py` no Windows com Node/FFmpeg/voz disponíveis.
Saídas ficam em `data/rea-proof` e são ignoradas pelo Git.

REAL local: FastAPI, SQLite, jobs, voz Windows, Remotion/FFmpeg e ZIP manual.
PAPER/MOCK: nenhum resultado desta etapa foi contabilizado como produção.
Bloqueados/pendentes: smoke do instalador 3D atualizado no CI, execução do
Blender no PC final do usuário, VPS, OAuth de publicação, mídia autorizada para
provas criativas e revisão humana final.
Custo de API paga nesta etapa: zero. Tempo/custo de GPU, VPS e provedores não
foram medidos; não há estimativa fictícia.

## Incremento Motion Ad — 23/10/2026

O formulário React e `POST /motion-ads/projects` criam quatro cenas a partir
do texto fornecido pelo criador, com EDL v2 versionado e dois cartões animados
renderizáveis. O banco atual guarda o briefing inicial e SHA-256 no plano;
não houve migração. Edições de cenas atualizam duração e texto dos cartões,
e a revisão exige fontes aprovadas para gancho, problema e benefício.
`POST /plan` não substitui o briefing por um plano genérico. O projeto segue
o worker local e a exportação manual existentes. Detalhes e prova em
[MOTION-AD-BRIEF.md](MOTION-AD-BRIEF.md).

Validação desta etapa: `pytest -q tests` com 120 passed e 1 skipped
(Blender opt-in), Ruff, TypeScript, `next build` 16.3.8 e `git diff --check`.
Um MP4 sintético 1080×1920 H.264/AAC de 17 s foi renderizado e o bloqueio
de exportação sem revisão foi confirmado. O formulário criou outro projeto
real em banco isolado; Editor e modal foram vistos em 1440×900, 1280×800
e 1000×900. REAL: API, SQLite, revisão EDL, UI, voz Windows e render.
PAPER: qualidade editorial/auditiva humana, mídia autorizada e instalação
do novo build no PC do usuário. MOCK: nenhum conteúdo fictício foi chamado
de pronto para publicação. Custo de API paga zero; sem VPS ou postagem.
