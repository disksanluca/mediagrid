# M4.A — Motion Composition Engine: contratos e validações

Data: 26/10/2026. **M4.A concluído localmente e entregue para revisão em PR draft.**
M4.B/C/D e Autonomous Visual Reference Scout permanecem fora da implementação.

## 1. Base auditada e limites da entrega

- Repositório: disksanluca/mediagrid; branch de implementação:
  codex/creative-m4-a-contracts, criada a partir da branch do PR draft #46,
  codex/creative-m3-2-final-polish.
- HEAD real conferido localmente e no GitHub:
  e6492adff3d134cea7431e322d235eb45e244f5f.
- CI da **base**, observada durante esta rodada:
  [Windows desktop build #98](https://github.com/disksanluca/mediagrid/actions/runs/40273441833)
  **success**; inicialmente estava em execução.
  [PostgreSQL migration smoke #37](https://github.com/disksanluca/mediagrid/actions/runs/40273441882)
  **success**. Estes resultados não são apresentados como CI do novo commit M4.A.
- ADR lido e confrontado com CreativeStoryboard/CreativeDNA, EDLV2, sound_v1,
  bridge M3 e renderer existentes. A arquitetura segue uma única EDL.
- Alembic heads: **0012_creative_direction**, único head; comando de inspeção,
  sem upgrade/downgrade no banco instalado.
- Python local 3.12.10, Pydantic 2.13.5, Node v24.19.0.
  Dependências e lockfiles existentes preservados.
- A aceitação humana da V2 Broadcast Final do M3.2 é uma referência provisória.
  Não registra aprovação de publicação, novos projetos ou artefatos.

O módulo novo é uma biblioteca de dados e validação. Não há endpoint, seleção de
receitas na UI, interpretador React, compilação para render ou job novo.
motion_scene_v1 **continua sendo recusado pela EDL de produção** até uma integração
posterior autorizada. Nenhum JSON desta entrega é um vídeo produzido.

## 2. Arquitetura e arquivos alterados

| Arquivos | Responsabilidade |
|---|---|
| apps/api/motion_contracts/models.py | Modelos Pydantic fechados, unions discriminadas, versões obrigatórias, limites de campos |
| apps/api/motion_contracts/validation.py | Grafo, hierarquia, profundidade, câmera, tempo, budgets e bindings de contexto |
| apps/api/motion_contracts/canonical.py | Entrada JSON limitada, canonicalização e SHA-256 |
| apps/api/motion_contracts/registry.py e __init__.py | Registro local de receitas fixadas por ID/versão/hash, sem execução de código |
| scripts/generate_motion_contracts.py | JSON Schema e TypeScript derivados dos modelos; modo --check |
| contracts/motion/generated/ | Quatro schemas, motion-contracts.ts e fixture-types.ts gerados |
| contracts/motion/recipes/ | Índice local e três receitas versionadas |
| contracts/motion/fixtures/{sports,music,geo}/ | Envelope, storyboard, DNA, EDL v2 e contexto sintéticos por estilo |
| contracts/motion/tsconfig.json e README.md | Typecheck isolado e documentação executável |
| tests/test_motion_contracts.py | Contratos, segurança, bindings, tempo, geração e compatibilidade |
| .github/workflows/motion-contracts.yml | Gate de geração, Python, Ruff e TS para o PR |
| docs/M4_MOTION_COMPOSITION_ENGINE_ADR.md | Estado M4.A, autoridade dos contratos atuais e roadmap Scout |
| docs/testing/creative-m4-a/ | Logs, hashes de contratos e preservação das provas anteriores |
| docs/CREATIVE_M4_A_IMPLEMENTATION.md | Este relatório |

Nenhuma alteração em models/tabelas existentes, Remotion, FFmpeg, editor,
instalador, dependências, env.example ou migrações foi necessária.

### Fronteira de validação

1. read_json(bytes): até 2 MiB; rejeita chaves duplicadas, profundidade excessiva,
   Unicode inválido, NaN/Infinity, números inseguros e precisão excessiva.
2. MotionComposition.model_validate: valida estrutura, campos fechados e semântica
   independente de estado externo.
3. load_recipe(id, version): busca apenas no índice local, verifica caminho, identidade
   e SHA; não importa Python/JS, não interpreta expressões nem acessa URLs.
4. validate_binding: compara receita expandida, projeto, revisão/snapshot, EDL,
   storyboard, DNA, assets e claims fornecidos por um contexto confiável.
5. Retorna CONTRACT_VALID e render_supported=false, com limites de frames/cues
   e complexidade calculados. Não altera o projeto ou sua aprovação.

Essas funções não autenticam usuário nem consultam CreativeReview. O adapter futuro
precisará obter aprovação vigente, direitos, existência física e hashes de mídia do
servidor. Asserções enviadas pelo cliente não podem ser usadas como contexto confiável.

A fonte dos tempos continua sendo a EDL/shot aprovado. required_duration_ms da receita
é uma asserção de compatibilidade; divergência é erro, nunca mudança silenciosa do shot.
Os contextos sintéticos de teste não equivalem a CreativeReview real.

## 3. Contratos produzidos

| Modelo / schema gerado | schema_version obrigatório |
|---|---|
| MotionScene | motion_scene_v1 |
| MotionComposition | motion_composition_v1 |
| MotionRecipe | motion_recipe_v1 |
| RegistryIndex | motion_registry_v1 |

Todos usam strict=True, extra=forbid, números finitos e revalidação.
Versão ausente/desconhecida é erro, sem fallback para v1.
Modelos congelados ainda contêm listas: verificações recompõem o modelo e recalculam
hash, detectando mutações em containers ou model_copy sem validação.

A geração parte de Pydantic; não existe uma definição TS escrita manualmente em paralelo.
O gerador falha ao encontrar tipos não suportados. --check detecta mudanças pendentes
e arquivos gerados extras. fixture-types.ts exige que os três envelopes satisfaçam
MotionComposition durante o typecheck.

JSON Schema Draft 2020-12 expressa restrições estruturais; TypeScript expressa tipos.
Nenhum dos dois substitui os validadores Python de ciclos, intervalos, hashes,
limites agregados e contexto. Regex/ranges também não são garantidos pelo TypeScript.
Foram consultadas a documentação oficial de
[strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) e de
[geração de JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/).
Não foi introduzida uma nova integração externa.

### Vocabulário e diferenças deliberadas em relação ao rascunho ADR

- Nodes: group, text, shape, mask, path_follower, image, video, particle e light_sweep.
- Transformações: posição XYZ, escala XY, rotação Z, opacidade; câmera XYZ/Z/focal.
  Rotação X/Y não faz parte deste contrato.
- Keyframes com propriedade tipada; referência temporal discriminada em milissegundos
  ou cue + offset. Propriedades incompatíveis com o node são rejeitadas.
- Curvas de easing fechadas e cubic_bezier limitado a [0,1]; overshoot deve ser
  representado explicitamente por valores das keyframes, sem inferência de expressão.
- Geometria usa rect/ellipse e pontos polygon/polyline. SVG/XML, comandos de curvas
  arbitrários, CSS, shaders e scripts não são aceitos nesta versão.
- Texto vem de campos do shot ou claim aprovado; fontes/cores usam bindings do DNA.
- Assets referenciados por ID/hash/metadados. Não há URL, caminho local ou download
  definido dentro de uma receita.
- Sons mantêm ganho >0 e ≤1, compatível com sound_v1. Cue silencioso usa sound=null.
  Vídeos declaram muted=true sem aceitar coerção de 1 para booleano.
- Os exemplos abreviados da seção 7 do ADR permanecem como estudo histórico.
  Schemas e fixtures atuais são a especificação executável do M4.A.

Os nomes das primitivas não significam que já existam componentes que as renderizam.

## 4. Segurança, tempo e complexidade

| Recurso | Limite / regra |
|---|---|
| Entrada | 2 MiB, profundidade 24, dados JSON; sem código executável |
| Composição | 3–30 s; 30 FPS; 1080×1920, 1920×1080 ou 1080×1080; até 12 shots |
| Grafo | 128 nodes expandidos/cena, 512 globais; hierarquia até 6; sem ciclos |
| Máscaras | Um alvo group irmão no mesmo espaço; até 2 máscaras aninhadas |
| Paths | Até 512 pontos/path e 4096 globais; follower referencia shape irmão compatível |
| Animação | Até 32 keyframes/propriedade, 8 animações/node, 8192 keyframes globais |
| Cues | Até 64 globais; IDs únicos; referências resolvidas |
| Partículas | Até 64/cena, incluídas no orçamento de nodes expandidos |
| Concorrência por cena | Até 4 imagens, 2 vídeos, 8 sons e 2 light sweeps simultâneos |
| Assets | Até 32 slots, 128 MiB/asset e 256 MiB no total declarado |
| Metadados | Imagem até 4096²; vídeo até 3840²/30 FPS; áudio até 2 canais/96 kHz |
| Câmera | Envelope Z conservador dos ancestrais/keyframes; margem >32 do plano próximo |
| Texto | Até 240 caracteres resolvidos; limite de linhas; medição visual futura |
| Registro | ID/semver restritos, índice fechado, hash verificado, caminho contido no diretório |

Frames são calculados nas bordas absolutas: F(t)=(30*t+500)//1000.
Cada shot usa [F(start),F(end)), sem acumular arredondamentos relativos.
Cues precisam cair em frames exibidos; keyframe final pode ser endpoint na borda.
Duas keyframes no mesmo frame são rejeitadas. O teste com shots de 1001 e 10999 ms
confere a fronteira compartilhada sem gap ou frame duplicado.
Filhos herdam o intervalo do pai; intervalo explícito não pode escapar dele.
O relatório de bindings registra erro de quantização dos cues em terços de ms inteiros.

Safe areas são validadas estruturalmente. Legibilidade real, recorte de glifos,
oclusão, continuidade e desempenho por frame dependem do interpretador e da QA visual
posteriores. Não são alegados como resolvidos por validação de JSON.

### Canonicalização verificável

mg-canonical-json-v1 é um formato do projeto, não RFC 8785/JCS.
Após validação/defaults: UTF-8, chaves ordenadas, arrays preservados, sem whitespace,
sem normalização Unicode implícita. Números finitos com módulo ≤2^53−1 e até seis
decimais, sem notação exponencial; -0→0 e 1.0→1. Não há arredondamento silencioso.
SHA-256 usa esses bytes. Hash da receita exclui somente seu próprio campo sha256.

O teste inclui vetor de bytes conhecido, igualdade após defaults, ordem de objetos,
diferença quando muda ordem de arrays, mutação e adulteração de arquivos.
O índice fixa versão e conteúdo; mudanças precisam de versão/índice revisados.

## 5. Três fixtures distintas

| Fixture / receita 1.0.0 | Estrutura declarada | Formato / duração |
|---|---|---|
| Sports / sports.depth-impact | Tipografia world space, grupo screen space, máscara e faixa diagonal | Vertical / 12 s |
| Music / music.orbital-sleeve | Capa central, hierarquia orbital e entradas vinculadas a cues musicais | Quadrado / 10 s |
| Geo / geo.route-explainer | Região ficcional, path, marcador seguidor e fonte demonstrativa | Horizontal / 15 s |

Cada diretório contém composition.json, storyboard.json, dna.json, edl_v2.json e
context.json. As árvores são estruturalmente diferentes; isso não comprova variedade
visual produzida. IDs, snapshots, claims e mídia são sintéticos.
Os hashes de assets identificam strings de teste, não arquivos licenciados existentes.

Hashes reais das receitas:

- Sports: 9b4a5dd40111743d9561e2b92bfb77ecee777c61444fed1f035a64cfc381b061
- Music: c36e17f249d0fb343ec6f79b2f8ee1b29190aac6824a9f50f373572dcad47d2f
- Geo: 9d0f1d3dcf0556b9b89a6a8b47a617a4e85b1e926e2e874839161e6905a2859d

[Hashes completos de receitas/envelopes](testing/creative-m4-a/contract-hashes.json).
Nenhuma fixture foi renderizada; não há MP4 novo nem avaliação artística nesta etapa.

## 6. Testes efetivamente executados

Comandos na raiz do repositório; resultados desta máquina Windows:

| Comando | Resultado |
|---|---|
| .venv/Scripts/python.exe -m pytest -q tests | **228 passed, 1 skipped**, 118,91 s |
| .venv/Scripts/python.exe -m pytest -q tests/test_motion_contracts.py | **83 passed**, 0,63 s, revisão final |
| .venv/Scripts/python.exe -m ruff check . | PASS, revisão final |
| .venv/Scripts/python.exe scripts/generate_motion_contracts.py --check | PASS, revisão final |
| node node_modules/typescript/bin/tsc --noEmit -p contracts/motion/tsconfig.json | PASS |
| node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json | PASS |
| node node_modules/typescript/bin/tsc --noEmit -p apps/renderer/tsconfig.json | PASS |
| .venv/Scripts/python.exe -m alembic heads | 0012_creative_direction (head) |

A suíte completa foi executada antes de cinco casos finais de endurecimento do módulo
novo (compatibilidade sound_v1 nas três fixtures, cue silencioso/booleano e inteiro
excessivamente grande). Esses ajustes passaram na execução final dos **83 testes de
contratos** e no Ruff. Não somar resultados nem afirmar que 233 testes passaram em uma
única execução completa. O skip é o teste existente que exige runtime Blender 4.5,
não configurado neste host.

[Log da suíte completa](testing/creative-m4-a/pytest-full.txt) e
[log final de contratos](testing/creative-m4-a/pytest-contracts.txt).

Cobertura efetiva: campos/versões inválidos, coerções, NaN/Infinity, tamanho/profundidade,
inteiros excessivos, chaves duplicadas, scripts/URLs/campos desconhecidos, ciclos,
parents, máscaras, followers, câmera, referências ausentes, budgets, tempos negativos/
colapsados/fora do shot, overlays simultâneos, IDs/hash de assets, revisão obsoleta,
snapshot divergente, claims ausentes, DNA e EDL incompatíveis, alteração de receita,
path escape, geração divergente e retorno explícito render_supported=false.
Os testes também verificam que a EDL de entrada e sua projeção legada não mudam.

Os testes de contratos substituem a fixture automática de reset de DB por no-op.
A suíte de integração existente usa data/mediagrid-test.db e recursos descartáveis
conforme tests/conftest.py. Nenhum comando foi direcionado ao SQLite instalado.

## 7. Preservação e estado real

Os quatro MP4 anteriores (M3, M3.1 V1/V2 e M3.2 V2) mantêm os hashes registrados:
[evidência de preservação](testing/creative-m4-a/preservation.json).
Código e reports anteriores permanecem; somente o ADR recebe atualização de status/roadmap.

| Capacidade | Estado nesta entrega |
|---|---|
| Contratos, canonicalização, registro e validação Python | REAL, testados localmente |
| Schemas/TS derivados e verificação de divergência | REAL |
| Fixtures Sports/Music/Geo | SINTÉTICAS, exclusivamente dados de contrato |
| Interpreter/compilador de receitas para Remotion | NÃO IMPLEMENTADO; M4.B/C |
| Aprovação, direitos e leitura física de assets para novos contratos | Contexto de teste; adapter real ainda necessário |
| UI de seleção e novos renders | NÃO IMPLEMENTADOS |
| Autonomous Visual Reference Scout | PAPER / desabilitado, somente roadmap |

Não houve migração, mudança de env.example, banco instalado, instalação desktop,
merge, publicação, deploy ou ativação de API paga. O código novo não faz rede.
Nenhuma cobrança de serviço externo foi acionada pelo runtime deste módulo.
Os tempos acima medem testes; não são benchmark de render nem medição de custo futuro.
A CI adicionada usa o plano Actions já existente, sem promessa de custo universal.

## 8. Autonomous Visual Reference Scout — roadmap

A seção 16 do [ADR](M4_MOTION_COMPOSITION_ENGINE_ADR.md) preserva e explicita:

- Planejamento a partir do brief/DNA, adapters de fontes públicas/APIs autorizadas.
- Proveniência, direitos, licença, cache, deduplicação, limites e hashes.
- Interfaces de request/query/results, análise multimodal opcional local e manifesto
  visual_inspiration_manifest_v1 versionado/imutável.
- Extração de composição, tipografia, paleta, iluminação, profundidade, ritmo e movimento,
  com evidências e incerteza; propostas originais e seleção humana.
- Bridge de propostas aprovadas para specs do Motion Engine e previews futuros.
- Fontes candidatas, requisitos de credenciais/termos, riscos e fases Scout A–E.

**Pesquisa pertence à descoberta.** Compilação e render recebem manifestos/specs congelados
e não consultam a web. Dependências ausentes exigem bloqueio ou redescoberta antes de
nova aprovação, sem alterar um render em curso. Nenhuma busca, modelo multimodal,
provider, endpoint ou tarefa automática do Scout foi implementada.

## 9. Como verificar e próximo gate

Na raiz:

    .venv/Scripts/python.exe scripts/generate_motion_contracts.py --check
    .venv/Scripts/python.exe -m pytest -q tests/test_motion_contracts.py
    .venv/Scripts/python.exe -m ruff check .
    node node_modules/typescript/bin/tsc --noEmit -p contracts/motion/tsconfig.json

Leia contracts/motion/README.md e as três fixtures junto com seus contextos.
Não envie esses envelopes para o worker legado: o preset ainda não está registrado.

M4.B requer autorização explícita. O próximo trabalho proposto é interpretar as
primitivas fechadas no Remotion existente, validar visualmente as semânticas/limites
e compartilhar preview/encode. Integração de assets reais, aprovação e worker segue
os gates posteriores do ADR. A implementação desta rodada termina no M4.A.
