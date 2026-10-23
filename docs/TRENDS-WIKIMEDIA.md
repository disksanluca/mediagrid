# Trends: sinal de leitura com escopo explícito

## Fonte e contrato

O Radar consulta, só após ação do usuário, a [lista diária de páginas mais vistas da Wikimedia Analytics API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html) para `pt.wikipedia.org`, `all-access`. Os [dados da API são CC0 1.0](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html); o cliente envia User-Agent identificável. A fonte pode não disponibilizar ainda um dia recente: [404 também significa dados não carregados](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/troubleshooting.html), por isso a UI recomenda um dia concluído e devolve indisponibilidade explícita. Não há chave nem assinatura paga.

`GET /api/v1/trends/wiki-top?day=AAAA-MM-DD&query=...` devolve no máximo 20 páginas de conteúdo do relatório, com posição e visualizações originais. O filtro de título é local depois da consulta; não representa os temas mais buscados na internet. `POST /api/v1/trends/projects` recebe canal, dia e identificador da página, consulta a API novamente e cria projeto local `knowledge` com três cenas editáveis, roteiro, EDL, URL, dia observado, hora da consulta e SHA-256 do recorte usado. As três alegações começam em `REVIEW_REQUIRED` e a revisão exige aprovação, cobertura de cenas e texto alinhado ao roteiro. O terceiro trecho explica a limitação da métrica e aponta à [definição de page view](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/concepts/page-views.html); sua data de consulta permanece vazia porque o import não abre essa página.

O número mede pedidos de conteúdo da Wikipédia em português. Não mede pessoas únicas, intenção de busca, tendência geral nem audiência no Instagram. O MediaGrid não baixa imagens, áudio ou texto dos verbetes e não atribui licença de mídia com base na licença dos dados da API. Qualquer mídia adicionada precisa de direitos próprios; fatos adicionais no roteiro precisam de novas fontes e revisão humana. Datas observadas e consultadas não são tratadas como datas de publicação.

## Como executar e verificar

1. Abra Radar, crie ou selecione um canal Trends, escolha um dia já carregado e consulte o relatório. Filtre o título se desejar.
2. Abra a URL oficial de uma linha e crie o roteiro. Confira cenas e alegações no Editor; edite antes de gerar voz e MP4.
3. Para uma prova técnica isolada no Windows, execute `.\.venv\Scripts\python.exe scripts/prove_official_trends.py --day 2026-10-20 --article Benito_di_Paula`. Requer internet, voz System.Speech, FFmpeg e Node/Remotion instalados. O script grava SQLite, resposta, hashes, MP4 e FFprobe em `data/trends-proof/<timestamp>/` (ignorado pelo Git), confirma jobs e export bloqueado. Ele não aprova alegações nem publica.

Testes: `.\.venv\Scripts\python.exe -m pytest -q tests`; `.\.venv\Scripts\python.exe -m ruff check .`; `.\node_modules\.bin\tsc.cmd --noEmit -p apps/web/tsconfig.json`; em `apps/web`, `node ..\..\node_modules\next\dist\bin\next build`.

## Prova local de 23/10/2026

A consulta real do dia 20/10/2026 encontrou `Benito_di_Paula` com 17.372 visualizações e posição 7 no relatório diário de `pt.wikipedia.org`. O recorte de fonte registrado tem SHA-256 `67f3dd228b6372915f442d3f72eb8d3bc747e6d84743ea554424fce645ecd700`. O projeto `a4be17ac-bdee-4988-a852-a3cb3cb4fe55` completou os jobs locais de voz e render; o arquivo ignorado pelo Git em `data/trends-proof/20261023T211007Z/renders/` tem SHA-256 `89a085a6b64bc3dd42d2aa316f64f50291c0790a10a71d90443dc7008a007bd2`, 34,27 s, 1080×1920, H.264/AAC. A duração aumentou em relação ao plano de 26 s para acomodar a voz.

Os frames de 2 s, 17 s e 29 s foram inspecionados; o primeiro foi corrigido para mostrar título, número e data. `ffmpeg volumedetect` confirmou sinal de áudio no primeiro render (média −23,8 dB, pico −5,1 dB). Isso comprova mídia técnica, não qualidade de locução aprovada por audição. O texto em cartão ainda é simples e precisa de trabalho criativo. As três alegações continuam `REVIEW_REQUIRED`; exportação bloqueada, sem aprovação humana e sem publicação.

**REAL:** Wikimedia online, API, SQLite, Editor, voz/render local, revisão/export manual. **PAPER:** qualidade narrativa, contexto da página, conferência factual e direitos humanos. **MOCK:** bytes de mídia sintética apenas nos testes automatizados. Sem migração ou variável nova em `.env.example`, sem VPS, serviço pago ou postagem. Custo de API paga zero; custo de CPU e rede depende da máquina e não foi medido nesta etapa.
