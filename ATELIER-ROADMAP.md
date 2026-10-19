# MediaGrid Atelier OS — auditoria e plano incremental

Base auditada: `disksanluca/mediagrid` em `7dcc7d7`. O pacote Atelier OS é a referência
visual; seu HTML contém dados e interações de demonstração. Os dados de produção continuam
vindo do Core local e do SQLite.

## Estado verificado

| Camada | Implementado | Próxima verificação ou lacuna |
| --- | --- | --- |
| Tauri / Windows | Janela, splash, bandeja, sidecar Core e worker, instalador NSIS | Recompilar e testar esta branch em instalação Windows limpa |
| React / Next | Sete espaços Atelier, setup e controles reais preservados | Comparar todas as telas e teclado com o protótipo em 1440 × 900 e 1000 × 900 |
| FastAPI / SQLite | Canais, projetos, EDL, assets, jobs, eventos, backup | Criar migrações versionadas antes de novas colunas ou tabelas; `create_all` não altera schema existente |
| Workers | Recuperação de jobs, voz/transcrição locais opcionais, render e backup | Testar retomada e dados após reiniciar o instalador atualizado |
| Render | Remotion com cinco movimentos por cena; FFmpeg e QC do MP4 | Timeline multifaixa, mídia real, legendas sincronizadas e presets versionados |
| Motores | Football, Music, Geo, Clips, Politics, Trends com guia e checagens; busca de PLs da Câmara para Politics | Outras fontes reais, validação de alegações, perfis e prompts por canal |
| Entrega | Revisão humana e ZIP manual com MP4 e manifesto | Conectores oficiais por plataforma, credenciais protegidas e estados de falha |
| Testes | Python, lint, typecheck, build web e render curto | Smoke do instalador desta branch, restore e teste em outro computador |

## Próximas fatias de implementação

1. **Persistência de pesquisa e direitos:** migrations versionadas, fontes, alegações,
   ligação entre assets e cenas e trilha de revisão. Bloquear exportação quando um asset
   realmente usado tiver licença ausente ou restrita.
2. **Editor e motion:** EDL multifaixa, seleção e movimentação de clipes, preview do mesmo
   scene graph do render, presets paramétricos por canal e testes de MP4 com áudio.
3. **IA local e autopilot:** descoberta e configuração explícita de Ollama e modelos
   opcionais, limites de hardware, jobs canceláveis e política de aprovação humana.
4. **Integrações:** conectar APIs oficiais e permissões por plataforma. Mostrar `NOT_CONNECTED`
   e oferecer pacote manual quando a conta ou permissão não estiver disponível.
5. **Insights:** ingestão de métricas oficiais com origem e data; nenhuma métrica fictícia.
6. **Release Windows:** build NSIS desta branch, instalação limpa, render, backup/restore,
   reinício e migração de dados. Integrar à `main` somente após os gates aplicáveis.

O sistema permanece local por padrão, sem VPS obrigatória. Downloads de modelos e APIs de
terceiros são opcionais. O ZIP de entrega manual não publica automaticamente.

## Correções em andamento após uso real

- O instalador encontrado no computador de teste é de 5 de outubro de 2026 e antecede esta
  branch. É necessário instalar o próximo build para validar as alterações de interface e fluxo.
- O plano de um tema curto continua sendo apenas uma estrutura editorial. Um briefing com três
  a cinco linhas concretas agora gera narrações editáveis a partir do texto fornecido, sem
  acrescentar fatos. A origem do plano fica identificada como `OUTLINE`, `BRIEF_BASED`,
  `LOCAL_AI` ou `MANUAL`. Voz e render ficam bloqueados para esboços até que todas as narrações
  tenham sido revisadas e salvas.
- O Editor permite retomar um projeto criado mesmo se a primeira geração do plano falhar.
  Alterações não salvas bloqueiam a geração de voz e o render.
- Um erro de bloqueio no backup diário foi visto no log do Windows. Os arquivos temporários
  agora têm nomes únicos e uma falha de backup não encerra o worker; ele tenta de novo depois.
- A detecção de voz no Windows agora independe da presença de reconhecimento de fala. A voz
  portuguesa instalada é selecionada explicitamente quando disponível. Um piloto isolado de
  Política para Instagram produziu MP4 vertical de 31 segundos com áudio e vídeo.
- O roteiro oficial testado tinha 35 segundos estimados, enquanto a fala sintetizada durou
  45 segundos. O render agora alonga as cenas conforme a fala e acrescenta margem final para
  evitar corte. Nova voz ou novo render invalida o vídeo e a aprovação anteriores. O vídeo de
  Política exibe a fonte institucional, usa textos curtos sem cortar palavras e não mostra
  rótulos internos do renderizador.
- O Radar consulta os Dados Abertos da Câmara (`GET /proposicoes` e `GET /proposicoes/{id}`)
  para projetos de lei. Documentação oficial consultada em 19/10/2026: API v2, Swagger
  0.4.344, publicado em 18/08/2026. Consulta HTTPS sem chave, com limite local de 10 itens,
  prazo de 15 segundos e resposta de até 1 MB. O identificador, a ementa, o último status
  registrado, o link e o horário de consulta entram no plano editável. A busca não funciona
  offline; um plano já salvo continua acessível. A situação pode mudar e requer revisão.
  Ref.: https://dadosabertos.camara.leg.br/swagger/api.html
- Esta fatia usa o JSON `plan` existente; não altera tabelas SQLite nem exige migração.
- Ainda faltam pesquisa com fontes para outros motores, mídia real por cena, roteiro de IA local com revisão,
  publicação oficial e validação manual do novo instalador. Esses itens impedem declarar a
  versão desktop como produto completo.
