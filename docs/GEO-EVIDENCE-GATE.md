# Geo: evidência por cena e revisão humana

## Estado implementado

O Radar consulta a [API de Localidades do IBGE, versão 1.0.0](https://servicodados.ibge.gov.br/api/docs/localidades), rota `GET /api/v1/localidades/municipios/{id}?view=nivelado`, sem credencial ou serviço pago. O import guarda a URL oficial, hora da consulta e SHA-256 do recorte normalizado dos campos usados no roteiro. Cria três cenas e três alegações vinculadas, cada uma em `REVIEW_REQUIRED`. O trecho de apoio identifica os nomes de campos e valores devolvidos pela API; não é uma citação textual inventada.

A resposta por município não informa data de publicação. `published_at` agora aceita `null`; `source_checked_at` registra a consulta, sem tratá-la como publicação. A migração `0010_geo_claim_source_dates` preserva as datas de fontes anteriores e não altera aprovações. `apps.api.migrate` faz backup do SQLite existente antes de aplicar revisões pendentes; ainda convém guardar uma cópia externa dos dados reais. O rollback para `0009` é bloqueado se existir alegação sem data de publicação, porque o schema anterior exigia esse valor.

Novas revisões de canais Geo, Politics e Trends exigem alegações aprovadas e URLs na revisão. Um Geo importado de fonte oficial também exige cobertura de todas as cenas e texto da alegação correspondente à narração atual. Alterar fonte/trecho remove a hora da consulta do registro editado. Alterar roteiro ou timeline invalida aprovações pertinentes. Exportar um projeto aprovado antes deste gate continua possível em Geo/Trends se o review antigo ainda corresponde ao vídeo/EDL e não havia ledger. Uma nova revisão entra no gate.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe -m ruff check .
.\node_modules\.bin\tsc.cmd --noEmit -p apps/web/tsconfig.json
cd apps/web
node ..\..\node_modules\next\dist\bin\next build
```

Uma prova vertical isolada, sem aprovar alegações ou publicar, pode ser feita com `python scripts/prove_official_geo.py --municipality-id 3550308`. Requer acesso à API do IBGE, Windows System.Speech, FFmpeg, Node e dependências travadas do Remotion. Os arquivos ficam em `data/geo-proof/<timestamp>/` (ignorado pelo Git): `source.json`, `evidence.json`, SQLite e MP4. O script confere hash da resposta, jobs, estado QC, bloqueio de export e FFprobe H.264/AAC 1080×1920. Não é aprovação editorial nem de voz.

Prova executada em 23/10/2026: `data/geo-proof/20261023T204617Z/evidence.json`. Município 3550308, fonte IBGE consultada ao vivo, snapshot SHA-256 `8dc371530de5b1fba4495bd2e1a8c1b45470206e56076219f8e33ca4bdc55bc6`. Voz e render `SUCCEEDED`, três alegações pendentes, projeto `QC`, export `409`. MP4 de 26,0 s, 1080×1920, H.264/AAC, SHA-256 `f053570beae021f7be853a38987f7ea82c0cee9b178422c84a5264ddc459c151`. O áudio não é silencioso (`mean_volume` -24,2 dB, `max_volume` -5,2 dB); a qualidade da locução não recebeu revisão auditiva humana. Frames em 2 s e 13 s foram inspecionados: tipografia e fonte legíveis, mas os cartões de texto são visualmente simples; esta prova não é aceitação criativa.

## Limites e integrações

- **REAL:** import IBGE online, API/SQLite local, migração, ledger, revisão, worker de voz/render e export manual bloqueado até aprovação.
- **PAPER:** avaliação editorial da atualidade da divisão regional e adequação do roteiro; exige pessoa revisora.
- **MOCK:** mídia audiovisual sintética usada apenas em testes de integração. Não há mídia própria/licenciada do usuário para provar cortes de terceiros ou publicação.
- **Custos:** consulta pública sem cobrança conhecida e processamento local. Nenhum VPS, serviço pago ou postagem foi ativado.
