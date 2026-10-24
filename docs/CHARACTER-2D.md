# Diálogo 2D original — Migo e Luma

O Editor permite criar cartões `character_dialogue_v1` em momentos distintos
da timeline, escolher Migo ou Luma em cada um e mostrar os dois no mesmo quadro.
Os dois rigs SVG são originais
e renderizados pela mesma composição Remotion usada pelo Player e pelo MP4.
Texto, cor, expressão, pose, início e marcas de boca são salvos na revisão EDL
v2. Trocar um personagem ou editar uma marca invalida o vídeo anterior e a
aprovação editorial. O contrato aceita somente `migo_v1` e `luma_v1` e recusa
marcas fora da duração, sobrepostas ou menores que 50 ms.

Para montar uma conversa, posicione cartões alternados ou ative a dupla em um
cartão. Edite as marcas de boca de cada personagem ouvindo a faixa WAV.
O MediaGrid mantém uma faixa de narração por
projeto. Se os personagens precisam de vozes diferentes, grave e importe o
diálogo completo como WAV com direitos confirmados. A troca de personagem
não cria uma segunda voz e as marcas não são deduzidas de fonemas.

## Prova técnica local

```powershell
$env:MEDIAGRID_FFMPEG_PATH = 'C:/caminho/ffmpeg.exe'
$env:MEDIAGRID_FFPROBE_PATH = 'C:/caminho/ffprobe.exe'
.venv/Scripts/python.exe scripts/prove_video_pipeline.py --character-2d --format vertical
```

Em 24/10/2026, a prova local em `data/rea-proof/20261024T000422Z` criou um
projeto e salvou dois cartões com Migo entre 0–4 s e Luma entre 5–9 s. VOICE
e RENDER terminaram `SUCCEEDED`; FFprobe confirmou H.264/AAC, 1080×1920 e
31 s. SHA-256 do MP4:
`36072cdf1612ca9265585719ef63767711e38c69ab4cef79948c685a5cc6e8e2`.
Quadros em 2,0 e 6,5 s foram vistos: nomes, texto e silhuetas distintas estão
legíveis e dentro do quadro. A voz SAPI gerada lê o roteiro técnico geral;
ela não atua as falas dos personagens. O projeto ficou sem aprovação humana
e sem publicação. Os arquivos de prova são locais e ignorados pelo Git.

Uma segunda prova em `data/rea-proof/20261024T000522Z` usou 16:9. VOICE e
RENDER terminaram `SUCCEEDED`; FFprobe confirmou H.264/AAC, 1920×1080 e
31 s, SHA-256
`667132b2b970a85d77994c31cf41f1c1b8cbb15fcf45787e4089f167d19e1327`.
Quadros em 2,0 e 6,5 s mostram os dois rigs e balões legíveis sem corte nas
bordas. Isto ainda é prova visual técnica, não uma cena de humor aprovada.

O smoke do instalador Windows usa dois cartões reais no EDL, incluindo uma
dupla, confere a prévia e renderiza MP4. O áudio desse teste é um tom sintético
identificado no log. O resultado da dupla será registrado após a CI da branch.

No build web local de produção com API/SQLite isolados, o Editor criou um
cartão pela interface, trocou Migo por Luma e salvou a revisão 1→2; a prévia
Remotion exibiu Luma. Depois adicionou Migo à segunda cena e salvou a revisão
2→3, com ambos os cartões visíveis na timeline persistida. O seletor e a cor
da Luma foram inspecionados visualmente em 1265×712. O banco de teste está em
`data/ui-second-character-proof`, ignorado pelo Git. Isso valida a edição
local nessa resolução, não substitui QA visual em todas as resoluções alvo.

Não houve migração SQL nem variável nova em `.env.example`. A entrega usa API,
`ProjectRevision`, Editor, Player, worker e FFmpeg atuais. Sem serviço pago,
VPS, postagem ou instalação no PC do usuário. A qualidade de timing cômico,
atuação, vozes distintas e continuidade ainda precisa de mídia/roteiro
editorial e revisão humana.

## Dupla no mesmo quadro — prova técnica incremental

O contrato EDL v2 guarda fala, cor, expressão, pose e marcas de boca de cada
rig. Exige Migo e Luma distintos, texto curto e marcas válidas dentro do
cartão. O Editor permite adicionar/remover o segundo rig e editar suas marcas
independentemente. A prévia e o worker usam a mesma composição Remotion. A
revisão salva invalida aprovação e MP4 anteriores, como nas edições EDL v2.

Em `data/rea-proof/20261024T001756Z`, o cartão da dupla em 10–14 s foi
renderizado em MP4 de 31 s, H.264/AAC, 1080×1920. SHA-256:
`fee1a323358009aba09608ee2351c8412a6fe7b4810df3fe8bdb58b5c5f0a780`.
Em `data/rea-proof/20261024T001845Z`, a versão 1920×1080 gerou MP4
H.264/AAC de 31 s, SHA-256
`b938014ca0955aecbc68ad75c82ce5c9ebf089a0dbd671733962670b97cc9331`.
Frames aos 11 s foram inspecionados nas duas proporções: rigs e balões são
distintos, legíveis e não foram cortados. VOICE e RENDER terminaram
`SUCCEEDED` em ambos. Os vídeos continuam sem revisão editorial, atuação ou
sincronia automática; a voz SAPI técnica lê o roteiro geral, não as falas de
Migo e Luma. Para vozes reais diferentes, importe WAV com gravação própria
ou licença e revise a mixagem. Os arquivos de prova são locais e ignorados
pelo Git. Não houve migração SQL nem variável nova em `.env.example`.

No build Next local e API/SQLite isolados em `data/ui-second-character-proof`,
o Editor ativou Migo como segundo rig de um cartão Luma existente. Uma fala
foi editada, uma segunda marca de boca foi adicionada e a revisão 3→4 foi
salva pela interface. A prévia Remotion da revisão 4 exibiu os dois rigs,
balões e rótulos em 1265×712; o vídeo ainda não foi renderizado nesse projeto
de UI. Este teste não equivale à prova do instalador Windows nem ao aceite
criativo humano.
