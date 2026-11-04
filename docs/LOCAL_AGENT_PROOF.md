# Prova dos agentes criativos locais

## Escopo e isolamento

Base: M4 do PR draft #48, commit `5a559c8416fbf2c3adc6918965ce3b6a266369cf`. A prova final `pov-20261103-06` usou **SQLite e diretório descartáveis** em `data/local-agent-proof/`; não tocou o banco instalado, a Biu, serviços globais ou a instalação principal. O projeto é ficcional. `--approve-synthetic-storyboards` autoriza somente a aprovação explícita da fixture local para teste do compilador; não representa aprovação editorial do usuário.

Comando reproduzível em Windows, com Ollama local e `qwen3:4b-instruct` já instalados:

```powershell
uv run python scripts/proof_local_agents.py --run NOVO_ID --full-pov --approve-synthetic-storyboards
```

O script cria um Brief/DNA, executa os sete jobs `CREATIVE_AI` pelo worker existente, adota direções e storyboard, acrescenta o score original aos seis shots por revisão M1, aprova explicitamente essa fixture, compila `pov.first-sale@1.2.0` com M4, renderiza pelo worker/Remotion e registra `REQUEST_REVIEW` no artefato. O render usa **o mesmo projeto e storyboard adotado**; o compilador deriva EDL v2 sem substituir silenciosamente a EDL do projeto. O plano e o vídeo preservam hashes de snapshot, receita e asset. O resultado não publica nada.

## Ollama e recursos observados

- Ollama `0.40.13`, HTTP em `127.0.0.1:11434`; não foi aberto para a rede. Modelos disponíveis: `qwen3.5:4b` (`d8b0f5e9…`, 3,3 GB) e `qwen3:4b-instruct` (`0edcdef3…`, 2,5 GB). A prova usou o segundo, digest completo `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
- RAM física: 33.231.568 KiB totais (~31,7 GiB); 10.660.396 KiB livres na leitura inicial. RTX 4050 Laptop: 6.141 MiB de VRAM, 253 MiB usados na leitura inicial. Durante uma chamada real, `nvidia-smi` mostrou 3.129 MiB usados, 2.792 MiB livres e 96% de utilização; `ollama ps` mostrou o modelo 100% GPU com contexto 4096. São **leituras pontuais**, não uma medição contínua de interferência na Biu.
- Sete jobs locais da prova final passaram no worker, com tempos medidos de 6.328 ms (referências textuais) a 47.266 ms (direções). Roteiro: 21.031 ms / 679 tokens de resposta; storyboard: 16.063 ms / 612 tokens. Total de latências das sete chamadas: ~117,2 s. Direções e notas de referência exigiram um reparo de contrato cada após cores inválidas; nenhum resultado inválido foi adotado. O agente de motion selecionou `pov.first-sale`, com `NEEDS_ASSET_BINDINGS_AND_PREVIEW`. O preview e render foram executados separadamente pela API M4.

O código usa [JSON Schema no `/api/chat` do Ollama](https://docs.ollama.com/capabilities/structured-outputs) e parâmetros/limites documentados pela [API oficial](https://docs.ollama.com/api/chat). A operação de modelos carregados foi verificada com a [documentação oficial](https://docs.ollama.com/faq).

## MP4 e QA técnica

- [Vídeo original de seis cenas](proofs/local-agents/pov-six-scene.mp4) (incluído no PR); cópia e evidências completas também em `data/local-agent-proof/pov-20261103-06/motion/` no host de teste.
- [FFprobe](proofs/local-agents/ffprobe.json): H.264, 1080×1920, 30 FPS, 900 frames; AAC estéreo 48 kHz, 1.409 frames/packets reportados; duração de container 30,016 s; 1.386.354 bytes.
- SHA-256 do MP4: `b635bc80f5e34b858e306008878be3cade052aa3189599b04498d947abb9a19a` (hash conferido em disco após a cópia).
- Plano derivado: SHA-256 `b5fb40b4cdca9876d30360ca9329ae7ac04afc9e14f43c223abf2883fc8713fc`. Receita: SHA-256 `5614b79ee9b93e147e6d488fe8bcdeab8bb54a1cf1f467a42847fde0543d34e9`.
- `ffmpeg -v error -i ... -f null NUL`: saída vazia, exit 0; decode completo sem erro. `blackdetect=d=0.1:pix_th=0.10`: nenhuma faixa preta detectada. `volumedetect`: média -26,9 dB, pico -15,3 dB. Isso verifica presença e nível do áudio, não sua qualidade artística.
- [Frames aos 2 s](proofs/local-agents/frame-2.png), [7 s](proofs/local-agents/frame-7.png), [12 s](proofs/local-agents/frame-12.png), [17 s](proofs/local-agents/frame-17.png), [22 s](proofs/local-agents/frame-22.png) e [27 s](proofs/local-agents/frame-27.png). Os frames aos 2, 12 e 22 s foram inspecionados visualmente. Texto legível e sem corte gráfico nessas amostras, mas o título do quinto shot contém erro gramatical (“O Primeiro Venda”); isso exige edição humana e não substitui revisão frame a frame.
- Revisão persistida do artefato: `REQUEST_REVIEW`, `publication_enabled=false`, vinculada aos hashes exatos do plano e MP4. Não houve aprovação artística.

## Resultado criativo e limites

O modelo produziu seis beats em segunda pessoa, três direções e seis shots com personagem ID estável. A composição M4 usa tipografia, um aparelho vetorial, elementos auxiliares, movimento de câmera/objeto e score original. **É uma prova funcional de integração, não um cartoon POV pronto para publicação.** A imagem é simples e repete o aparelho em várias cenas; não há personagem ilustrado, atuação, voz narrada ou montagem cinematográfica madura. A prova não teve escuta humana formal; áudio foi validado tecnicamente. O roteiro ainda contém inconsistência de objeto/causalidade (parece fotografar um aparelho com ele próprio), e o quinto título tem erro gramatical. Isso requer reescrita editorial.

A primeira tentativa gráfica de três cenas usou `geo.route-explainer` em 16:9; foi guardada apenas em `data/local-agent-proof/pov-20261103-03` para diagnóstico, sem ser apresentada como filme POV completo. A consulta inicial de motion na prova de seis cenas também sugeriu uma receita Music incompatível. O código passou a fornecer catálogo, rejeitar sugestão incompatível e registrar estado de compatibilidade; a consulta posterior selecionou a receita POV. O QA escrito pelo modelo também deixou passar problemas encontrados manualmente. Assim, `SUCCEEDED` significa contrato validado e persistido, não qualidade editorial garantida.

O modelo local disponível não produz ilustrações. ComfyUI e pesos visuais não foram instalados; geração cartoon e análise multimodal real permanecem bloqueadas. O Visual Reference Scout/web não foi ativado; a tarefa `references` trabalha apenas com texto do Brief/DNA. Não há evidência de uso simultâneo com a Biu, portanto o lock e o gate de modelo não constituem garantia de prioridade sobre ela.

## Validação e operação

Testes executados: `uv run pytest -q tests` (**285 passed, 1 skipped**, 176,26 s; skip do Blender 4.5 portátil opcional confirmado com `-rs`), `uv run ruff check .` (pass), geradores de contratos local e M4 com `--check` (pass), typecheck de web, renderer, contratos locais e M4 (pass), Vitest web (**11 passed**). API e Next foram iniciados somente em loopback sobre o banco descartável; o painel Creative Director foi aberto e o histórico compacto de agentes inspecionado em 1265×713. Os processos de teste foram encerrados.

Para uso local, configurar as variáveis do [`.env.example`](../.env.example), iniciar API, web e worker normalmente, salvar Brief e DNA no Creative Director e abrir **Assistentes criativos · Ollama local**. Os jobs, erros e hashes ficam consultáveis após reinício pelo SQLite. Não é necessário manter o Codex aberto. Não há migração de schema, serviço pago, publicação ou alteração de credenciais.
