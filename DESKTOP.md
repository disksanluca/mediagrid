# Desenvolvimento desktop

O código Tauri está em `apps/desktop`. O painel Next.js é exportado estaticamente para
`apps/web/out`. Na execução desktop, o Tauri inicia o Core e o worker por processos locais;
o painel recebe a porta interna via comando Tauri. Splash, ícone e bandeja do sistema já
integram a estrutura da janela. O fechamento normal do aplicativo encerra os processos.
O diagnóstico técnico também pode ser executado com `uv run python -m apps.api.doctor`.

## Build de desenvolvimento Windows

Requer Node.js 22+, Rust/Cargo, uv, Python 3.12 e WebView2. No repositório:

```powershell
npm ci
uv python install 3.12
uv sync --frozen
.\scripts\build-desktop-sidecar.ps1
npm run dev --workspace @mediagrid/desktop
```

Para o build instalável, execute `.\scripts\build-desktop-runtime.ps1` e depois
`npm run build --workspace @mediagrid/desktop`. O workflow
`.github/workflows/desktop-windows.yml` compila em Windows, guarda o instalador NSIS e testa
sua instalação, início de Core/worker e renderização de MP4 com vídeo e áudio em pasta isolada.
Os dados ficam em `%LOCALAPPDATA%\MediaGrid\Data` por
padrão; logs do Core e worker em `Logs`. O arquivo `runtime.json` nessa pasta registra a porta
local ativa enquanto o aplicativo está aberto.

Na aba **Sistema**, é possível exportar um `.mgrid` com banco e configurações e selecionar
biblioteca, vídeos e modelos locais. A restauração verifica manifesto, checksums e integridade
do SQLite antes de trocar os dados. O diretório anterior é preservado ao lado do novo.

## Estado da integração

O painel, a API, o banco e a fila já têm caminhos locais reais. O instalador leva Node,
Remotion, FFmpeg, FFprobe e Chromium para renderizar sem ferramentas de desenvolvimento ou
download durante o uso. O teste automatizado de instalação e renderização passou no Windows;
ainda é necessário validar interface, backup/restauração e modelos opcionais em um PC Windows de
uso real. Ollama,
WhisperX, Chatterbox e ComfyUI continuam opcionais e devem ser detectados antes de mostrar
ações de instalação ou início.
Nenhuma funcionalidade ausente deve ser exibida como concluída.
