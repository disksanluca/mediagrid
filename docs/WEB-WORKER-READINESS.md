# Web/VPS sem GPU — auditoria de prontidão

Estado: **não implantável como produto web**. Esta branch inicia o Marco 10 com
um bloqueio de configuração explícito; ela não afirma que a fila remota ou a
autorização por recurso já funcionam. O desktop local continua em SQLite.

## O que existe

- FastAPI e Next compartilham a interface com o desktop. A API possui sessão
  de administrador e bloqueio de origem; isso é uma única conta, sem
  `owner_id` ou tenant por canal/projeto/asset.
- SQLAlchemy aceita URL PostgreSQL e `psycopg[binary]>=3.2,<4` consta das
  dependências. A CI executa migração Alembic até 0009, claim concorrente e
  backup/restauração com PostgreSQL temporário. Não há VPS escolhido nem prova
  de operação com dois hosts persistentes.
- A fila usa a tabela `jobs` e `FOR UPDATE SKIP LOCKED` no claim. Há lease,
  heartbeat e fence de conclusão; `RENDER`, legendas, cortes, Football Edit e 3D
  promovem seus MP4s temporários somente após o fence; a voz promove o WAV e o
  digest do roteiro após o fence. Ainda faltam cancelamento
  de subprocesso remoto, token revogável
  de dispositivo, transporte autenticado de inputs/artefatos e reconciliação
  após queda entre rename e commit, ou entre as duas trocas da voz. Proxy e outros jobs de mídia ainda
  escrevem arquivos compartilhados antes do fence. Os arquivos estão no disco local do host da
  API; o desktop não pode acessá-los de forma autenticada por saída.
- O worker local agora recusa modo não local. No modo servidor a API só inicia
  com credenciais, URL pública HTTPS, PostgreSQL explícito, `DRY_RUN=true` e
  IA paga desligada. A chave `MEDIAGRID_SERVER_EXPERIMENTAL=true` ainda é
  exigida para testes isolados; o padrão é falhar antes da migração. Isso evita
  executar um worker de mídia no VPS sem GPU ou expor o protótipo por acidente.
- Jobs de mídia criados em modo servidor ficam `WAITING_FOR_WORKER`; requisições
  repetidas não geram duplicatas e retry de falha volta ao mesmo estado. O
  status de ingestão e os eventos registram a espera. O Editor não oferece a
  configuração de Blender do servidor. Uma alteração do storyboard 3D cancela
  o job antigo em espera. Nenhum job passa a `QUEUED` sem um worker remoto
  autorizado, que ainda não existe.

## Contrato necessário antes de um VPS

1. Autorizar cada rota e arquivo por proprietário. Migrar canais, projetos,
   assets, revisões e jobs com `owner_id` e testar acesso cruzado negado.
2. Ampliar a prova PostgreSQL da CI para hosts separados, falhas de conexão e
   rollback operacional; manter backup restaurável. Usar URL
   `postgresql+psycopg://...` conforme a
   [documentação oficial do dialeto](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
3. Registrar worker desktop com token revogável e capacidades. Claim atômico
   por capacidade com lease/heartbeat e idempotência; sem worker compatível,
   estado `WAITING_FOR_WORKER` em vez de sucesso ou fila sem consumidor.
4. Expor somente manifestos tipados e assets autorizados por download curto,
   verificar SHA-256 no desktop, executar localmente, carregar resultado com
   hash/FFprobe e confirmar no servidor antes de `SUCCEEDED`. Não aceitar
   comandos shell remotos.
5. Testar ponta a ponta sem GPU no servidor e com worker Windows de saída,
   inclusive perda de conexão, retry, conflito de revisão, cancelamento,
   vazamento entre usuários e restauração de DB+assets.

Nenhum host, conta, custo mensal, domínio ou armazenamento externo foi
escolhido ou ativado. Esta etapa não altera publicação manual nem instala uma
nova versão no PC do usuário.

O teste de job de voz em modo servidor cobre deduplicação e retry; o teste 3D
cobre cancelamento após revisão e promoção quando Blender local é configurado.
A CI PostgreSQL prova migração e backup/restauração em um serviço temporário.
Não foi executado web end-to-end com VPS e worker Windows remoto.
