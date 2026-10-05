# MediaGrid V1: plano técnico desktop

Este plano combina o blueprint mestre MediaGrid com a alteração oficial de 5 de outubro de
2026. A alteração troca a distribuição da V1: **o aplicativo Windows é o produto**. O
FastAPI continua como serviço interno; o usuário não precisa abrir navegador ou terminal.
Os módulos editoriais, renderização, canais e conectores do blueprint continuam no escopo.

## Decisões de arquitetura

1. **Janela:** Tauri 2 hospeda o painel React/TypeScript existente. O Next.js é exportado como
   arquivos estáticos para o desktop. Não haverá servidor Next.js no uso instalado.
2. **Processos:** um gerenciador no processo Tauri inicia e encerra o FastAPI e o worker, mede
   saúde e grava logs. Serviços opcionais são detectados; a ausência deles não impede abrir.
3. **Banco:** SQLite é a escolha para um computador e um usuário. Dispensa instalador e serviço
   de PostgreSQL, preserva transações e permite backup nativo. A camada SQLAlchemy mantém a
   opção de PostgreSQL para uma fase de servidor.
4. **Dados:** por padrão em `%LOCALAPPDATA%\MediaGrid\Data`, com opção de escolher outra pasta.
   `C:\MediaGrid\Data` exigiria permissões de administrador em algumas instalações. Nenhum
   caminho de usuário fica embutido no executável.
5. **Rede:** API escuta apenas em `127.0.0.1` numa porta escolhida pelo aplicativo. O painel
   recebe essa porta por comando Tauri. Modo LOCAL não usa APIs pagas.
6. **Mídia e modelos:** binários locais e modelos ficam fora do executável principal. O assistente
   apresenta tamanho, destino e progresso antes de baixar opcionais. Renderização precisa de
   Remotion, Node, FFmpeg e Chromium localmente; a distribuição deve levar os binários essenciais.
7. **Backup:** arquivos `.mgrid` com manifesto, banco consistente e seleção explícita de mídias,
   renders e modelos. A restauração terá validação de versão, espaço, integridade e confirmação.

## Sequência de entrega e critérios

| Etapa | Entrega funcional | Evidência para concluir |
| --- | --- | --- |
| 1 | Tauri abre painel em janela, splash, inicia Core e worker, fecha processos | Executável Windows abre sem navegador; teste de ciclo de vida |
| 2 | Assistente inicial, perfil de hardware, pasta de dados, diagnóstico | Instalação limpa cria banco e detecta recursos reais |
| 3 | Pacote Windows com Python, Node/Remotion, FFmpeg e navegador de render | Vídeo com áudio renderiza em instalação limpa, sem ferramentas de desenvolvimento |
| 4 | Biblioteca, canais e pipeline editorial dentro da janela desktop | Fluxo completo até MP4 e revisão, dados persistem após reiniciar |
| 5 | Modelos opcionais locais com progresso, stop/restart e reparo | Baixar, usar e desinstalar sem chamadas pagas |
| 6 | Editor de timeline e preview, QC, review, publishers e analytics reais | Testes de ponta a ponta por plataforma e validação humana |
| 7 | Exportar/restaurar `.mgrid`, instalador e desinstalador | Migração entre dois computadores Windows de teste |

Não marcar a V1 como pronta antes de validar as etapas aplicáveis numa instalação Windows
limpa. A publicação e análises dependem das APIs das plataformas e das permissões de cada
conta; permanecerão desativadas até estarem realmente integradas.

## Limitações técnicas verificadas no ambiente de desenvolvimento

Este workspace de desenvolvimento é Linux e não contém Rust, Cargo, PowerShell nem Windows.
Ele valida os componentes web/Python, mas não executa um `.exe`. A compilação e teste do
aplicativo instalado devem rodar em Windows, por CI e teste humano numa instalação limpa.
WhisperX, Chatterbox e ComfyUI têm modelos grandes e requisitos de GPU diferentes; não serão
simulados nem marcados como disponíveis quando estiverem ausentes.
