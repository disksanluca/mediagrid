# Prova local de pauta Política com fonte oficial

## O que esta etapa melhora

Uma ementa da Câmara que começa com “Altera a Lei…” agora destaca no cartão o
assunto presente no trecho “para…” do próprio registro. Ementas mais longas são
divididas em cenas e alegações menores, preservando o texto integral para
conferência humana. O título visual abrevia o texto, mas não cria um fato novo.
O Editor continua permitindo alterar roteiro, legendas e mídia antes do render.

## Reprodução e evidência de 23/10/2026

No Windows, com as dependências locais instaladas:

```powershell
.venv\Scripts\python.exe scripts/prove_official_politics.py --proposal-id 2648811
```

O script usa banco e diretório de dados isolados em `data/politics-proof/`;
consulta ao vivo o [PL 5650/2026 na Câmara](https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2648811).
Ele salva `source.json`, a base SQLite, `evidence.json`, WAV e MP4 local. Não
aprova alegações nem projeto, não exporta e não publica. A ausência de rede,
voz Windows, Node, Remotion ou FFmpeg faz a prova falhar explicitamente.

Na execução `20261023T202416Z`, o plano persistiu quatro cenas de origem
`OFFICIAL_SOURCE` e quatro alegações em `REVIEW_REQUIRED`. Jobs VOICE e RENDER
terminaram em `SUCCEEDED`; o projeto ficou em `QC` e a API negou exportação
com HTTP 409. Download do MP4 pela API coincidiu com o hash do job. FFprobe:
H.264/AAC, 1080×1920, 43,133 s, SHA-256
`34b76652684fd1aeeaa1463a2a41a3048bf6605866865f41e263a0a038dc2070`.
O título da cena principal passou a “O reajuste anual dos valores do Programa
Bolsa Família”, extraído da ementa. Quadros em 13 s e 29 s foram inspecionados:
texto legível, composição tipográfica ainda simples e bastante espaço vazio.

## Limites

Esta é uma prova de fluxo e rastreabilidade, não uma aprovação editorial.
O áudio não recebeu avaliação auditiva humana completa. A fonte pode mudar
depois da consulta e os quatro trechos requerem leitura do registro original,
checagem de contexto e aprovação explícita antes do ZIP manual. A prova não
contém filmagem ou trilha de terceiros: o usuário ainda não forneceu material
próprio ou licenciado. Custo de API paga: zero. Não houve VPS, instalação do
novo build no PC, publicação ou merge.

Não há alteração de schema nem nova variável de ambiente nesta etapa.
