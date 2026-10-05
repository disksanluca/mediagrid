# MediaGrid V1 no Windows

O painel funciona no seu computador. Não é preciso contratar hospedagem, criar conta em nuvem
ou configurar IP público. O endereço `http://localhost:3000` só abre no próprio computador
enquanto o script de inicialização estiver em execução.

## Instalar uma vez

1. Instale **Node.js 22 ou mais recente**, **uv** e **FFmpeg**. Se o `winget` estiver disponível,
   execute no PowerShell:

   ```powershell
   winget install --id OpenJS.NodeJS.LTS -e
   winget install --id astral-sh.uv -e
   winget install --id Gyan.FFmpeg -e
   ```

   Feche e reabra o PowerShell após a instalação para atualizar o `PATH`. Os comandos
   `node`, `uv`, `ffmpeg` e `ffprobe` precisam funcionar antes do próximo passo.
   O `uv` instala o Python 3.12 do projeto.
2. Abra o PowerShell na pasta MediaGrid e execute `uv python install 3.12`.
3. Dê dois cliques em **Iniciar-MediaGrid.cmd**. Na primeira vez, ele cria `.env` com modo
   `LOCAL`, instala as
   dependências, baixa uma vez o navegador do renderizador e prepara o banco SQLite em
   `data/mediagrid.db`. A instalação inicial precisa de internet; o uso diário não.
4. O navegador abre **http://localhost:3000** automaticamente. Nas próximas vezes, use o mesmo arquivo `.cmd`.

Como alternativa ao arquivo `.cmd`, rode `.\scripts\bootstrap.ps1` e
`.\scripts\dev.ps1` no PowerShell. Se ele bloquear os scripts, execute antes
`Set-ExecutionPolicy -Scope Process Bypass` nessa janela.

Mantenha a janela aberta durante o uso. `Ctrl+C` encerra painel, API e worker. A pasta
`data/` contém sua biblioteca, banco, vídeos, voz, transcrições e cópias diárias do banco;
faça também sua própria cópia dessa pasta em um disco externo.

## Recursos de IA e áudio, sempre locais

- **Plano:** funciona sem IA. Para melhorar as narrações, instale Ollama localmente e execute
  `ollama pull llama3.2` uma vez. O MediaGrid só se conecta ao Ollama em `127.0.0.1`.
- **Voz:** usa o sintetizador offline do Windows. Em Produção, gere a voz antes de renderizar;
  o MP4 renderizado depois inclui o áudio. A voz e a pronúncia dependem das vozes instaladas
  no Windows.
- **Transcrição:** usa o reconhecimento offline instalado no Windows. Para mais precisão,
  instale `whisper-cli` do whisper.cpp e baixe um modelo para seu disco. Defina
  `WHISPER_MODEL_PATH` no `.env` apontando para o arquivo local. O painel mostra se há um
  mecanismo disponível. Para o reconhecimento do Windows, instale o pacote de fala do idioma
  em Configurações > Hora e idioma > Idioma e região. O primeiro uso do Ollama ou whisper.cpp exige obter modelos uma vez;
  depois a execução pode permanecer sem internet.
- **Automação:** o worker faz backup diário do SQLite e processa a fila local. Cada canal pode
  habilitar renderização automática após gerar um plano; ela vem desligada.

Nenhum serviço pago ou em nuvem é chamado pela configuração padrão. Publicação em redes
sociais não faz parte do fluxo automático da V1.
