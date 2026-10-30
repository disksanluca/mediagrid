# MediaGrid — validação desktop + navegador móvel

Base: `codex/m4-complete-motion-engine` (`5a559c8`), trabalho em
`codex/mobile-companion-validation`. O M4 continua em PR draft #48. Esta etapa
não faz merge, não modifica a instalação principal nem lê seu SQLite.

## Arquitetura testada

- O desktop Windows continua sendo o host de FastAPI, SQLite, Next e worker.
  Remotion e FFmpeg executam no PC. Não há VPS, worker remoto ou app nativo de
  Android/iOS nesta etapa.
- `scripts/mobile-companion.ps1` usa exclusivamente uma pasta em
  `data/mobile-companion/<workspace>`, com API e painel presos a `127.0.0.1`.
  Tailscale Serve oferece HTTPS **somente na rede privada**; o script nunca
  chama Funnel. O telefone precisa entrar na mesma rede Tailscale e o PC
  precisa permanecer ligado com o terminal aberto.
- `MEDIAGRID_PUBLIC_URL` em modo `LOCAL` exige origem HTTPS `*.ts.net`, senha
  de pelo menos 16 caracteres e segredo de sessão de pelo menos 32 caracteres.
  A API aceita apenas a origem configurada para requisições autenticadas com
  escrita. A porta do painel local é explícita, inclusive para o proxy Next.
- A sessão é HTTP-only e Secure no acesso HTTPS. Projetos, jobs, direitos,
  revisão e hashes continuam na API e no banco existentes.

## Prova executada em 29/10/2026

1. `uv run python scripts/proof_motion_engine.py --run mobile-validation-20261029 --only sports --approve-synthetic-storyboards`
   concluiu o pipeline real em SQLite isolado. O job
   `28be1a6c-d0d1-5a93-822c-b2d6af6d4043` terminou `SUCCEEDED`; o
   storyboard permaneceu aprovado, a revisão do artefato ficou
   `REQUEST_REVIEW` e o endpoint de vídeo respondeu. Tempo medido do job:
   107,634 s neste host.
2. `ffprobe` do arquivo
   `data/m4-complete-proof/mobile-validation-20261029/sports/sports-motion.mp4`:
   H.264 1080×1920, 30 FPS, 360 frames, 12,011 s, áudio AAC. SHA-256:
   `68514fb7d7a718ea59025382d50a0f98241a3e0cbaa1105063e2a4b081c9e35c`.
3. Em navegador com viewport 390×844, a primeira configuração abriu. O primeiro
   clique foi bloqueado por HTTP 403 porque a porta web `3180` ainda não era
   reconhecida. Após parametrizar a porta, a configuração salvou, o Studio
   abriu o projeto persistido, e Creative Director → Revisão exibiu o MP4,
   hash, status e link de download. O elemento `<video>` informou
   `readyState=4`, 12,011 s e 1080×1920. A raiz da página mediu 375 px para
   viewport de 390 px, sem overflow horizontal do documento.
4. A página Studio agora usa o artefato M4 validado pela rota de revisão como
   vídeo real, em vez de afirmar que um projeto com MP4 não foi renderizado.
   A Motion Library consulta a API e mostrou as seis receitas suportadas,
   incluindo Sports, Music e Geo 1.1.0/1.2.0.
5. Tailscale Serve respondeu com a tela de login HTTPS privada, e o serviço
   local exigiu login. Durante a sessão, o perfil Tailscale ativo do PC mudou;
   o URL temporário deixou de resolver. O script agora detecta essa troca e
   encerra os serviços. O serviço e os listeners de teste foram desligados.

## Testes e limites

- `uv run pytest -q tests`: 280 passaram, 1 ignorado (Blender opcional).
  Após o ajuste final no login privado,
  `uv run pytest -q tests/test_web_readiness.py tests/test_product_flows.py tests/test_local_workflows.py`:
  19 passaram. Uma execução paralela anterior de pytest foi descartada porque
  as duas instâncias usaram o mesmo arquivo SQLite de teste; a repetição serial
  passou.
- `uv run ruff check .`: passou.
- `node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json`:
  passou; renderer também passou.
- `node ../../node_modules/vitest/vitest.mjs run` em `apps/web`:
  11 testes passaram.
- Build Next 16.3.8: passou no ensaio privado e no painel de prova.
- Testes de autenticação cobrem URL inválida, ausência de credenciais, origem
  externa, cookie Secure e escrita permitida apenas pela origem configurada.
- **Não houve teste físico no telefone:** o usuário confirmou que Tailscale
  ainda não está instalado nele. O ensaio de 390 px foi em navegador de PC.
  Uploads grandes, captura de mídia, playback com áudio no alto-falante do
  celular e uso prolongado fora de casa ainda precisam de teste no aparelho.
- A prova usa mídia sintética original. Ela não valida os seis motores com
  material publicável, nem torna o aplicativo inteiro “100% pronto”.

## Como executar e verificar

No terminal Windows com `uv`, `node`, FFmpeg e Tailscale disponíveis, na raiz
do repositório:

```powershell
.\scripts\mobile-companion.ps1 -WorkspaceName review
```

O comando pede uma senha, cria/reutiliza apenas a pasta de teste indicada,
mostra o URL HTTPS privado e mantém API, worker e painel ativos. `Ctrl+C`
encerra o acesso privado. O script recusa configurações Tailscale Serve
preexistentes para não sobrescrevê-las. Se o perfil Tailscale mudar durante a
sessão, confira a configuração Serve no perfil anterior antes de reutilizá-lo.

Para revisar localmente o MP4 sintético deste ensaio, sem exposição de rede:

```powershell
.\scripts\review-motion-proof.ps1 -Run mobile-validation-20261029
```

No telefone, instale o cliente Tailscale oficial, conecte-o à **mesma rede
privada** do PC, abra o URL impresso pelo script, faça login e confirme criação
de projeto, prévia, render, revisão e download. Esse teste de aparelho é a
próxima porta de aceitação. Nenhuma publicação ou aprovação automática ocorre.

## Schema e integração

Sem migração Alembic ou mudança da EDL. A única nova configuração é a porta
web local permitida. Tailscale Serve é opcional e privado; nenhum serviço pago
foi ativado. O modo `SERVER`/VPS permanece experimental e não foi alterado.
