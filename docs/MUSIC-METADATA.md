# Música: ficha com proveniência MusicBrainz

## Escopo entregue

O Radar pesquisa grupos de lançamentos na API MusicBrainz e abre o registro
original antes da importação. Um canal `music` pode importar um registro para um
projeto SQLite `knowledge`, com três cenas editáveis: identidade/créditos, primeira
data cadastrada e limites dos direitos. O registro importado preserva URL,
instante da consulta e SHA-256 dos campos normalizados. Há uma alegação por cena
no ledger de revisão. O Render usa os mesmos props que a prévia e compõe cartões
originais no Remotion, com fonte e identificador visíveis. O worker existente gera
voz local e MP4; exportação manual depende de aprovação humana das alegações,
fatos, direitos e artefato vigente. Edição de narração exige atualizar alegações e
render novamente.

Isto é uma **ficha de metadados**, não uma crítica musical ou vídeo de performance.
Nenhuma capa, gravação, trecho, letra ou áudio de obra é obtido do MusicBrainz.
Sem material com direitos comprovados, a saída usa cartões e voz local.

## Protocolo e limites

- [API MusicBrainz v2](https://musicbrainz.org/doc/MusicBrainz_API): busca e lookup
  de `release-group`, resposta JSON e `inc=artist-credits` no lookup.
- [Limitação de taxa](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting):
  cliente com User-Agent identificável e média máxima de uma requisição por
  segundo. A API local serializa chamadas neste processo e espera 1,1 s entre
  elas. Uma implantação com múltiplos processos precisará de limitador compartilhado.
- [Licença de dados](https://musicbrainz.org/doc/About/Data_License) e
  [base de dados](https://musicbrainz.org/doc/MusicBrainz_Database): os campos
  centrais usados na ficha são disponibilizados sob CC0; dados suplementares
  podem ter outra licença. A ficha não herda licença sobre capa ou gravação.
- [Sobre MusicBrainz](https://musicbrainz.org/doc/About): a base cataloga
  metadados, sem armazenar as gravações. Identidade, créditos e data ainda
  precisam de conferência editorial; `first-release-date` pode ser parcial.

Consulta à documentação oficial em 24/10/2026. Cliente local `httpx 0.28.1`.
Timeout de 20 s, redirecionamentos desabilitados e limite de corpo de 200 KB.
Falha de rede, limite do provedor ou resposta inválida retornam erro explícito;
nenhum roteiro é criado com dados supostos. O endpoint de importação busca o
registro de novo, sem confiar na lista exibida no navegador.

## Verificação

No Windows com dependências bloqueadas instaladas, Node, voz SAPI e FFmpeg no
`PATH`:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_official_music.py
.venv\Scripts\python.exe -m ruff check apps/api/official_music.py apps/api/routes/music.py apps/api/render_plan.py tests/test_official_music.py
node node_modules/typescript/bin/tsc --noEmit -p apps/renderer/tsconfig.json
node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json
.venv\Scripts\python.exe scripts/prove_musicbrainz.py b29e94e7-0b0b-3a66-ab06-e02f8fa5054f
```

O último comando usa uma pasta/banco isolados em `data/music-proof/`, consulta o
MusicBrainz ao vivo duas vezes, cria projeto, executa worker de voz e render,
valida MP4 H.264/AAC com FFprobe, hash e entrega pela API, e exige `409` na
exportação antes da revisão. `evidence.json`, `source.json`, quadros e MP4 ficam
fora do Git. Não execute em uma base de produção. O usuário deve revisar o vídeo
inteiro e ouvir a voz antes de aprovar para publicação.

## Integrações e dados

- **REAL:** MusicBrainz ao vivo, API FastAPI, SQLite, ledger de alegações,
  UI React, voz SAPI Windows, render local Remotion/FFmpeg, revisão e exportação
  manual do pipeline existente.
- **PAPER:** aprovação editorial real, qualidade artística da narração e uso de
  mídias com licença; não realizados nesta prova técnica.
- **MOCK:** as respostas `httpx.MockTransport` são usadas apenas nos testes
  automatizados. Nenhuma resposta simulada é rotulada como resultado de produção.
- Banco: apenas tabelas existentes (`projects`, `knowledge_claims`, jobs e
  revisões); sem migração. `.env.example`: sem variável nova. API paga: custo
  monetário zero nesta execução; CPU/energia não mensuradas como custo financeiro.
- Publicação: somente pacote manual após revisão; nenhuma postagem ou deploy.

O teste de instalação Windows dessa ficha ainda deve ser repetido no build que
inclui esta branch. Também faltam material autorizado, revisão auditiva humana,
pesquisa musical contextual e um motor capaz de produzir conteúdo criativo sobre
a obra além dos metadados.

## Prova local de 24/10/2026

`data/music-proof/20261024T004908Z/evidence.json`: registro **Clube da
Esquina**, MBID `b29e94e7-0b0b-3a66-ab06-e02f8fa5054f`, snapshot SHA-256
`a9cfdd3d27b77873725b38006459350072d1086793772e665984791b0cda049c`.
Foram criadas três cenas e três alegações `REVIEW_REQUIRED`. Voz e render
terminaram `SUCCEEDED`; projeto permaneceu `QC`; exportação retornou `409`.
MP4 em `data/music-proof/20261024T004908Z/renders/7b80a6b4-cb06-49e4-ab96-2f93af6208d1.mp4`,
SHA-256 `99ead1344669b93bb955d4aa7c9e87bf4d686a1354184c019e79c7829b97d3b8`.
FFprobe: H.264/AAC, 1080×1920, 29,2 s. FFmpeg `volumedetect`: média -23,9 dB,
pico -4,7 dB (prova de áudio presente, não de qualidade de locução). Quadros
das três cenas foram extraídos e inspecionados; título, artista, data, fonte e
alerta de direitos aparecem legíveis. O ritmo, a pronúncia, a criatividade e
as alegações não receberam revisão humana.

Na interface Next local com SQLite isolado (`data/ui-music-proof`), o Radar
pesquisou **Clube da Esquina** ao vivo, diferenciou o álbum de 1972 de outros
registros homônimos, criou o canal Música e abriu o projeto no Editor. A
timeline e o ledger exibiram três cenas e três alegações. A prévia Remotion
carregou. A lista de fontes mostra o horário somente no registro efetivamente
consultado; a página “About” é referência sem data de consulta inventada.
Servidores e aba de prova foram encerrados depois da verificação.

Validação de código: `pytest -q tests` **126 passed, 1 skipped** em execução
isolada; o skip é o teste Blender opt-in. Depois do ajuste de streaming com
limite de resposta, `pytest -q tests/test_official_music.py` **2 passed**,
`ruff check .`, typecheck web/renderer, `next build` 16.3.8 e
`git diff --check` passaram. Uma primeira suíte paralela a outro pytest
teve duas falhas de configuração do mesmo banco SQLite de testes; a execução
isolada concluiu sem falhas.
