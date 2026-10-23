# Narração própria no Editor

Esta etapa permite importar áudio próprio ou gravar pelo microfone no Editor desktop.
O navegador/WebView precisa permitir `getUserMedia` e `MediaRecorder`; se não permitir,
o botão de importação de arquivo continua disponível. Nenhum modelo, serviço pago ou
credencial é necessário. O arquivo permanece no diretório de dados local.

## Fluxo real

1. Salve narração em todas as cenas. A gravação deve corresponder ao texto salvo;
   a confirmação é humana, não uma transcrição automática.
2. Em **Editor → Saída**, grave ou importe áudio e ouça a prévia. Confirme direitos
   e correspondência com o roteiro. O limite é 50 MB e 5 minutos.
3. `POST /api/v1/projects/{id}/voice/recorded` aceita multipart `file`,
   `rights_confirmed=true`, `script_confirmed=true` apenas em modo `LOCAL`.
   Recusa jobs de voz/render ativos, esboço sem narração, arquivo vazio, áudio
   inválido ou FFmpeg/FFprobe ausente. O áudio é normalizado para WAV PCM
   mono/48 kHz em arquivo temporário, com hash do original e da saída.
   WebM de `MediaRecorder` pode não trazer duração no cabeçalho; a conversão
   tem limite de 301 s e o WAV final precisa medir até 300 s.
4. O manifesto `data/voice/{id}.sha256` vincula hash do roteiro, hash do WAV
   e origem `RECORDED`. `voice_matches` confirma ambos os hashes antes de
   download e render. O evento `RECORDED_VOICE_IMPORTED` registra duração,
   tamanho, hashes, nome do arquivo e confirmações humanas. Trocar a voz
   revoga revisão/saída anterior; editar o roteiro torna a voz indisponível.
5. O render existente inclui o WAV verificado e ajusta a duração das cenas
   para preservar narração mais longa que o plano. Ouça o MP4 e revise
   fatos/direitos antes da exportação manual.

O áudio gravado não recebe limpeza de ruído, atuação ou alinhamento automático.
A aprovação editorial depende de uma pessoa. A qualidade acústica deve ser
verificada no hardware real do usuário; os testes usam sinal sintético.

## Execução e prova

No checkout de desenvolvimento, configure FFmpeg e FFprobe no PATH (ou as
variáveis opcionais em `.env.example`), execute a API/worker e rode
`uv run pytest -q tests/test_recorded_voice.py`. No desktop empacotado,
salve um roteiro, grave uma frase com autorização, confira o WAV, renderize,
ouça/assista ao MP4 e confirme que editar o texto oculta a voz antiga.

Sem migração de banco: o evento usa a tabela existente e os WAVs/manifests
ficam na pasta de dados. Integração REAL: API, hash, normalização, worker de
render e UI de importação. Gravação via microfone depende do WebView e aguarda
smoke no instalador. PAPER: qualidade de voz humana e audição editorial.
MOCK: nenhum resultado é apresentado como gravação própria do usuário.
Custo de API paga: zero. Não há deploy, postagem nem instalação do usuário.
Na branch de desenvolvimento, `pytest -q tests` passou com 115 testes e
1 teste Blender opt-in ignorado; Ruff, TypeScript e `next build` passaram.

## Prova técnica local em 23/10/2026

O primeiro CI Windows da branch falhou porque os testes de normalização
rodavam antes de o workflow preparar FFmpeg/FFprobe portátil (503 em vez de
422 ao enviar áudio inválido). O workflow agora monta o runtime primeiro e
adiciona seu diretório `bin` ao PATH dos testes Python. A confirmação desta
correção depende do CI do PR seguinte; não é tratada como aprovada pelo teste
local, que já tinha FFmpeg no PATH.

Base isolada em `data/recorded-voice-visual` (ignorada pelo Git): projeto de
cinco cenas com roteiro salvo; o job `VOICE` local gerou 18,48 s de fala SAPI
correspondente ao texto. Uma cópia foi importada pelo Editor usando o novo
endpoint, com manifesto `RECORDED`, `voice_ready=true` e hashes persistidos.
Esta cópia demonstra o caminho de importação, **não** qualidade de locução
humana nem uma gravação feita pelo usuário. O primeiro render de
desenvolvimento falhou por falta de `MEDIAGRID_RENDERER_ROOT`/`MEDIAGRID_NODE_PATH`
no processo avulso; após configurar esses caminhos e tentar novamente, o
worker finalizou `SUCCEEDED`. O instalador configura ambos automaticamente.

O MP4 resultante está em `data/recorded-voice-visual/renders/` com SHA-256
`f287e02991cf647524586f0b67c3572a509ac881057cd8a5dbc83729f8e59844`.
FFprobe confirmou H.264 1080×1920, AAC e 45,0 s. `volumedetect` mediu média
de −28,7 dB e pico de −5,1 dB; isso confirma sinal, não aprovação auditiva.
O quadro em 3 s foi inspecionado e mostra o título legível em tela vertical,
sem visuais externos. Projeto em `QC`, sem revisão factual, sem exportação
aprovada e sem publicação. Não houve uso de mídia do usuário.
