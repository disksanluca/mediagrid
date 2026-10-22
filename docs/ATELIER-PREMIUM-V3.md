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
| Remotion / FFmpeg | Cinco transições (`impact`, `slide`, `cut`, `zoom`, `fade`) e MP4 com áudio | Seis artes conceituais do kit não correspondem a seis presets implementados; timeline multifaixa falta |
| Motores | Football, Music, Geo, Clips, Politics e Trends; Politics consulta PLs da Câmara e Geo consulta localidades do IBGE | Fontes para Football, Music e Trends, recorte de Clips e checagem automática de alegações faltam |
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
  edição continua no Editor persistido. Planos `OUTLINE` aparecem como
  **Estrutura a completar**, sem sugerir um roteiro finalizado.
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
4. Windows: o [CI da primeira etapa](https://github.com/disksanluca/mediagrid/actions/runs/39552495101)
   compilou NSIS, instalou o app no runner, iniciou Core/SQLite/worker e gerou
   MP4 com vídeo e áudio. Ainda faltam backup/restauração e teste humano em
   outra máquina Windows antes de integrar à `main`.

Não há VPS obrigatória. Nenhum merge, publicação direta ou integração paga faz
parte desta etapa.

## Etapa funcional: mídia real por cena (21 de outubro de 2026)

- O Editor grava `asset_id` em cada cena do plano e do EDL. JPEG, PNG, WebP e
  MP4 importados na Biblioteca podem ser selecionados; a tela de texto continua
  disponível. A interface permite corrigir status de direitos, criador, licença
  e permissão comercial de arquivos já importados. Cenas podem ser adicionadas
  e removidas (mínimo duas); rascunhos com narração vazia podem ser salvos, mas
  não geram voz ou vídeo até serem preenchidos. A mídia escolhida tem prévia
  de imagem ou vídeo no Editor.
- A API rejeita mídia inexistente, ausente, restrita ou de direitos desconhecidos;
  mídia licenciada exige nome de licença. A fila verifica novamente os direitos
  antes de renderizar. O worker confere SHA-256, copia apenas os arquivos usados
  para uma pasta temporária isolada e passa essa pasta ao Remotion. Imagens cobrem
  o quadro; vídeos ficam sem áudio e repetem conforme a duração da cena. A pasta
  temporária é removida no fim do trabalho.
- Não houve alteração de schema SQLite: a associação fica nos campos JSON
  existentes `plan` e `edl`. Projetos antigos sem `asset_id` continuam com as
  cenas de texto. O render pode falhar se um arquivo importado não for de fato
  decodificável no formato declarado; a falha fica visível no job.
- A revisão humana aceita uma legenda editável. O pacote manual inclui
  `caption.txt` quando a legenda foi registrada, além de `video.mp4` e
  `manifest.json`; projetos aprovados antes desta etapa mantêm seus pacotes
  antigos sem legenda.
- Verificado localmente: 39 testes Python passaram, Ruff passou, typechecks Web
  e Renderer passaram, build Next passou. Um render real de quatro segundos em
  1080×1920 usou uma imagem vermelha e um MP4 verde; a leitura de pixels confirmou
  as cores em cenas diferentes. O smoke do instalador Windows foi ampliado para
  importar e renderizar esses dois tipos de mídia e testar revisão sintética e
  exportação manual no CI. O [primeiro smoke de mídia instalada](https://github.com/disksanluca/mediagrid/actions/runs/39696317921)
  passou, incluindo conferência de pixels e áudio. O smoke com exportação ainda
  precisa de execução na revisão correspondente, e o aplicativo instalado no
  PC do usuário continua na versão anterior.
- A interface de produção foi conferida em 1440×900, 1280×800 e 1000×900, sem
  overflow horizontal; no Editor, a seleção de mídia e o salvamento foram
  exercitados contra a API e o SQLite de validação. O Radar consultou ao vivo a
  lista de PLs de 2026 e abriu uma proposição pela API oficial da Câmara.
  Adição e remoção de cenas foram persistidas no projeto; uma imagem importada
  carregou na prévia do Editor em 1000×900. A atribuição à Câmara agora permanece
  no vídeo mesmo quando o roteiro oficial recebe edição humana.
- Um fluxo local isolado importou ao vivo o PL 5642/2026, preservou a URL oficial
  após edição, gerou voz pelo sintetizador Windows, processou os jobs VOICE e
  RENDER pelo worker e produziu MP4 de 24,53 segundos com faixas de vídeo e áudio
  em estado `QC`. Um quadro extraído mostrou a atribuição à Câmara. O roteiro
  desse teste foi abreviado para acelerar a renderização; ele não recebeu
  revisão editorial humana e não é conteúdo pronto para publicação.

## Etapa funcional: Geo com fonte oficial (21 de outubro de 2026)

- O Radar pesquisa municípios na [API de Localidades do IBGE v1.0.0](https://servicodados.ibge.gov.br/api/docs/localidades), sem chave. A pesquisa ocorre apenas por ação do usuário; baixa o catálogo de municípios (cerca de 2,4 MB na validação) e filtra nome, inclusive sem acentos. A importação consulta novamente o identificador escolhido, evitando depender de uma lista antiga.
- A importação cria projeto Geo local com três cenas editáveis, plano, roteiro, EDL, URL oficial e hora da consulta. Narração e cartões usam somente município, UF e regiões imediata, intermediária e grande região retornadas pelo IBGE. O vídeo preserva a atribuição “Fonte: IBGE” depois de edição humana. Não acrescenta população, área, mapa ou estatística sem fonte.
- O usuário ainda precisa verificar a divisão territorial atual, escolher imagens ou vídeos com direitos registrados, gerar voz, renderizar e aprovar a revisão. Não houve mudança de schema SQLite. Falha de rede retorna erro visível e não cria projeto vazio.
- Validação local: 41 testes Python e Ruff passaram; busca e detalhe de São Paulo foram consultados ao vivo no IBGE. O typecheck e build Web passaram. Em uma base SQLite isolada, o Radar criou o canal Geo, buscou São Paulo, importou o projeto e abriu o Editor; a narração editada foi salva e os botões de voz/render voltaram a ficar disponíveis. O instalador e o fluxo Geo completo ainda precisam passar no CI da revisão antes de qualquer instalação no PC do usuário.
- Um teste adicional na mesma base isolada editou as três narrações, gerou voz pt-BR pelo Windows e processou o render com Remotion e FFmpeg. O MP4 resultante tem 12,81 s, faixas de vídeo e áudio e estado `QC`; um quadro extraído confirmou “Fonte: IBGE”. O worker agora localiza o CLI do Remotion instalado na raiz do workspace npm, além do runtime empacotado do Tauri. O primeiro render de desenvolvimento falhou porque `npm` não estava no PATH deste ambiente; após configurar o Node e o diretório do renderer, o trabalho seguinte foi concluído. Esta validação técnica usou frases abreviadas e não equivale à aprovação editorial.
- O smoke do instalador Windows agora também invoca o serviço de backup empacotado e restaura o arquivo `.mgrid` em outra pasta descartável do runner, conferindo SQLite, MP4 e mídias. A checagem só estará confirmada quando o CI desta revisão passar; a instalação real do usuário permanece intocada.

Próxima validação: executar o instalador no CI com imagem, clipe, voz e exportação;
conferir Geo no aplicativo instalado e completar os motores sem fonte real. A
atualização local só será instalada após os fluxos funcionais serem validados.
Publicação direta permanece sem integração real.

## Etapa funcional: recorte de MP4 por cena (21 de outubro de 2026)

- O Editor permite definir início e fim em segundos para um MP4 próprio ou licenciado. A API exige intervalo válido e mídia de vídeo, persiste o recorte no plano e no EDL e repete a faixa escolhida durante a cena. Áudio do clipe permanece mudo sob a narração; a voz local continua a faixa principal.
- O worker confere a duração real do MP4 antes de renderizar e marca o job como falho, com erro legível, se o intervalo ultrapassar o arquivo. Projetos sem recorte mantêm a reprodução anterior. Não há migração SQLite.
- Validação local: 42 testes Python, Ruff, typechecks Web/Renderer e build Next passaram. Um MP4 de teste vermelho no primeiro segundo e verde no segundo foi importado com direitos próprios; duas cenas selecionaram de 1 a 2 segundos. O render real com voz terminou em `QC`, gerou MP4 de 8,80 s com vídeo e áudio, e o pixel extraído do início saiu verde (`RGB 3,77,2`). No navegador, o Editor mostrou os intervalos persistidos e a prévia do MP4 respondeu com HTTP 206. O smoke Windows passou a enviar o recorte no EDL, mas precisa de CI da revisão para confirmar o instalador.
- O Studio agora abre no motor do projeto mais recente (ou do primeiro canal, se ainda não houver projeto). Isso evita mostrar “Sem projeto” quando a única produção pertence a Clips, Geo ou Política. A escolha manual de outro motor continua disponível na faixa inferior.
