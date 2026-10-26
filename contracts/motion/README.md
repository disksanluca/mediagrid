# Motion contracts — M4.A–D

Contratos compartilhados pelo compilador Creative Director e interpretador Remotion.
O preset motion_scene_v1 é aceito somente na EDL derivada e validada pelo compilador;
a edição livre da EDL continua bloqueada. JSONs e fixtures não aprovam conteúdo.
Provas reais, API, UI e limites: [entrega M4](../../docs/M4_COMPLETE_MOTION_ENGINE.md).

## Fonte de verdade

- apps/api/motion_contracts/models.py: Pydantic estrito, versionado, campos fechados.
- validation.py: semântica do grafo/tempo/bindings e conferência **somente leitura**
  com CreativeStoryboard, CreativeDNA e EDLV2 existentes.
- canonical.py: limite de entrada JSON e mg-canonical-json-v1.
- registry.py: receitas locais versionadas, SHA e igualdade do grafo expandido.
- generated/: JSON Schemas (Draft 2020-12), tipos TS e fixtures TS gerados.
- recipes/: índice e versões 1.0 (referência), 1.1 e 1.2 (suportadas). Nenhum script em receitas.
- fixtures/{sports,music,geo}/: composition, storyboard, DNA, EDL v2 e contexto de teste.

O nome de cada schema gerado corresponde à classe Python:
MotionScene.schema.json (motion_scene_v1), MotionComposition.schema.json
(motion_composition_v1), MotionRecipe.schema.json e RegistryIndex.schema.json.

## Validar localmente

Na raiz do repositório:

    .venv/Scripts/python.exe scripts/generate_motion_contracts.py --check
    .venv/Scripts/python.exe -m pytest -q tests/test_motion_contracts.py
    node node_modules/typescript/bin/tsc --noEmit -p contracts/motion/tsconfig.json

Para atualizar artefatos após editar o modelo Python:

    .venv/Scripts/python.exe scripts/generate_motion_contracts.py

O gerador não usa npm/download/modelo/rede. Não editar TS/JSON Schema manualmente.
TypeScript representa os tipos de entrada; ranges, regex, ciclos, hashes e relações
temporais não são todos expressáveis em TS. JSON Schema valida a estrutura, mas
não substitui os validadores Python de semântica e contexto. Esse limite é explícito
nos artefatos gerados. O teste de geração detecta divergência.

## Contratos e fronteiras

1. Ler bytes externos com read_json (máximo 2 MiB, chaves duplicadas/NaN/Infinity/
   profundidade >24 rejeitados), depois MotionComposition.model_validate.
   schema_version é obrigatório em cenas, envelope, receitas e índice; sem fallback implícito.
2. Resolver a receita por load_recipe(id, version), a partir do índice local.
3. Chamar validate_binding com EDL, storyboard, DNA, revisão/snapshot e metadados
   de assets/claims **obtidos de estado confiável pelo servidor**.
4. Receber CONTRACT_VALID e render_supported=false: o validador puro não autoriza render.
   A API M4.C aplica aprovação/direitos/hash físico e compila MotionSceneSpec para o worker.

Essas funções puras não autenticam usuário, não consultam CreativeReview, não atestam
licença nem leem bytes de mídia. O adapter implementado em apps/api/creative/engine.py
autentica pelas rotas existentes, valida aprovação/direitos/hash físico e fornece o contexto.
Passar asserções do cliente como contexto confiável seria erro de integração.

O relatório retorna bordas em frames e arredondamento dos cues, sem criar timeline.
A EDL continua sendo a autoridade de start_ms/duration_ms. RecipeScene declara
required_duration_ms como requisito da receita; não muda o shot aprovado.

## Vocabulário v1 entregue

Nodes: group, text, shape, mask, path_follower, image, video, particle, light_sweep.
Câmera tem translação XYZ, rotate_z e focal_length; rotação X/Y fica fora desta versão.
Paths são pontos de polygon/polyline; comandos de curva/SVG/XML não são aceitos.
Keyframes: position, scale, rotate_z, opacity, progress e draw_progress, conforme o
tipo de node. Tempo discriminado: time={kind:"ms",at_ms:...} ou
time={kind:"cue",cue_ref:...,offset_ms:...}. Easing linear/hold/cubic_in_out/cubic_out
ou cubic_bezier com controles em [0,1]; overshoot somente por pontos explícitos.

Bindings de texto vêm de shot_field/approved_claim_field; cor e fonte vêm do DNA.
Assets são IDs/hash/metadados de imagem/áudio/vídeo, sem URL ou caminho.
Imagens/vídeos e sons precisam estar nos assets do shot aprovado ao validar o contexto.
Fontes do DNA ainda precisarão de resolução/licença/medição no futuro pipeline.

Tipos aceitos não significam primitivas implementadas visualmente. Nenhum node deste
módulo desenha pixels. O antigo exemplo conceitual do ADR usa outras formas abreviadas;
estas fixtures e o schema gerado são a especificação executável do M4.A.

## Limites aplicados

3–30 s, 30 FPS, 1080×1920 / 1920×1080 / 1080×1080; até 12 shots.
128 nodes expandidos por cena, 512 no total, hierarquia 6, até 2 máscaras aninhadas.
32 keyframes/propriedade, até 8 animações/node, 8192 pontos globais; 64 cues globais.
512 pontos/path, 4096 pontos globais. 64 partículas/cena, contadas no orçamento expandido.
Máximo simultâneo por cena: 4 imagens, 2 vídeos, 8 sons e 2 light sweeps.
32 bindings de mídia, 128 MiB/asset e 256 MiB no total dos slots.
Imagens até 4096², vídeos até 3840² / 30 FPS, fontes sonoras até 2 canais / 96 kHz.
Os metadados são asserções; o probe/hash físico pertence ao adapter posterior.
SoundCue usa ganho >0 e ≤1, como sound_v1 existente. Evento silencioso usa sound=null.

Frames: F(t)=(30*t+500)//1000 em milissegundos absolutos. Shots usam [F(start),F(end)).
Cue precisa estar dentro de frame exibido; keyframe final pode estar na borda final
como endpoint de interpolação. Duas keyframes no mesmo frame são rejeitadas.
Atividade de filhos herda o intervalo do pai quando omitida; intervalo explícito
não pode escapar do pai. Animação usa tempo local do shot, mesmo em grupos.

Câmera usa uma checagem conservadora do envelope Z de cada ancestral e das keyframes,
com margem >32 do plano próximo. Não há física nem avaliação acumulativa de frames.
A validação pode recusar trajetória que seria segura por correlação de movimentos;
a garantia conservadora é preferível até existir um avaliador temporal testado.

## Canonicalização e SHA

mg-canonical-json-v1 é um formato do projeto, **não RFC 8785/JCS**.
Validar e expandir defaults Pydantic antes do hash. UTF-8, chaves ordenadas, arrays
preservados, sem espaços; texto sem normalização Unicode implícita.
Números finitos JSON-safe (|x|≤2^53−1), até seis casas decimais, sem notação
exponencial; -0 vira 0 e 1.0 vira 1. Não arredondar dados silenciosamente.
Escapes JSON de strings seguem json.dumps(ensure_ascii=False). SHA-256 em lowercase.

Hash de receita exclui somente seu próprio sha256; mantém versão, defaults e graphs.
O índice fixa ID/versão/SHA. Alterar conteúdo exige nova versão revisada e alteração
explícita do índice; o loader não atualiza arquivos nem aceita importação dinâmica.
Modelos frozen não tornam listas imutáveis em memória: verificações revalidam os
dados e recomputam SHA, e não confiam em objeto alterado via model_copy/lista.

## Natureza das fixtures

- Sports: tipografia em profundidade, grupo screen space, recorte e faixa diagonal.
- Music: capa central, grupo orbital e aparição por cue musical.
- Geo: região ficcional, path, marcador e rótulo de fonte demonstrativa.

As diferenças são estruturais, não uma alegação de resultado visual validado.
IDs, revisões, claims, metadados de mídia e snapshot são sintéticos e servem apenas
a testes. Os hashes de “assets” são hashes de strings identificadoras de fixture,
não de WAV/PNG/MP4 existentes. Não autorizam download/render/publicação nem atestam
direitos. Hashes das receitas, por outro lado, são verificações reais dos documentos.

O pacote de contratos não depende de banco. A integração M4.C utiliza a migração
0013_motion_artifact_review, documentada no relatório M4; nenhuma nova variável.
M4.D acrescenta gradientes fechados (2–8 stops), glow limitado, tracking e seleção
de uma linha exata do texto aprovado. Barlow, Space Grotesk e IBM Plex Sans são
incorporadas com OFL. Defaults novos omitidos preservam hashes de receitas anteriores.
O Autonomous Visual Reference Scout permanece apenas no roadmap do ADR.
