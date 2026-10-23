# Motion Ad: briefing estruturado

## Fluxo disponível

Em **Nova produção → Motion Ad**, escolha um canal e o formato vertical ou
horizontal. Forneça produto, público, gancho, problema, benefício, chamada para
ação e cor. A API `POST /api/v1/motion-ads/projects` cria quatro cenas com a
cópia recebida e dois cartões `motion_card_v1` no EDL v2. O briefing inicial e
seu SHA-256 ficam no plano; edições do Editor criam revisões e mantêm os
cartões alinhados ao benefício e à chamada para ação.

O MediaGrid não pesquisa o produto nem acrescenta promessas. O criador pode
editar cenas, prévia, cartões, voz, som e mídia na interface existente. O
worker local usa o mesmo pipeline Remotion/FFmpeg dos outros projetos. A
revisão exige fonte e aprovação por alegação do gancho, problema e benefício,
além de atestados de fatos e direitos. A entrega é um pacote manual. Não há
publicação automática nem métricas de campanha.
Cadastrar uma alegação mantém o projeto em `motion_ad`; editar o roteiro
revoga aprovações anteriores de alegações.

## Verificação

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_motion_ad_brief.py
.venv\Scripts\python.exe -m ruff check apps/api/motion_ad.py apps/api/routes/motion_ads.py tests/test_motion_ad_brief.py
.venv\Scripts\python.exe scripts/proof_motion_ad.py
```

Os testes usam texto e mídia sintéticos. Sem material autorizado do usuário,
um render de teste comprova o pipeline técnico, não aptidão editorial ou
direitos para publicar. Não há migração de banco ou variável nova; o projeto
usa `Project.plan`, `ProjectRevision`, jobs e verificações de revisão atuais.

## Prova local de 23/10/2026

Em banco e pasta isolados `data/motion-ad-proof` (ignorados pelo Git), o
script criou um anúncio fictício, gerou voz SAPI local e concluiu um render
Remotion/FFmpeg. FFprobe confirmou H.264/AAC, 1080×1920 e 17,0 s. SHA-256 do
MP4: `a79c450c1c001806d15019d1bb1f74b5547979387e74d4002af99b447e87f891`.
O volume médio medido foi −25,1 dB, pico −5,5 dB. Quadros em 9,5 s e 14 s
foram inspecionados: benefício e chamada para ação legíveis, dentro da tela.
O projeto permaneceu `QC`; exportação retornou 409 sem alegações aprovadas.
Isso comprova fluxo técnico, não qualidade de locução nem aprovação editorial.
O teste visual do Editor e do formulário React em 1440×900, 1280×800 e
1000×900 não mostrou rolagem horizontal; em 1000×900 o formulário rola
verticalmente e o botão Criar permanece alcançável. Uma criação pelo
formulário gerou um segundo projeto real no banco isolado.

O smoke Windows instalado agora também chama `POST /motion-ads/projects`,
confere o briefing salvo, as quatro cenas, os dois cartões no EDL e na prévia,
gera voz local e MP4 H.264/AAC e exige que a exportação sem aprovação siga
bloqueada. Esse gate usa texto sintético e banco descartável do runner. O
resultado depende do CI desta branch; não equivale à instalação no PC do
usuário nem a uma aprovação criativa.

O projeto usa Remotion 4.0.532 do lockfile. A [licença oficial do
Remotion](https://www.remotion.dev/docs/license/pricing) permite uso gratuito
para indivíduos e equipes de até três pessoas, mas prevê licença paga para
organizações maiores. Nenhuma licença paga foi ativada nesta etapa; confirme
o enquadramento da operação antes da distribuição comercial.
