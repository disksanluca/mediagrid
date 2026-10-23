# Pauta política da Câmara — evidências por cena

No Radar, a pessoa pode pesquisar PLs na API pública da Câmara e escolher um
registro específico. Uma pauta genérica como “Política” continua sendo apenas
um esboço e não pode ser renderizada sem narração revisada. A importação do
registro gera um roteiro vertical editável, com origem `OFFICIAL_SOURCE`,
referência, horário da consulta e SHA-256 dos campos usados. Não afirma que
uma proposição virou lei nem que o resumo cobre todo o debate político.

Em **Nova produção**, selecionar um canal Política agora oferece primeiro a
pesquisa no Radar. Isso evita criar um plano genérico por acidente quando a
pessoa ainda não tem uma pauta nem fontes. A opção de rascunho com briefing
próprio permanece disponível: a API grava novos projetos editoriais de
Política como `knowledge`, e a revisão/exportação exigem pelo menos uma
alegação com fonte aprovada. O mesmo gate de revisão se aplica a projetos
políticos `video` criados por versões anteriores; seus dados não são alterados.
O editor permite cadastrar e revisar as alegações. Renderizar um rascunho
factual ainda não significa que ele está pronto para publicação.

O import agora cria um projeto `knowledge` e uma alegação `REVIEW_REQUIRED`
para a identificação/data, cada trecho da ementa e a situação, quando a API
fornece data e descrição válidas. Os trechos de ementa têm tamanho limitado
para caber no editor; as evidências de identificação e situação mostram nomes
de campos estruturados da API, sem fingir uma citação em prosa. Ausência de
data de apresentação, data futura ou resposta incompleta impede o import.

O Editor já mostra cada alegação e sua fonte. A pessoa deve abrir o registro,
comparar o trecho, conferir contexto e data e aprovar cada alegação. Editar a
timeline invalida aprovações anteriores. O gate de revisão/export exige todas
as alegações aprovadas e as URLs no registro final; o pacote inclui o ledger
e o hash da revisão. A fonte pode mudar depois da consulta: o SHA-256 registra
o que foi usado para criar o plano, mas não arquiva a resposta original nem
substitui uma nova leitura humana antes de publicar.

Contrato consultado em 23/10/2026: [OpenAPI da Câmara](https://dadosabertos.camara.leg.br/api/v2/api-docs),
versão do serviço `0.4.346` informada em 21/10/2026. Os endpoints
`GET /proposicoes` e `GET /proposicoes/{id}` retornaram HTTP 200 neste host,
com os campos `dataApresentacao`, `ementa` e `statusProposicao` esperados. A
documentação oficial avisa que a API é incompleta e pode mudar; o código
limita a resposta a 1 MB, não segue redirecionamentos, não pede credenciais e
falha com 503 quando a consulta não é confiável. Nenhuma fonte de terceiros,
mídia ou serviço pago foi ativado.

Validação: `uv run pytest -q tests/test_official_politics.py
tests/test_knowledge_claims.py` cobre import, persistência, revisão e export,
datas inválidas e esgotamento da ementa em alegações. O teste de revisão usa
um arquivo sintético apenas para exercitar o gate; não prova qualidade do
vídeo, neutralidade editorial, direitos de imagens ou aprovação humana.
