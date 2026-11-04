# MediaGrid Narrative POV Studio

## Estado da entrega

Esta branch acrescenta uma prova vertical real de 56 segundos ao Motion Composition
Engine M4. O resultado usa o Creative Director, revisão versionada, briefing com direitos,
snapshot aprovado, receita declarativa, fila existente, Remotion e FFmpeg. Não há segunda
timeline, aplicação paralela, publicação ou alteração da instalação principal.

O artefato final está em `docs/proofs/narrative-pov/narrative-pov-studio.mp4`. Ele tem
status `REQUEST_REVIEW`: passou QA técnico, mas não recebeu aprovação artística ou de
publicação.

## Resultado audiovisual

- História ficcional original em oito cenas e português brasileiro.
- Personagem Caio consistente: cabelo preto, moletom mostarda e construção vetorial única.
- Ambientes: quarto/anúncio, ônibus/cidade, café, inspeção POV, quarto chuvoso, conversa
  dividida, assistência e composição final.
- Enquadramentos e movimentos: establishing, médio, sobre o ombro, POV, close, aberto;
  push, track, rack focus, handheld, pull-out e pan.
- Cutout limitado, poses e expressões discretas, câmera, parallax, interfaces fictícias,
  tipografia contextual e oito efeitos sonoros procedurais.
- Locução `pm_alex` do Kokoro local em CPU, música procedural e mix estéreo original.

O vídeo não usa imagem gerada, fotografia de terceiro, marca, clone de voz ou asset externo.
A animação de personagem é cutout vetorial limitado, não animação quadro a quadro. O contato
visual confirma diversidade entre as oito composições, mas a cena 6 repete a frase
“Fatos, não briga” em dois níveis e o desenho permanece deliberadamente simples. Esses são
problemas artísticos abertos, não falhas escondidas por métricas.

## Arquitetura

1. O briefing e o Creative DNA continuam versionados no M1/M2.
2. Os sete agentes do PR #50 usam o Ollama em `127.0.0.1`, a fila `CREATIVE_AI`, um único
   slot por processo, validação Pydantic/JSON Schema e resultados `NEEDS_REVIEW`.
3. O roteiro ganhou estágios causais explícitos (`setup` até `lesson`), regras de variedade,
   gramática, continuidade e rejeição de preços, percentuais, garantias ou marcas fictícias.
4. O roteiro do Ollama da prova foi preservado como proposta, mas não adotado: ele ainda
   incluiu um desconto percentual e continuidade editorial insuficiente. O MP4 usa o fixture
   editorial original `tests/fixtures/narrative_pov_editorial.json`, identificado como
   `EDITORIAL_FIXTURE` em todos os registros de prova.
5. O storyboard editorial foi aprovado somente no banco descartável. A mix foi registrada
   antes do storyboard, preservando o hash do briefing e evitando invalidar a própria
   aprovação.
6. `pov.webtoon-cutout@1.3.0` é uma receita M4 declarativa com oito cenas. O renderer React
   genérico interpreta a receita; não existe componente React específico para este vídeo.
7. O plano derivado referencia revisão, snapshot, receita, asset e hashes. O render termina
   em `REQUEST_REVIEW` e publicação permanece desativada.

## Agentes locais

Na execução `narrative-20261104-06`, os sete jobs terminaram pelo
`qwen3:4b-instruct`/Ollama local:

| Tarefa | Latência | Reparos | Resultado |
| --- | ---: | ---: | --- |
| roteiro | 136,563 ms | 1 | `SUCCEEDED`, proposta não adotada |
| direções | 72,984 ms | 0 | `SUCCEEDED` |
| storyboard | 102,812 ms | 0 | `SUCCEEDED`, proposta não adotada |
| continuidade | 65,719 ms | 0 | `SUCCEEDED` |
| referências | 27,828 ms | 1 | `SUCCEEDED`, sem alegar pesquisa web |
| motion | 25,891 ms | 0 | `SUCCEEDED`, escolheu a receita 1.3.0 |
| QA | 74,640 ms | 0 | `SUCCEEDED`, manteve revisão humana |

Os jobs somaram 506,437 ms. O primeiro iniciou com 13.555 MiB de RAM e 5.920 MiB de VRAM
livres; após carregar o modelo havia 12.505 MiB e 2.120 MiB livres. Ao final do QA ainda
havia 10.439 MiB de RAM e 2.118 MiB de VRAM livres. O piso configurado é 4.096 MiB de RAM e
1.800 MiB de VRAM. O modelo não é descarregado à força porque pode ser compartilhado pela
Biu.

## Isolamento, cancelamento e Biu

- Ollama aceita somente origem HTTP loopback; nenhuma porta foi aberta na internet.
- Um lock entre processos impede duas gerações MediaGrid simultâneas.
- RAM e VRAM são verificadas antes de cada job; `RESOURCE_BUSY` falha de forma explícita.
- Jobs `CREATIVE_AI` em execução aceitam solicitação cooperativa de cancelamento, verificada
  durante o streaming do Ollama.
- A migração `0014_creative_ai_cancellation` adiciona `jobs.cancel_requested`.
- A Biu, seus modelos, banco, credenciais e serviço não foram modificados. O processo da Biu
  permaneceu ativo durante a prova. Não foi feito teste interativo de carga simultânea na
  assistente; coexistência observada não substitui esse teste humano controlado.

## TTS e geração visual

Kokoro foi escolhido para a prova: o repositório e os pesos oficiais são Apache-2.0 e a
lista oficial inclui vozes pt-BR. O runtime `kokoro==0.9.4` ficou em ambiente virtual isolado
sob `data/` e usou `CUDA_VISIBLE_DEVICES=''`. O primeiro carregamento medido de amostra levou
92,494 s, incluindo download/cache; a prova reutilizou o cache local.

O Piper atual (`OHF-Voice/piper1-gpl`) é GPL-3.0 e exige auditoria da licença de cada voz;
por isso não foi incorporado. ComfyUI também não estava instalado. Sua API local e o
offloading de baixa VRAM são tecnicamente compatíveis, mas nenhum checkpoint de imagem com
licença auditada estava disponível. Instalar ComfyUI/modelos no computador poderia disputar
os 6 GiB de VRAM com Ollama/Biu. A prova usa desenho vetorial original e não representa
placeholder como geração de imagem concluída.

Referências oficiais auditadas:

- <https://github.com/hexgrad/kokoro>
- <https://huggingface.co/hexgrad/Kokoro-82M>
- <https://github.com/OHF-Voice/piper1-gpl>
- <https://github.com/Comfy-Org/ComfyUI>
- <https://github.com/Comfy-Org/ComfyUI/blob/master/openapi.yaml>

## QA técnico

- MP4 H.264 High, `yuv420p`, BT.709, 1080×1920, 30 fps, 1.680 frames, 56,000 s.
- AAC-LC, 48 kHz, estéreo, 56,000 s; vídeo e áudio começam em 0.
- Decode completo passou; FFmpeg não encontrou trecho preto acidental nem congelamento
  superior a 2 s nos limiares usados.
- Áudio: −25,8 LUFS integrado, LRA 6,6 LU e pico verdadeiro −7,9 dBFS.
- Os oito segmentos de fala começam 350 ms após cada cena e terminam antes de seus slots.
- ASR local de retorno detectou pt-BR com probabilidade 1,0 e recuperou a narrativa inteira,
  com pequenas diferenças de reconhecimento. A naturalidade/pronúncia ainda precisa de
  escuta humana.
- Render M4 final: 262.438 ms, concorrência 1.
- Receita: SHA-256 `5a0124607cab185b8856d6ee62650efa2e095eb3f8e8f7b5366dbf4c625f5ce8`.
- Plano: SHA-256 `8544417f7943a406f48a7288644b54d66d5b12fa6c3497e29496527d007efb8b`.
- MP4: SHA-256 `8b2386bb8f884d606ae0f3d923a0f0d7199449528d766d260aa87e92a7af8f43`.

Os relatórios reproduzíveis, storyboard, locução, frames e hashes estão em
`docs/proofs/narrative-pov/`.

## Validações executadas

Todos os resultados abaixo foram executados nesta branch, não simulados:

| Comando | Resultado |
| --- | --- |
| `uv run pytest -q tests` | 287 passaram, 1 pulou; 2 avisos de depreciação do adaptador `datetime` do SQLite no Python 3.12 |
| `uv run ruff check .` | passou |
| `uv run python scripts/generate_motion_contracts.py --check` | passou; schema e tipos gerados estão sincronizados |
| `uv run python scripts/generate_local_agent_contracts.py --check` | passou; contratos dos agentes estão sincronizados |
| `uv run python scripts/build_motion_recipes.py --check` | passou; registro e hashes das receitas estão íntegros |
| `.\\node_modules\\.bin\\vitest.cmd run --root apps/web` | 2 arquivos e 11 testes passaram |
| `.\\node_modules\\.bin\\tsc.cmd --noEmit -p apps/web/tsconfig.json` | passou |
| `.\\node_modules\\.bin\\tsc.cmd --noEmit -p apps/renderer/tsconfig.json` | passou |
| `node node_modules/next/dist/bin/next build apps/web` | passou; páginas estáticas geradas |
| FFmpeg decode, `ffprobe`, detecção de preto/congelamento e QA de áudio | passaram no MP4 entregue |

O teste Rust/Tauri não foi executado porque `cargo` não está instalado/não está no `PATH`
deste host. Nenhum arquivo Tauri foi alterado nesta entrega. Aprovação artística e escuta
humana permanecem explicitamente fora dos resultados automáticos.

## Execução isolada

Pré-requisitos: Ollama loopback com `qwen3:4b-instruct`, FFmpeg, Node/Remotion já instalados
no repositório e um runtime Kokoro isolado com cache local.

```powershell
uv run python scripts/build_narrative_pov_recipe.py
uv run python scripts/proof_narrative_pov.py `
  --run narrative-YYYYMMDD-NN `
  --kokoro-python data/narrative-pov-proof/runtime/kokoro-venv/Scripts/python.exe `
  --kokoro-cache data/narrative-pov-proof/runtime/hf-cache `
  --approve-synthetic-storyboard
```

`scripts/resume_narrative_pov_render.py` retoma somente preview/render/QA de um banco de
prova já aprovado, sem repetir inferência, quando uma falha técnica interrompe essa etapa.

## Limitações e próximos refinamentos

- Aprovação artística e escuta humana continuam pendentes.
- Cutout possui poucas articulações; faltam rig facial, lipsync e gestos secundários mais
  orgânicos.
- A voz é inteligível no ASR, mas precisa de avaliação humana de prosódia brasileira.
- O QA do modelo interpretou incorretamente uma janela de duração; o prompt foi renomeado
  para `per_scene_narration_duration_ms` para reduzir essa ambiguidade.
- ComfyUI permanece `BLOCKED_NOT_INSTALLED_NO_AUDITED_MODEL`; não há geração visual local
  representada como pronta.
- O teste controlado Biu + MediaGrid com interação humana não foi executado.
- Publicação, deploy, instalação principal e merge permanecem fora do escopo.
