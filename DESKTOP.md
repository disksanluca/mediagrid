# Desenvolvimento desktop

O código Tauri está em `apps/desktop`. O painel Next.js é exportado estaticamente para
`apps/web/out`. Na execução desktop, o Tauri inicia o Core e o worker por processos locais;
o painel recebe a porta interna via comando Tauri. Splash, ícone e bandeja do sistema já
integram a estrutura da janela. O fechamento normal do aplicativo encerra os processos.

## Build de desenvolvimento Windows

Requer Node.js 22+, Rust/Cargo, uv, Python 3.12 e WebView2. No repositório:

```powershell
npm ci
uv python install 3.12
uv sync --frozen
.\scripts\build-desktop-sidecar.ps1
npm run dev --workspace @mediagrid/desktop
```

O build instalável é `npm run build --workspace @mediagrid/desktop`. O workflow
`.github/workflows/desktop-windows.yml` executa a compilação em Windows e guarda o artefato
para testes. Os dados de desenvolvimento ficam em `%LOCALAPPDATA%\MediaGrid\Data`; logs do
Core e worker em `Logs`. Uma instalação limpa no Windows ainda precisa ser testada antes de
distribuir o executável ao usuário final.

## Estado da integração

O painel, a API, o banco e a fila já têm caminhos locais reais. O worker de render ainda chama
o Remotion pelo ambiente de desenvolvimento; o empacotamento de Node, Remotion, FFmpeg e
Chromium para instalação limpa é uma etapa pendente. Ollama, WhisperX, Chatterbox e ComfyUI
continuam opcionais e devem ser detectados antes de mostrar ações de instalação ou início.
Nenhuma funcionalidade ausente deve ser exibida como concluída.
