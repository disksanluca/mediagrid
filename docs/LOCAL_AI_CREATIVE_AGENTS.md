# Agentes criativos locais — integração v1

## Base preservada

Esta entrega parte do M4 do PR draft #48 (`5a559c8416fbf2c3adc6918965ce3b6a266369cf`). Reusa `Channel`, `Project`, revisões M1 do Creative Director, `Job`, o worker de mídia, o compilador de receitas M4 e o render Remotion/FFmpeg. Não cria timeline, renderizador ou banco paralelo. Nenhuma migração foi necessária: os rascunhos e sua proveniência são armazenados em `Job.result`; a adoção usa as revisões criativas existentes. A EDL v2 e a renderização anterior não foram alteradas. A receita original `pov.first-sale@1.2.0` acrescenta seis cenas verticais declarativas ao registro M4, com gráficos vetoriais e trilha procedural original; o renderer compartilhado a interpreta.

## Configuração e isolamento

Definir `MEDIAGRID_AGENTS_ENABLED=true`, `MEDIAGRID_AGENTS_MODEL=qwen3:4b-instruct` e `OLLAMA_BASE_URL=http://127.0.0.1:11434` no ambiente **local** do processo MediaGrid, depois iniciar API e worker existentes. A função vem desativada por padrão. O provedor rejeita origem que não seja HTTP loopback e usa `httpx.Client(trust_env=False)`; não altera configuração global do Ollama, Biu, modelos, serviços ou credenciais. O acesso da interface passa pela autenticação já existente da API.

A fila `CREATIVE_AI` é persistente, com até um trabalho MediaGrid ativo, 12 solicitações por 24 horas, `max_attempts=1`, prioridade 200 e lock entre processos. O worker de mídia usa o mesmo mecanismo de lease/recuperação do projeto. Se outro **modelo** estiver carregado no Ollama, o trabalho falha com `MODEL_BUSY` em vez de tentar desalojá-lo. O lock só coordena processos MediaGrid: não reserva GPU para a Biu nem garante ausência de disputa quando ela usa o mesmo modelo. Chamadas têm timeout de 150 s e `keep_alive=30s`. O provedor verifica modelo instalado e captura digest, tokens, latência, versão/hash do prompt, hashes dos insumos e hash do resultado. Não fornece acesso a ferramentas, shell ou execução de código ao modelo.

## Contratos e tarefas

Os sete contratos Pydantic são estritos (`extra=forbid`) e o Ollama recebe o JSON Schema nativo, `think=false`, seed 17, temperatura 0,2 e limites de contexto/saída. JSON malformado ou fora do contrato recebe até duas tentativas de reparo; depois o job falha, sem rascunho de sucesso. `scripts/generate_local_agent_contracts.py` produz JSON Schemas e tipos TypeScript em `contracts/local-agents/generated/`; `--check` verifica deriva. A validação semântica adicional fica no Python.

| Tarefa | Resultado | Limite editorial |
| --- | --- | --- |
| `script` | Seis a doze beats POV, personagem estável, narração em segunda pessoa | Com briefing factual, exige ao menos uma fonte marcada revisada; texto permanece rascunho. |
| `directions` | Três direções visuais | Adoção explícita cria revisão M1 com `origin=ollama_local`. |
| `storyboard` | Seis a doze ideias de shot; a aplicação distribui frames no tempo do briefing | Exige roteiro atual, direção M1 atual e escolha explícita; adoção cria revisão M1 e invalida aprovação anterior conforme regras existentes. |
| `continuity` | Descrição textual de personagem, roupa, locais e conflitos | Não cria imagens nem prova continuidade visual. |
| `references` | Notas de inspiração extraídas somente do Brief e DNA | Não pesquisa a internet nem atribui licença a referência externa. O Visual Reference Scout continua futuro. |
| `motion` | Sugestão de receita M4 registrada com hash/slots e checagem determinística de número de cenas, limite total de 30 s e formato | `BLOCKED_RECIPE_MISMATCH` quando incompatível; mesmo uma sugestão compatível ainda exige bindings de assets, preview e render M4. O compilador M4 escala os tempos internos da receita para os shots aprovados. |
| `qa` | Lista de alertas e sugestões | `human_review_required=true`; não aprova ou publica. |

Todas as tarefas revalidam Brief, DNA e dependências antes de persistir. Jobs de motion exigem snapshot de storyboard aprovado; a aprovação é conferida novamente após a geração. Um resultado `SUCCEEDED` significa **JSON validado**, nunca aprovação criativa, fato confirmado ou MP4 produzido.

## Rotas e interface

- `GET /api/v1/creative/agents/status`: estado Ollama/modelo/tarefas.
- `POST /api/v1/projects/{id}/creative/agents/jobs`: enfileirar tarefa com revisões esperadas.
- `GET /api/v1/projects/{id}/creative/agents/jobs`: consultar resultados/erros.
- `POST /api/v1/projects/{id}/creative/agents/jobs/{job}/adopt-directions`: adotar três direções em revisão M1.
- `POST /api/v1/projects/{id}/creative/agents/jobs/{job}/adopt-storyboard`: adotar storyboard em revisão M1.

A seção **Assistentes criativos · Ollama local** fica no workspace Creative Director existente. Exibe disponibilidade, jobs, erros, metadados, JSON e botões de adoção. A execução continua no servidor local após o navegador ser fechado; não depende de sessão do Codex. Os botões são desativados quando a função está desligada ou falta Brief/DNA. A ação de adoção exige revisão vigente e retorna 409 se os insumos mudaram. Aprovação de storyboard e revisão de artefato continuam humanas.

## Limites conhecidos

- Não há modelo de ilustração/cartoon instalado; `continuity` é textual. ComfyUI não foi instalado.
- As receitas M4 anteriores tinham de uma a quatro cenas. A nova receita POV permite seis cenas de até 30 s no canvas vertical. Ela representa objetos por vetores; não cria personagem ilustrado nem voz narrada. A revisão humana do storyboard e do vídeo continua obrigatória. O planejador `motion` devolve uma sugestão, não uma composição pronta; o compilador valida receita, assets e snapshot antes do render.
- A Biu não oferece uma API de prioridade/estado integrada aqui. O teste de uso simultâneo com a Biu não foi realizado.
- Cancelamento de trabalho em andamento ainda não interrompe a chamada síncrona ao Ollama; jobs enfileirados seguem o cancelamento da fila existente. Falha ou interrupção do worker permanece visível no job.
- O sistema não substitui checagem factual, direitos, revisão editorial nem publicação humana.
