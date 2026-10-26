# M3 — Cinematic Motion Proof

Base conferida: PR #44, `4af147f71bc599c3e8b4ac241d9f7650e251671d`, árvore limpa.
Branch: `codex/creative-m3-motion-proof`. Auditoria iniciada em 26/10/2026.

## Auditoria e decisão antes da implementação

- M1 `review_snapshot` inclui storyboard, DNA, direções, direitos, claims e também
  `Project.edl`, `plan`, `script`. Converter gravando nesses campos invalidaria a aprovação.
- EDL v2 já oferece tracks, milissegundos, keyframes, `sound_v1`, projeção para cenas
  e validação de continuidade. Será reutilizada como formato derivado, sem nova timeline.
- `render_props`, `MediaGridTimelineV2`, `<Player>`, staging com verificação de hash,
  Remotion CLI, FFmpeg, fila Job, lease/heartbeat e promoção protegida já existem.
- `kinetic_title_v1` e `motion_card_v1` fornecem tipografia e keyframes; não contêm
  linguagem esportiva em camadas. Acrescentar somente `sports_cinematic_v1` ao mesmo
  registro de overlays, mantendo o mixer `sound_v1` e a composição existente.
- Persistência: usar `Job.payload` para o plano derivado completo e SHA-256 canônico.
  ID determinístico do Job garante idempotência por plano. Não há endpoint de edição
  do payload. O worker confere hash, revisão, aprovação e arquivos antes de executar
  e novamente antes de promover a saída. Alterações bloqueiam execução/entrega.
- **Sem nova tabela ou migração.** `Project`, `ProjectRevision`, EDL original, plan e
  script permanecem intactos. Resultados pertencem ao job, sem substituir o MP4 legado.
- Preview e MP4 usam os mesmos props e preset. Aprovação criativa permite executar;
  não equivale a aprovação audiovisual, editorial ou autorização para publicar.

## Dependências e fontes oficiais

Nenhuma API paga. Remotion existente, versão fixada no package-lock, sem upgrade.
Referências consultadas: [interpolate](https://www.remotion.dev/docs/interpolate),
[Easing](https://www.remotion.dev/docs/easing),
[CLI](https://www.remotion.dev/docs/cli/render),
[licença Remotion](https://www.remotion.dev/license).
Fonte Barlow Condensed: Jeremy Tribby / The Barlow Project Authors, SIL OFL 1.1;
[metadados oficiais](https://github.com/google/fonts/tree/main/ofl/barlowcondensed).
Licença incluída com a fonte. Áudio e geometria serão originais/procedurais, sem samples.

Versões executadas: Remotion **4.0.532**, Node **24.19.0**, React **19.3.0**,
Next **16.3.8**, Python **3.12.10**, FFmpeg/FFprobe **9.0.2** (Gyan).
O encoder utilizado internamente por Remotion informa libavcodec 61.19.100/libx264.
O package-lock existente permanece intacto; reprodução deve usar `npm ci`.
Fonte local sem download em runtime: Barlow Condensed Bold, SHA-256
`e476562ec9c1e16cf16475895b511f08c804f438cc9a9f80a44ea50a0eeb5b65`.

## Arquitetura entregue e mapeamento

`CreativeReview(APPROVE)` → snapshot vigente → conversão determinística →
`Job.payload {plan, plan_sha256}` → fila/lease existentes →
`MediaGridTimelineV2` → estágio privado → FFprobe/decode →
revalidação de dependências → promoção do MP4 por job.

O plano preserva project_id; storyboard completo com ID/revisão/SHA; decisão
e snapshot aprovados; brief/DNA versionados; direção selecionada; assets, hashes e
direitos; EDL v2 derivada; presets e hashes de fontes do renderer; configurações
de qualidade, codecs, frames, FPS e canvas. A aplicação não oferece escrita
sobre esse payload. O SHA detecta adulteração e UUID v5 por plano resolve
duas solicitações concorrentes para o mesmo job.

O job não modifica status, EDL, plan, script nem ProjectRevision. O teste também
cobre projetos com EDL/roteiro pré-existentes. A aprovação permaneceu
`APPROVED_STORYBOARD` após enfileiramento, render e download. Se uma dependência
mudar durante a codificação, o resultado é descartado, o job falha e o arquivo
legado permanece intacto. Retry/cancel/heartbeat usam o mecanismo existente.

| Tempo / frames | Plano | Implementação no preset | Áudio original |
| --- | --- | --- | --- |
| 0–2 s / 0–59 | ENTRE / EM JOGO | Máscara tipográfica, easing Bézier, escala/posição/opacidade dos keyframes EDL, órbitas e faixa diagonal | Impacto em 0, pulso 120 BPM |
| 2–5 s / 60–149 | SINTA / O CAMPO | Bola vetorial original com shading, rotação, aproximação e parallax entre órbitas | Impacto em 2 e arpejo |
| 5–9 s / 150–269 | MUDE / O JOGO | Campo inclinado, rota progressiva, três posições conceituais e wipe diagonal | Impacto em 5 e subdivisões |
| 9–12 s / 270–359 | É AGORA. | Tipografia central, círculo expansivo, estabilização com drift e encerramento | Impacto em 9, acorde e cauda com fade |

As quatro fases têm geometria e movimento definidos no preset. Ele **não interpreta**
prosa de câmera/áudio como linguagem de programação: essas intenções permanecem
no manifesto. Os textos, IDs, tempos e cores vêm do storyboard/DNA; a conversão
recusa outras durações, FPS, formato ou títulos que ultrapassem os limites.
Paleta: fundo `#0B1013`, texto `#F4F0E6`, destaque `#D7FF3F`.
As etiquetas 01/02/03 são posições conceituais, não resultados esportivos.

### Rotas e interface

- `POST /api/v1/projects/{id}/creative/motion/preview`: exige revisão/hash
  aprovados, devolve plano e os props reais para o Player.
- `POST /api/v1/projects/{id}/creative/motion/render`: mesmos pré-requisitos;
  devolve Job (202), sem reenfileirar o mesmo plano.
- `GET /api/v1/projects/{id}/creative/motion/jobs/{job_id}/video`: exige job
  correto e concluído, hash físico e dependências vigentes; 409 quando obsoleto.
- Progresso, erros, retry e cancelamento continuam em `/api/v1/jobs`.
- Em **Creative Director → Revisão → Sports Motion**, selecionar a trilha
  já presente no brief e nos quatro planos. Preparar prévia com som e escolher
  MP4 540×960 ou 1080×1920. A UI mostra job/status/hash e o vídeo concluído.
  Alterações não salvas ou falta de aprovação bloqueiam os controles.

Preview e MP4 usam o mesmo componente, keyframes e áudio. A versão reduzida
usa `--scale=0.5`, mantendo canvas lógico, 360 frames e timings.

## Arquivos alterados

| Arquivo | Responsabilidade |
| --- | --- |
| `apps/api/creative/motion.py` | Bridge, plano imutável, validação e idempotência |
| `apps/api/edl_v2.py` | Registro e validação do preset `sports_cinematic_v1` |
| `apps/api/routes/creative.py` | Preview, fila e entrega do artefato |
| `workers/render/remotion_runtime.py` | Invocação CLI compartilhada, extraída do renderer atual |
| `workers/render/main.py` | Despacho do job no mesmo worker, recuperação e lease existentes |
| `workers/render/creative_motion.py` | Staging, revalidação, Remotion e QA técnico mínimo |
| `apps/renderer/src/sports-cinematic.tsx` | Geometria e animação originais; carregamento de fonte com delayRender |
| `apps/renderer/src/sports-font.ts`, `sports-font-OFL.txt` | Fonte incorporada e licença |
| `apps/renderer/src/timeline-v2.tsx`, `types.ts` | Integração no renderer existente |
| `apps/web/components/creative/creative-motion-proof.tsx` | Player real, seleção de trilha/qualidade, render e status |
| `apps/web/components/creative/creative-workspace.tsx` | Acesso a partir da revisão M2 |
| `apps/web/lib/api.ts`, `types.ts` | Cliente tipado e respostas |
| `scripts/m3_score.py` | Score estéreo procedural determinístico, sem samples |
| `scripts/proof_creative_motion.py` | Ensaio reproduzível em banco/pastas descartáveis |
| `scripts/qa_creative_motion.py` | Decode, métricas de áudio, sincronização, frames e hashes |
| `tests/test_creative_m3.py` | Oito testes de contrato, persistência, concorrência e bloqueios |
| `.env.example` | Runtime local existente e isolamento da prova |
| `docs/testing/creative-m3/` | Evidências do MP4 real, não screenshots de mock |

## Prova audiovisual entregue

Diretório local:
`data/creative-m3-proof/final-01/`.
MP4: `creative-renders/92516ca6-8be2-559f-9a43-3e170fcec433.mp4`
(5.530.927 bytes; aproximadamente 5,53 MB).

Caminho absoluto neste PC:
`C:\Users\SP0097A\Documents\Codex\2026-10-12\github-plugin-github-openai-curated-remote-2\work\mediagrid\data\creative-m3-proof\final-01\creative-renders\92516ca6-8be2-559f-9a43-3e170fcec433.mp4`.

- Projeto: `98f5fce5-a612-4684-8b73-f460a404d655`.
- Direção escolhida: `timeline` / referência determinística M1.
- Storyboard SHA-256: `58284939a9a0526d430fc29530c0cb7d8ae5be07f76805095acafa59b61317c7`.
- Snapshot aprovado: `1f93f337029126e955a9d84aca9552784fbf3e8c00ae85d6fcb432aa1b4d2242`.
- Plano derivado: `35db5a2ffc6bdba5e0cfc5edad37ee9f02fea3bc775147770cf9a2c5838d02b2`.
- MP4 SHA-256: `146246344c51e00674df6463a13a37721b5138865f7bfb55e41eeff340fe8f14`.
- Score WAV SHA-256: `3526e4ae9189acf89cfaf45a67aab91bdcdb7612513cb88f8298f61ddfb985af`.

O script registrou aprovação **explícita de fixture sintética** com
`--approve-synthetic-storyboard`, para executar a sequência solicitada
0/2/5/9/12s. O ator está identificado como `M3 fixture operator` e a nota
declara que não houve aprovação humana da qualidade audiovisual. A UI/API
nunca aprovam automaticamente storyboards. O usuário ainda precisa assistir
e ouvir esta prova para decidir sobre a linguagem artística.

![Quatro planos do MP4 real](testing/creative-m3/contact.jpg)

Frames de fronteira e encerramento:
[0 s](testing/creative-m3/00-0s.jpg),
[1,9 s](testing/creative-m3/03-1.9s.jpg),
[2 s](testing/creative-m3/04-2s.jpg),
[5 s](testing/creative-m3/07-5s.jpg),
[9 s](testing/creative-m3/10-9s.jpg),
[11,967 s](testing/creative-m3/13-11.967s.jpg).
Todos foram extraídos do MP4 com FFmpeg. Os 14 frames originais estão na
subpasta local `frames/`.

## Validação técnica automática

| Verificação executada | Resultado |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests` | **141 passed, 1 skipped** em 115,84 s. Skip: Blender opt-in. |
| `.venv/Scripts/python.exe -m pytest -q tests/test_creative_m3.py` após adicionar os dois últimos casos | **8 passed** em 5,47 s, incluindo alteração durante encode e EDL legado preenchido |
| `.venv/Scripts/python.exe -m ruff check .` | Passou |
| `node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json` e renderer | Passaram |
| `node node_modules/vitest/vitest.mjs run apps/web` | 3 passed |
| `node node_modules/next/dist/bin/next build apps/web` | Passou |
| Script de prova em `preview-01` | Worker real; 540×960; 50,495 s incluindo primeiro bundle |
| Script de prova em `final-01` | Worker real; 1080×1920; 24,583 s |
| Script de prova em `reproduce-01` | Novo banco/projeto; mesmo código/score; 25,590 s |
| FFprobe + decode integral | H.264 High, 1080×1920, 9:16, 30/1 FPS, **360 frames**, vídeo 12,000 s |
| Áudio/container | AAC LC, 48 kHz, estéreo; **12,011 s**, tolerância 0,060 s para padding AAC |
| Integridade | Decode de todos os frames e áudio sem erros |
| Detecção de preto | Nenhum trecho: regra ≥98% pixels abaixo de 2% por ≥0,03 s |
| Movimento amostrado | 120 frames a 10 Hz; menor diferença média 0,24164/255, sem amostras repetidas |
| Áudio mono medido | RMS −18,349 dBFS; pico amostral −1,614 dBFS; não é medida LUFS/true peak |
| Sincronização de envelopes | Deslocamento estimado 0 ms nas quatro entradas; resolução 10 ms, tolerância 30 ms |
| Migrações | Head único continua `0012_creative_direction`; nenhuma migração nova |

O teste de mudança durante encoding utiliza stub **somente para exercitar
orquestração e descarte**. Não é evidência de codec. As três provas acima
executaram o Remotion/FFmpeg reais, sem stub, e têm manifests/MP4 físicos.
Resultados brutos: [FFprobe](testing/creative-m3/ffprobe.json),
[QA](testing/creative-m3/qa.json),
[plano](testing/creative-m3/derived-plan.json),
[prova](testing/creative-m3/proof.json),
[score](testing/creative-m3/score-manifest.json).

### Reprodução

O segundo render final não foi idêntico byte a byte. Seu SHA-256 é
`12bb9ef03b3a4417d9df73731108a183fad1fa799b8d743f69c9093837165e85`.
O áudio PCM decodificado foi idêntico. A comparação de vídeo teve SSIM
médio **0,999518**, mínimo por frame **0,997822**, nenhum frame abaixo de 0,99.
Há pequenas diferenças de pixels/codificação; a origem exata não foi isolada.
Portanto a prova confirma reprodução de conteúdo/timings com tolerância visual,
**não determinismo binário do MP4**. IDs de projetos e snapshots naturalmente
diferem entre bancos novos.
[Hashes decodificados](testing/creative-m3/reproducibility.json),
[SSIM](testing/creative-m3/ssim-summary.txt).

## Avaliação artística e limitações

**Avaliação artística humana: PENDENTE.** Não houve sessão humana de escuta
ou aprovação do filme. As medidas técnicas não atestam que o resultado é
cinematográfico, agradável ou pronto para publicação.

Inspeção visual dos frames pelo agente: título do segundo plano e campo do
terceiro estavam próximos do rodapé na primeira prévia; ambos foram reposicionados
antes do final. A hierarquia, margens e continuidade do fundo estão visíveis nas
evidências. Frames 0/60/150/270 iniciam com máscara de texto; são transições
intencionais, com elementos gráficos visíveis, sem tela preta completa.

Pontos para avaliação/refinamento humano:

- A bola é uma ilustração vetorial com sugestão de volume, não material realista.
- A tipografia domina a composição; avaliar se o ritmo de 2 segundos da abertura
  permite leitura confortável em telefone.
- As quatro fases têm linguagem gráfica consistente, mas o wipe diagonal pode
  parecer repetitivo. Avaliar motivação e intensidade das transições.
- O score é uma composição sintética curta. Conferir impacto, textura, fadiga
  auditiva, equilíbrio e sensação de clímax em caixas e fones.
- Contraste e safe areas foram inspecionados em frames; não houve ensaio humano
  com overlays de todas as plataformas. O arquivo usa full-range 4:2:0
  (`yuvj420p` no FFprobe), sem mastering HDR/broadcast.
- A ferramenta de navegador recusou observar `http://127.0.0.1:3000/` por
  política de segurança. Não se contornou o bloqueio. Build, API, props e render
  passaram; a interação da nova UI em navegador continua sem validação nesta rodada.
- A prova foi executada no checkout local. O instalador Windows não foi alterado,
  instalado ou validado para M3. O fingerprint de fontes requer o runtime local.
- Nenhuma dependência paga foi ativada; custo de serviços externos: zero chamadas.
  Energia elétrica e custo de hardware não foram medidos.

## Como executar e acessar

Na raiz do repositório, com `uv sync`, `npm ci`, Node, FFmpeg e FFprobe no PATH
e Chrome headless já instalado pelo runtime Remotion:

```powershell
.venv/Scripts/python.exe scripts/proof_creative_motion.py --run minha-prova --quality final --approve-synthetic-storyboard
.venv/Scripts/python.exe scripts/qa_creative_motion.py data/creative-m3-proof/minha-prova
```

O nome de execução precisa ser novo. O script rejeita caminhos fora de
`data/creative-m3-proof` e pastas existentes. Ele configura DATABASE_URL e
MEDIAGRID_DATA_DIR antes de importar a API. Nenhum banco instalado é usado.
Para a versão reduzida, usar `--quality preview`.

Para usar a tela existente com a prova final:

```powershell
$proofDir = (Resolve-Path data/creative-m3-proof/final-01).Path
$env:DATABASE_URL = "sqlite:///" + ($proofDir + "/workspace.db").Replace("\", "/")
$env:MEDIAGRID_DATA_DIR = $proofDir
$env:MEDIAGRID_RENDERER_ROOT = (Resolve-Path apps/renderer).Path
$env:MEDIAGRID_NODE_PATH = (Get-Command node).Source
.venv/Scripts/python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
# Em outro terminal:
node node_modules/next/dist/bin/next dev apps/web --hostname 127.0.0.1 --port 3000
```

Abrir o projeto **Entre em jogo — estudo original** e acessar Creative Director
→ Revisão → Sports Motion. O arquivo local também abre diretamente em qualquer
player MP4. MP4, WAV e bancos ficam ignorados pelo Git; evidências pequenas
estão versionadas. Em clone novo, executar os scripts para gerar a própria prova.

O próximo passo é a avaliação humana deste vídeo e do som. M4, redesign
Lovable, publicação, VPS, merge e instalação principal não foram iniciados.
