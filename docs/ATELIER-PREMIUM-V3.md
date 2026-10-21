# Atelier Premium v3 — auditoria e integração incremental

Base: `feat/atelier-os-incremental` em `a411a5f`; branch de trabalho:
`feat/atelier-premium-v3`. O pacote recebido é uma especificação visual e um
protótipo demonstrativo. Seus dados, imagens e interações não são uma fonte de
conteúdo ou de funcionalidades de produção.

## Auditoria da base

| Camada | Estado verificado | Limite atual |
| --- | --- | --- |
| Tauri | Janela Windows, splash, sidecars Core e worker, instalador NSIS | Novo instalador ainda precisa de teste manual em instalação limpa |
| React / Next | Sete ambientes, login, SetupWizard, formulários reais, editor, atalhos e modais | Shell antigo não correspondia ao v3; Settings não existia na navegação |
| FastAPI / SQLite | Autenticação local, canais, projetos, planos, assets, jobs, revisão e backup | Mudança futura de schema exige migrações versionadas |
| Workers | Fila local, voz/transcrição opcionais, render e backup | Recuperação após reiniciar o instalador atualizado precisa de verificação |
| Remotion / FFmpeg | Cinco transições (`impact`, `slide`, `cut`, `zoom`, `fade`) e MP4 com áudio | Seis artes conceituais do kit não correspondem a seis presets implementados; mídia de arquivo por cena e timeline multifaixa faltam |
| Motores | Football, Music, Geo, Clips, Politics e Trends; Politics consulta PLs oficiais da Câmara | Fontes para os demais motores e checagem automática de alegações faltam |
| Entrega | Revisão humana e pacote ZIP para publicação manual | Publicação direta e métricas de plataformas ainda não conectadas |

Antes das mudanças, `pytest` passou com 37 testes, Ruff passou, TypeScript passou e
o build Next passou. A base técnica mais recente era a branch funcional acima,
sete commits à frente de `main`; partir de `main` perderia funcionalidades já
implementadas.

## Primeira etapa implementada

- Tokens Premium v3, fontes offline Space Grotesk, DM Sans e IBM Plex Mono,
  navegação superior com oito ambientes, ícones Lucide, foco e atalhos existentes.
- Settings mostra perfil, pasta real de dados, estado da IA local, hardware,
  diagnóstico, controles de serviço Tauri e backup quando disponíveis.
- Studio usa canal, projeto, plano, cenas, status e MP4 do Core. Quando o MP4
  ainda não existe, apresenta uma **prévia editorial**, identificada como tal,
  sem arte conceitual ou vídeo fictício. A faixa de cenas seleciona cenas reais;
  edição continua no Editor persistido.
- Splash e cor de fundo Tauri seguem a nova paleta. APIs, banco e renderer não
  foram alterados nesta fatia; nenhuma migração é necessária.

As famílias tipográficas foram baixadas de `google/fonts/ofl` e acompanhadas dos
respectivos arquivos `OFL.txt` em `apps/web/public/fonts`. Fontes e interface
funcionam offline no Tauri; não há chamada ao Google Fonts durante o uso.

## Verificação visual

O protótipo e as capturas `studio-1672.png`, `studio-1000.png`, `editor-1672.png`,
`motions-1672.png` e `control-1672.png` foram inspecionados. O Studio real foi
comparado com o kit em 1440×900, 1280×800 e 1000×900. Uma base SQLite de
validação separada, ignorada pelo Git, continha apenas um canal de Política e
um plano `OUTLINE` criado pela API real. A automação de navegador confirmou oito
itens de navegação visíveis, fontes carregadas, ausência de overflow horizontal,
abertura de Settings e reabertura do projeto no Editor nas três resoluções. As
capturas locais estão em `data/premium-v3-visual/screenshots/` e não são assets
da aplicação.

## Próximas etapas

1. Motion Library: mostrar os cinco movimentos reais com prévia do próprio
   renderer; marcar conceitos adicionais como indisponíveis até implementá-los.
2. Control e Editor: aproximar a hierarquia visual do v3 sem perder jobs,
   revisão, EDL, render e exportação. Timeline multifaixa só após contrato e
   persistência reais.
3. Radar, Network e Insights: adaptar composição visual, preservando dados
   oficiais e estados vazios. Conectores externos continuam não conectados.
4. Windows: gerar NSIS da branch, instalar em máquina limpa, verificar abertura,
   serviços, render com áudio, backup e restauração antes de integrar à `main`.

Não há VPS obrigatória. Nenhum merge, publicação direta ou integração paga faz
parte desta etapa.
