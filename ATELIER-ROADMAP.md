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
| Motores | Football, Music, Geo, Clips, Politics, Trends com guia e checagens | Fontes reais, validação de alegações, perfis e prompts por canal |
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
