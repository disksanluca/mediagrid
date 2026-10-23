# Cancelamento de trabalhos na fila

No Control Room, o botão **Cancelar** aparece somente para jobs `QUEUED` ou
`WAITING_FOR_WORKER`. A API `POST /api/v1/jobs/{job_id}/cancel` faz a transição
atômica para `CANCELLED`, registra `JOB_CANCELLED` com o estado anterior e grava
o horário de conclusão. O worker busca apenas jobs `QUEUED`; portanto, um job
cancelado não inicia ao reiniciar o desktop. Repetir a chamada para o mesmo job
já cancelado retorna o estado existente sem outro evento.

Se o worker já reclamou o job, a API retorna HTTP 409. A interface não oferece
cancelamento para `RUNNING`: interromper FFmpeg, Remotion, ASR ou Blender no
meio exigiria uma operação cooperativa de cada worker e limpeza de artefatos.
Não se afirma que um processo em execução tenha sido parado.

Para `PROXY`, o estado de ingestão do asset muda para `CANCELLED`; o arquivo
original permanece no armazenamento. **Repetir** recoloca um job cancelado na
fila e atualiza o estado do proxy. Jobs `FAILED` usam a mesma ação. A nova
tentativa limpa horários, lease e resultado anteriores, preservando a contagem
de tentativas para o limite existente.

## Verificação

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_job_cancellation.py
.venv\Scripts\python.exe -m ruff check apps/api/routes/jobs.py tests/test_job_cancellation.py
cd apps/web
..\..\node_modules\.bin\tsc.cmd --noEmit
```

Os testes cobrem cancelamento idempotente em fila e espera, proteção do lease
de um job já em execução, estado de proxy sem apagar o asset e nova tentativa.
Para verificar
manualmente, deixe o worker parado, enfileire um job, abra Control Room,
clique **Cancelar**, reinicie o worker e confira que o job permanece
`CANCELLED`. Faça um backup dos dados locais antes de testar com um projeto
real, como em outras operações do desktop.

Não há migração de banco nem variável nova em `.env.example`. REAL: API,
SQLite, evento de auditoria e ação React. PAPER: operação com dois workers
remotos concorrentes não foi validada neste incremento. MOCK: nenhum. Custo
de API paga: zero. Sem deploy, publicação ou instalação no PC do usuário.
