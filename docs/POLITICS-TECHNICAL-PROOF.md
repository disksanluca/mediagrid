# Prova técnica local de Política para Instagram

O script [`scripts/prove_official_politics_pipeline.py`](../scripts/prove_official_politics_pipeline.py)
recebe um ID de proposição **escolhido pela pessoa operadora**. Ele usa uma base
SQLite isolada, consulta a API oficial da Câmara, importa a pauta, cria as
alegações pendentes, gera voz Windows local e renderiza um MP4 9:16 via
Remotion/FFmpeg. Confere status de jobs, hashes, codecs, duração e bloqueio da
revisão/exportação. Não aprova alegações nem publica conteúdo.

Execução neste host em 23/10/2026:

```powershell
.venv\Scripts\python.exe -m scripts.prove_official_politics_pipeline 2648811 `
  --node 'C:\Users\SP0097A\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
```

O PL 5650/2026 foi escolhido apenas para esta prova, sem recomendação editorial.
O registro oficial consultado é
[Câmara dos Deputados — PL 5650/2026](https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2648811).
O dado pode mudar após a captura. A prova local ignorada pelo Git está em
`data/rea-proof/politics-20261023T192648Z-55a673ea/` e não viaja com um clone.

| Verificação | Resultado |
| --- | --- |
| Projeto e origem | `QC`, `OFFICIAL_SOURCE` |
| Fonte usada | URL oficial, consulta `2026-10-23T19:26:49Z`, SHA-256 `ca02b3a010afcc1df38c37411829574b0d2f2ed7ac39569b8086f6e47db018f2` |
| Alegações | 3 em `REVIEW_REQUIRED` |
| Worker | `VOICE` e `RENDER` em `SUCCEEDED` |
| MP4 | H.264/AAC, 1080×1920, 43,13 s; SHA-256 `850ec8e5e365e6ef2164308ff5f0844b8be87a09e81229d7b50aaa5838da091e` |
| Voz | WAV local de 42,12 s; `volumedetect` no MP4: média −23,3 dB, pico −4,5 dB |
| Gate editorial | `POST /review` sem aprovar alegações retornou 409; `GET /export` retornou 409 |

Foram extraídos e inspecionados os quadros em 2, 17 e 38 segundos. O texto e a
fonte cabem no quadro sem corte visível, mas a composição tem cartões estáticos
e muito espaço vazio. Há áudio mensurável e continuidade de duração; não foi
feita escuta humana integral da narração. Este MP4 prova o pipeline e o bloqueio
editorial, **não** prova neutralidade, clareza jornalística, ritmo, qualidade
criativa ou que o vídeo esteja pronto para Instagram. O próximo refinamento
visual deve manter o registro da fonte e a revisão de alegações.
