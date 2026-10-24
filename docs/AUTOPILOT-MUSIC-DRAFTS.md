# Agendamento local de rascunhos musicais

Este incremento agenda **a criação de um rascunho**, nunca um render ou uma
publicação. No Radar Música, escolha um registro MusicBrainz e um horário local
entre 10 segundos e 30 dias no futuro. O worker do desktop consulta o registro
novamente quando o horário chegar. Se a fonte responder com dados válidos, cria
um projeto, três cenas e três alegações pendentes de revisão. A origem, a data da
consulta e o hash do snapshot ficam no plano. O projeto entra no Editor e só
segue para voz, render e exportação pelas ações e barreiras existentes.

## Contrato e operação

- `POST /api/v1/music/drafts/schedules`: `channel_id` de um canal Música,
  `release_group_id` UUID e `scheduled_at` ISO 8601 com fuso. A combinação
  canal, registro e instante é idempotente. Retorna `201` e o estado existente
  se a mesma solicitação for repetida.
- `GET /api/v1/music/drafts/schedules`: últimos 100 agendamentos locais.
- `POST /api/v1/music/drafts/schedules/{id}/cancel`: cancela `PENDING` ou
  `RUNNING`. Uma consulta em curso não pode criar projeto depois do cancelamento.
- `POST /api/v1/music/drafts/schedules/{id}/retry`: reativa uma falha, até o
  limite de três tentativas. A causa resumida fica no histórico de eventos;
  inspecione o log local quando necessário.

O estado passa por `PENDING` → `RUNNING` → `SUCCEEDED` ou `FAILED`; o usuário
pode chegar a `CANCELLED` antes da criação. O worker usa lease de 90 segundos,
token de posse e atualização condicional para impedir que uma tentativa vencida
grave um projeto. Projeto e estado `SUCCEEDED` são confirmados na mesma
transação. Após queda do processo, uma lease vencida pode ser retomada até a
terceira tentativa. O worker é consultado no ciclo local já existente e também
por `python -m workers.render.main --once`. A máquina precisa estar ligada,
com MediaGrid e worker em execução e rede disponível; o horário não é promessa
de execução com o computador desligado. Uma falha de rede aparece como
`FAILED`, sem roteiro inventado e sem retry automático imediato.

Modo `SERVER` responde `503` para estas rotas: não há agendador distribuído,
isolamento por proprietário ou worker remoto comprovado. Nenhum VPS, chave de
API paga ou cron externo é necessário no desktop. MusicBrainz continua sujeito
ao limite de média de uma chamada por segundo **por processo**; não execute
múltiplos workers desse tipo contra a API sem limitador compartilhado. Veja
[MUSIC-METADATA.md](MUSIC-METADATA.md) para fontes oficiais, versão `httpx`
e licença de dados consultadas em 24/10/2026. Áudio e capa de terceiros não são
obtidos por este recurso.

## Banco, migração e recuperação

`0011_music_draft_schedule` acrescenta `music_draft_schedules`, índices por
canal, horário, próxima tentativa e estado, unicidade da requisição e
referência única ao projeto criado. Não altera projetos anteriores. A atualização
local usa `python -m apps.api.migrate`, que mantém a rotina de backup do SQLite
antes de aplicar revisões. Faça também uma cópia externa do banco real antes de
atualizar o aplicativo. O downgrade é bloqueado se houver projetos criados por
agendamento para não apagar seu vínculo. `.env.example` não exige nova
variável; `MEDIAGRID_MODE=LOCAL` é necessário para o recurso.

## Verificação

Em checkout de desenvolvimento Windows, com `.venv`, Node, voz SAPI, FFmpeg e
FFprobe disponíveis:

```powershell
.venv\Scripts\python.exe -m pytest -q tests
.venv\Scripts\python.exe -m ruff check .
node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json
node node_modules/typescript/bin/tsc --noEmit -p apps/renderer/tsconfig.json
.venv\Scripts\python.exe scripts/prove_musicbrainz.py b29e94e7-0b0b-3a66-ab06-e02f8fa5054f --scheduled
```

O último comando usa banco e saída isolados em `data/music-proof`, consulta a
fonte ao vivo, confirma que a tarefa não roda cedo, espera o horário, executa o
worker real e depois solicita voz e render. A prova de 24/10/2026 está em
`data/music-proof/20261024T010324Z/evidence.json`: agendamento
`3b341069-4d8f-4cda-a520-88b30f9dedd7` concluído em uma tentativa,
projeto `e630371b-4ebf-45b3-9dff-f6dfd0deb10c`, snapshot SHA-256
`a9cfdd3d27b77873725b38006459350072d1086793772e665984791b0cda049c`.
MP4 H.264/AAC 1080×1920, 29,2 s, SHA-256
`99ead1344669b93bb955d4aa7c9e87bf4d686a1354184c019e79c7829b97d3b8`.
As três alegações ficaram `REVIEW_REQUIRED`, exportação recebeu `409` e nada
foi publicado. O mesmo hash da prova de render imediato indica saída binária
idêntica para esta fonte; isso não substitui a revisão humana de voz e fatos.

Validação local desta branch: suíte Python **129 passed, 1 skipped** em 84,76 s
(skip Blender opt-in); `ruff check .`, typecheck web/renderer, `next build`
16.3.8 e `git diff --check` passaram. Na interface web com banco isolado em
`data/ui-scheduled-music-proof`, o Radar pesquisou o álbum de 1972, agendou o
registro correto e exibiu `PENDING`, horário local e 0/3 tentativas. O botão
Cancelar mudou o estado para `CANCELLED`. Captura em
`data/ui-scheduled-music-proof/schedule-ui.png`. A primeira busca ao vivo
recebeu `503`; a segunda retornou os dez registros e o fluxo funcionou. A
prova de UI não substitui o smoke do instalador Windows desta branch.

**REAL:** agendamento e persistência local, consulta MusicBrainz, worker, projeto
e prova de MP4, revisão e bloqueio de exportação. **PAPER:** qualidade editorial,
direitos de mídia, instalação do novo build no PC do usuário. **MOCK:** respostas
HTTP substitutas apenas nos testes. Custo de API paga: zero; CPU, energia e
eventual rede não foram mensuradas como despesa financeira. Sem postagem
automática, serviço pago, deploy público ou mudança no banco do usuário.
