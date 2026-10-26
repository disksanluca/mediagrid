# ADR proposto — M4 Motion Composition Engine v1

**Estado: PROPOSTO, NÃO IMPLEMENTADO.** Data: 26/10/2026.
Esta entrega implementa somente o polimento M3.2 e documenta o M4.
A implementação do motor depende de avaliação humana posterior.

## 1. Contexto e decisão proposta

M3 tornou real o caminho Creative Director → vídeo. M3.1 introduziu V1/V2;
o usuário escolheu V2 Broadcast como base provisória, não como aprovação artística
automática do refinamento final. M3.2 encerra esta rodada de polimento.

O próximo problema é expressar linguagens visuais diferentes por dados validados,
reutilizando a composição, fila e runtime existentes. A referência enviada mostra
Sports, Music e Geo como experiências distintas. Ela não é um asset autorizado
para os filmes nem evidência de funcionalidades da MediaGrid.

**Proposta:** adicionar um preset declarativo motion_scene_v1 ao registro EDL v2,
um interpretador React de primitivas fechadas e um compilador Python determinístico
de receitas. O resultado continua dentro de Job.payload, como EDL v2 derivada.
Não criar uma segunda timeline persistente nem executar JavaScript vindo do projeto.

A identidade Editorial Light & Dark/Lovable pertence à interface; a receita de vídeo
usa Creative DNA do canal. Tokens da UI não devem sobrescrever paleta/tipografia do vídeo.

## 2. Mapa do código atual

| Camada | Evidência no repositório | Reuso / lacuna |
|---|---|---|
| Conteúdo e aprovação | apps/api/creative/contracts.py e service.py | Brief, DNA, direções, shots, claims e snapshot; fonte editorial |
| Bridge M3 | apps/api/creative/motion.py | Plano imutável, hash, UUID v5 por plano; bloqueado em ficção, quatro atos 2/3/4/3 s, uma trilha aprovada, Barlow e 9:16 |
| Timeline | apps/api/edl_v2.py | EDLV2, Canvas, tracks e TimelineItem; x/y/opacity/scale limitados em OverlaySpec; presets fechados |
| Projeção | scene_projection e to_legacy, no mesmo arquivo | Remove overlays/áudio e mantém picture/voice/titles alinhados. Somente 30 FPS e formatos conhecidos; não aceita um graphic arbitrário como cena |
| Props | apps/api/render_plan.py | Projeção compartilhada; hoje overlays/sounds/video_layers separados |
| Renderer | apps/renderer/src/timeline-v2.tsx | Mesma composição no Player e no encode; dispatch de presets |
| Metadados | apps/renderer/src/Root.tsx | FPS fixo 30; duração pela soma das cenas; canvas conforme format |
| Preset esportivo | sports-cinematic.tsx e sports-refinement.tsx | Bola, parallax e trajetórias em código; não são uma gramática genérica |
| Biblioteca de mídia | apps/api/scene_media.py | Direitos, existência física, MIME e staging com SHA; precisa percorrer referências aninhadas do grafo |
| Render | workers/render/creative_motion.py, main.py e remotion_runtime.py | Job/lease/heartbeat, staging privado, revalidação antes/depois, CLI e FFprobe |
| Preview/API | apps/api/routes/creative.py e componente CreativeMotionProof | Snapshot e hash exatos; mesmos props e assets; não interpreta prosa |
| Revisão/export legado | apps/api/routes/projects.py | Aprova MP4/EDL/revisão gravando Project.plan.review; não serve diretamente a artefato derivado, pois invalidaria M1 |
| Desktop | apps/desktop/src-tauri/src/service_manager.rs | Descobre Node, renderer, FFmpeg/FFprobe e Chrome locais; mantém serviço local |
| Persistência | SQLAlchemy, SQLite, head 0012_creative_direction | Não há tabela de uma segunda timeline de motion |

Lacunas centrais: parâmetros esportivos fixos; ausência de grupos/câmera declarativos;
mídia aninhada não suportada na bridge; falta de limites globais de complexidade;
aprovação audiovisual por job ainda não persistida; metadados com FPS fixo; fontes
ainda específicas do preset; ordenação de layers globais não unificada.

## 3. Fontes técnicas e versões

Base instalada preservada: Remotion/Player 4.0.532 e lockfile existente, React
19.3.0, Next 16.3.8, Node 24.19.0, Python 3.12.10, FFmpeg/FFprobe 9.0.2.
Nenhum pacote foi atualizado para escrever este ADR.

Documentação oficial consultada em 26/10/2026:

- [Sequence](https://www.remotion.dev/docs/sequence): useCurrentFrame é deslocado
  pelo início da Sequence; logo o interpretador deve receber tempo local explicitamente.
- [OffthreadVideo](https://www.remotion.dev/docs/offthreadvideo): extração de frames
  no render ocorre fora do navegador; preview e export precisam de testes de paridade.
- [Performance](https://www.remotion.dev/docs/performance): concorrência depende do
  host; filtros/efeitos podem ter custo relevante; reduzir escala não muda a composição.
- [renderMedia](https://www.remotion.dev/docs/renderer/render-media): referência
  do runtime existente; não é proposta trocar a CLI nesta fase.

A documentação atual recomenda APIs de mídia mais novas. Isso não justifica migrar
o runtime validado neste milestone. Uma migração de vídeo deverá ser isolada, com
benchmark e verificação de licenças antes de alterar dependências.

## 4. Contratos e uma única autoridade temporal

### 4.1 Envelope de compilação

motion_composition_v1 é o documento de compilação proposto:

- project_id e expected: revisão do storyboard, snapshot SHA-256, canvas e duração
  esperados. Canvas/duração são **assertivas**, nunca substitutos dos valores aprovados.
- recipe: ID, versão semântica e SHA-256 do documento de receita no registro.
- asset_bindings: nomes de slots → IDs e hashes de assets da biblioteca.
- scenes: associação exata shot_id → grafo local motion_scene_v1.
- DNA, direção, direitos e claims são resolvidos pelo servidor e incluídos no plano.
  O cliente não consegue se declarar titular de direitos por esse JSON.

A API futura recebe expected, recipe e bindings. Os graphs expandidos mostrados nos
exemplos abaixo são a representação declarativa produzida pelo compilador a partir
de uma receita aprovada no registro, não overrides arbitrários de uma receita existente.
Criar um novo desenho significa versionar JSON de receita; não criar outro componente.

### 4.2 Grafo local motion_scene_v1

| Campo | Contrato proposto |
|---|---|
| schema_version | literal motion_scene_v1 |
| nodes | união discriminada pelo type; IDs únicos; pai opcional; ordem estável |
| camera | posição XYZ, rotação limitada e focal_length; apenas uma por cena |
| cues | eventos explícitos locais; cada cue possui ID e at_ms dentro do shot |
| safe_area | insets em pixels lógicos e regra para texto obrigatório |
| metadata | apenas chaves de proveniência declaradas; sem blobs de estilo livre |

Defaults de node: parent_id=null, space=world, posição [0,0,0], escala [1,1],
rotate_z=0, opacity=1, z_index=0, anchor=[0,0], active_ms=[0,duração do shot].
Screen space ignora câmera e serve para títulos que precisam permanecer legíveis.
Filhos herdam transformação e clipping do pai. IDs formam uma árvore/forest acíclica,
sem referências entre cenas. Empate de z_index usa a ordem original do array.

params é uma união tipada por node, não um dicionário de CSS. Proibir campos extras,
NaN/Infinity, coerção de string para número e booleano para inteiro.
Configuração proposta Pydantic: extra=forbid, strict=true, allow_inf_nan=false.
Gerar JSON Schema e tipos TS desse contrato; validar também a fronteira do Player.

Tipos de binding são fechados: texto do shot aprovado, campo de claim aprovado,
slot de asset e índice da paleta/fonte do DNA. Não há interpolação de expressões,
eval, URL de fonte, callback, HTML, JSX, import ou código em strings.
Uma string em motion_intent permanece texto descritivo. Se não houver tradução
estruturada suportada, retornar UNSUPPORTED_INTENT; não fingir que ela foi executada.

### 4.3 Tempo, keyframes e cues

A EDL v2 mantém start_ms/duration_ms dos shots. O grafo só anima dentro do seu
TimelineItem. Não pode estender o shot, criar cortes globais ou mudar duração aprovada.

Cada animação declara property em uma enumeração, keyframes ordenados e easing.
at_ms é local ao item. Alternativamente, cue_ref + offset_ms referencia um cue
local resolvido pelo compilador; ambos não podem coexistir no mesmo keyframe.
Valores numéricos e vetoriais precisam ter dimensões consistentes.
Easing inicial: linear, hold, cubic_in_out, cubic_out e cubic_bezier com quatro
controles finitos; X dos controles em [0,1], Y em [-2,2]. Opacidade sempre limitada.
Sem springs simuladas ou dependência de frames anteriores; overshoot deve ser explícito.

Limites em frames são derivados uma única vez dos limites absolutos em ms:
F(t)=floor(t*30/1000+0.5). Item usa [F(início), F(fim)).
Nunca somar durações arredondadas independentemente. Atos contíguos compartilham
a mesma borda. Evento colapsado ou fora do item é erro, não ajuste silencioso.
Persistir no manifesto o arredondamento aplicado e erro temporal de cada cue.

## 5. Primitivas e parâmetros

Primitivas são expansores de dados limitados, avaliados no mesmo interpretador.
Nenhuma primitiva pode montar componentes pelo nome recebido do usuário.

| Primitiva | Parâmetros essenciais / defaults | Limites iniciais |
|---|---|---|
| TransformGroup / ParallaxGroup | position, scale, rotate_z, depth; depth 0 | profundidade 6; escala 0,05..8; z em -600..4000 |
| TypographyReveal / KineticText | binding de texto, fonte DNA, size, line_height=1, align=left, método fade_slide | 240 caracteres/node; 6 linhas; fonte ≥32 px para texto obrigatório em 1080 |
| ShapeReveal | rect/ellipse/polygon/polyline; fill/stroke tipados; draw_progress=1 | 512 vértices/path; 4096 por composição |
| MaskTransition | rect/ellipse/polygon; progress 0..1; alvo group | 2 níveis de clip; sem SVG/HTML cru |
| CameraMove | position, rotate_z, focal_length=1200 | uma câmera/cena; sem cruzar o plano próximo |
| PathAnimation | path_ref, progress, orientação opcional | path existente, progress 0..1, sem física |
| ImageReveal | asset_binding, fit=contain, crop, máscara opcional | imagens locais até 4096²; no máximo 4 simultâneas |
| VideoLayer | asset_binding, trim, fit=cover, muted=true | no máximo 2 simultâneos; velocidade 1 no v1 |
| ParticleAccent | seed, count, trajetória analítica, duração | 64 partículas/cena; incluidas no orçamento expandido |
| SoundCue | asset_binding, source_in_ms, duration_ms, gain, fades | traduz para music/sfx sound_v1, nunca outro mixer |
| LightSweep | gradiente fechado, direção, largura, intensidade | até 2 simultâneos; blur limitado a 12 px |
| VectorGeometry | arrays de comandos M/L/Q/C/Z validados, sem XML | mesma cota de paths; sem referência externa |

Movimentos 2.5D usam uma projeção pinhole determinística em coordenadas lógicas.
Rotação X/Y, quando habilitada, é limitada a ±60 graus. Validar toda a trajetória
para distância positiva ao plano próximo; nunca esconder uma divisão por zero.
Elementos vetoriais/texto mantêm fundos/sombras locais; não prometer material PBR.

Antes de adicionar uma primitiva nova, verificar se é uma combinação das existentes.
Primitivas parecidas, como ShapeReveal e PathAnimation, compartilham o mesmo
avaliador de paths. A bola do preset M3 não vira requisito para todo Sports Motion.

## 6. Receitas, autoria e Creative DNA

Cada receita é JSON versionado no repositório/registro local, com ID, versão,
schema compatível, slots, defaults, limites, graphs, cues e um hash canônico.
O hash exclui apenas o próprio campo de hash; mantém ordem dos arrays, UTF-8,
números finitos normalizados e o conteúdo de todos os defaults resolvidos.
Versão publicada é imutável. Editar cria outra versão; jobs antigos conservam a receita.

Conteúdo (texto, claims, artefatos, duração, paleta, fontes) vem do projeto aprovado.
Receita define relações espaciais, ritmo e composição. Bindings só podem resolver
dados que já pertencem ao snapshot; dados novos exigem revisão editorial.
Áudio de sound design derivado segue a distinção explícita do M3.1: sua escolha
não altera o brief, mas entra no hash do plano e na futura revisão do artefato.
Nenhuma receita pode acrescentar uma afirmação factual por conta própria.

O primeiro M4 não inclui marketplace nem editor livre de receitas. Autoria será
por documentos locais revisados, usando o mesmo compilador. UI seleciona receitas,
parâmetros limitados e slots; o grafo expandido fica legível para diagnóstico.
A escolha ainda não enfileirada é um rascunho local; após enfileirar, Job.payload é
a fonte persistida. Não prometer autosave de uma segunda timeline.

## 7. Exemplos de JSON — três linguagens

Os exemplos são **propostas documentais**, não payloads aceitos pela API atual.
Tokens como \${PROJECT_ID}, \${APPROVED_SNAPSHOT_SHA256} e hashes de assets devem
ser resolvidos com dados reais. São JSON sintaticamente válidos, mas não são provas
de validação de um schema que ainda não foi implementado.

Cada exemplo pressupõe um storyboard demonstrativo aprovado com um shot do tempo
indicado; a associação shot_id é obrigatória. Para vários shots, a expansão repete
graphs locais com seus bindings, sem copiar start_ms/duration_ms para outra timeline.
As fontes de textos são bindings do storyboard, não texto livre criado pela receita.
Os cues de score referenciam WAVs originais previamente importados.

### A. Sports — título em profundidade, recorte diagonal e impacto

Canvas vertical, 12 s. Tipografia dominante em dois planos, recorte motivado no
impacto e câmera curta. Não depende de escudo, atleta ou resultado de partida.

```json
{
  "schema_version": "motion_composition_v1",
  "project_id": "${PROJECT_ID}",
  "expected": {
    "storyboard_revision": 1,
    "snapshot_sha256": "${APPROVED_SNAPSHOT_SHA256}",
    "canvas": {
      "width": 1080,
      "height": 1920,
      "fps_num": 30,
      "fps_den": 1
    },
    "duration_ms": 12000
  },
  "recipe": {
    "id": "sports.depth-impact",
    "version": "1.0.0",
    "sha256": "${RECIPE_SHA256}"
  },
  "asset_bindings": {
    "score": {
      "asset_id": "${ORIGINAL_SPORTS_SCORE_ASSET_ID}",
      "sha256": "${ORIGINAL_SPORTS_SCORE_SHA256}"
    }
  },
  "scenes": [
    {
      "shot_id": "${APPROVED_SHOT_ID}",
      "graph": {
        "schema_version": "motion_scene_v1",
        "safe_area": {
          "left": 72,
          "right": 72,
          "top": 120,
          "bottom": 180
        },
        "camera": {
          "position": [
            0,
            0,
            0
          ],
          "focal_length": 1200,
          "animations": [
            {
              "property": "position",
              "keyframes": [
                {
                  "at_ms": 0,
                  "value": [
                    0,
                    0,
                    0
                  ],
                  "easing": "cubic_in_out"
                },
                {
                  "at_ms": 4800,
                  "value": [
                    60,
                    -30,
                    120
                  ],
                  "easing": "cubic_in_out"
                },
                {
                  "at_ms": 10000,
                  "value": [
                    0,
                    0,
                    40
                  ],
                  "easing": "cubic_in_out"
                }
              ]
            }
          ]
        },
        "nodes": [
          {
            "id": "back-title",
            "type": "text",
            "position": [
              110,
              600,
              600
            ],
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "size": 260,
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "opacity": 0.18,
              "method": "fade_slide"
            },
            "animations": [
              {
                "property": "position",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": [
                      110,
                      600,
                      600
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 10000,
                    "value": [
                      -80,
                      500,
                      600
                    ],
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "hero",
            "type": "group",
            "space": "screen",
            "position": [
              90,
              660,
              0
            ],
            "params": {},
            "animations": [
              {
                "property": "scale",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": [
                      0.92,
                      0.92
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 300,
                    "value": [
                      1,
                      1
                    ],
                    "easing": "cubic_out"
                  },
                  {
                    "at_ms": 10500,
                    "value": [
                      1.02,
                      1.02
                    ],
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "title",
            "parent_id": "hero",
            "type": "text",
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "size": 210,
              "max_width": 900,
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "method": "fade_slide"
            }
          },
          {
            "id": "diagonal",
            "type": "shape",
            "space": "screen",
            "params": {
              "shape": "polygon",
              "points": [
                [
                  0,
                  1400
                ],
                [
                  1080,
                  1100
                ],
                [
                  1080,
                  1200
                ],
                [
                  0,
                  1500
                ]
              ],
              "fill": {
                "kind": "dna_palette",
                "index": 2
              }
            },
            "animations": [
              {
                "property": "opacity",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": 0,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 5000,
                    "value": 0,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 5250,
                    "value": 0.8,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 9000,
                    "value": 0.4,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 11500,
                    "value": 0,
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "cut-mask",
            "type": "mask",
            "space": "screen",
            "params": {
              "target_id": "hero",
              "shape": "polygon",
              "points": [
                [
                  0,
                  0
                ],
                [
                  1080,
                  0
                ],
                [
                  1080,
                  1920
                ],
                [
                  0,
                  1920
                ]
              ],
              "progress": 1
            },
            "animations": [
              {
                "property": "progress",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": 0,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 300,
                    "value": 1,
                    "easing": "cubic_out"
                  },
                  {
                    "at_ms": 11500,
                    "value": 1,
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          }
        ],
        "cues": [
          {
            "id": "impact",
            "at_ms": 0,
            "sound": {
              "asset_binding": "score",
              "source_in_ms": 0,
              "duration_ms": 12000,
              "gain": 0.8,
              "fade_in_ms": 5,
              "fade_out_ms": 350
            }
          },
          {
            "id": "cut",
            "at_ms": 5000
          },
          {
            "id": "resolve",
            "at_ms": 9000
          }
        ]
      }
    }
  ]
}
```

### B. Música — capa central e palavras em órbita

Canvas quadrado, 10 s. Capa autorizada ocupa o centro; geometria circular e texto
em profundidade mudam a moldura ao ritmo de cues manuais. O texto frontal aparece
no início de uma frase musical. Não inclui letra de música, capa ou fonograma de terceiros.

```json
{
  "schema_version": "motion_composition_v1",
  "project_id": "${PROJECT_ID}",
  "expected": {
    "storyboard_revision": 1,
    "snapshot_sha256": "${APPROVED_SNAPSHOT_SHA256}",
    "canvas": {
      "width": 1080,
      "height": 1080,
      "fps_num": 30,
      "fps_den": 1
    },
    "duration_ms": 10000
  },
  "recipe": {
    "id": "music.orbital-sleeve",
    "version": "1.0.0",
    "sha256": "${RECIPE_SHA256}"
  },
  "asset_bindings": {
    "score": {
      "asset_id": "${ORIGINAL_MUSIC_SCORE_ASSET_ID}",
      "sha256": "${ORIGINAL_MUSIC_SCORE_SHA256}"
    },
    "cover": {
      "asset_id": "${AUTHORIZED_COVER_ASSET_ID}",
      "sha256": "${AUTHORIZED_COVER_SHA256}"
    }
  },
  "scenes": [
    {
      "shot_id": "${APPROVED_SHOT_ID}",
      "graph": {
        "schema_version": "motion_scene_v1",
        "safe_area": {
          "left": 72,
          "right": 72,
          "top": 72,
          "bottom": 72
        },
        "camera": {
          "position": [
            0,
            0,
            0
          ],
          "focal_length": 1400,
          "animations": [
            {
              "property": "position",
              "keyframes": [
                {
                  "at_ms": 0,
                  "value": [
                    -80,
                    0,
                    0
                  ],
                  "easing": "cubic_in_out"
                },
                {
                  "at_ms": 5000,
                  "value": [
                    80,
                    0,
                    120
                  ],
                  "easing": "cubic_in_out"
                },
                {
                  "at_ms": 9500,
                  "value": [
                    0,
                    0,
                    0
                  ],
                  "easing": "cubic_in_out"
                }
              ]
            }
          ]
        },
        "nodes": [
          {
            "id": "orbit",
            "type": "group",
            "position": [
              540,
              540,
              400
            ],
            "params": {},
            "animations": [
              {
                "property": "rotate_z",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": -24,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 9500,
                    "value": 36,
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "ring",
            "parent_id": "orbit",
            "type": "shape",
            "position": [
              -420,
              -420,
              0
            ],
            "params": {
              "shape": "ellipse",
              "width": 840,
              "height": 840,
              "fill": null,
              "stroke": {
                "kind": "dna_palette",
                "index": 2
              },
              "stroke_width": 6
            },
            "animations": [
              {
                "property": "scale",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": [
                      0.9,
                      0.9
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 2500,
                    "value": [
                      1,
                      1
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 5000,
                    "value": [
                      0.92,
                      0.92
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 7500,
                    "value": [
                      1.02,
                      1.02
                    ],
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "orbital-text",
            "parent_id": "orbit",
            "type": "text",
            "position": [
              -400,
              -400,
              0
            ],
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "size": 64,
              "max_width": 800,
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "method": "fade_slide"
            }
          },
          {
            "id": "sleeve",
            "type": "image",
            "position": [
              310,
              280,
              0
            ],
            "params": {
              "asset_binding": "cover",
              "width": 460,
              "height": 460,
              "fit": "contain"
            },
            "animations": [
              {
                "property": "scale",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": [
                      0.9,
                      0.9
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 900,
                    "value": [
                      1,
                      1
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 7500,
                    "value": [
                      1.04,
                      1.04
                    ],
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 9500,
                    "value": [
                      1,
                      1
                    ],
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "front-title",
            "type": "text",
            "space": "screen",
            "position": [
              90,
              850,
              0
            ],
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "size": 84,
              "max_width": 900,
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "method": "fade_slide"
            },
            "animations": [
              {
                "property": "opacity",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": 0,
                    "easing": "hold"
                  },
                  {
                    "cue_ref": "phrase",
                    "offset_ms": 0,
                    "value": 0,
                    "easing": "linear"
                  },
                  {
                    "cue_ref": "phrase",
                    "offset_ms": 400,
                    "value": 1,
                    "easing": "cubic_out"
                  }
                ]
              }
            ]
          }
        ],
        "cues": [
          {
            "id": "score",
            "at_ms": 0,
            "sound": {
              "asset_binding": "score",
              "source_in_ms": 0,
              "duration_ms": 10000,
              "gain": 0.75,
              "fade_in_ms": 80,
              "fade_out_ms": 500
            }
          },
          {
            "id": "pulse",
            "at_ms": 2500
          },
          {
            "id": "phrase",
            "at_ms": 5000
          },
          {
            "id": "resolve",
            "at_ms": 7500
          }
        ]
      }
    }
  ]
}
```

### C. Geografia — mapa demonstrativo e percurso

Canvas horizontal, 15 s. Geometria de região **ficcional**, caminho progressivo,
marcador e câmera de acompanhamento. O exemplo não representa Cairo nem um mapa
real. O campo source_label precisa dizer que os dados são demonstrativos e passar
pela revisão de claim. Para geografia factual, importar geometria simplificada de
fonte verificável como asset com hash/licença; os dados inline então são derivados
desse asset e o manifesto registra essa relação. Não buscar tiles durante o render.

```json
{
  "schema_version": "motion_composition_v1",
  "project_id": "${PROJECT_ID}",
  "expected": {
    "storyboard_revision": 1,
    "snapshot_sha256": "${APPROVED_SNAPSHOT_SHA256}",
    "canvas": {
      "width": 1920,
      "height": 1080,
      "fps_num": 30,
      "fps_den": 1
    },
    "duration_ms": 15000
  },
  "recipe": {
    "id": "geo.route-explainer",
    "version": "1.0.0",
    "sha256": "${RECIPE_SHA256}"
  },
  "asset_bindings": {
    "score": {
      "asset_id": "${ORIGINAL_GEO_SCORE_ASSET_ID}",
      "sha256": "${ORIGINAL_GEO_SCORE_SHA256}"
    }
  },
  "scenes": [
    {
      "shot_id": "${APPROVED_SHOT_ID}",
      "graph": {
        "schema_version": "motion_scene_v1",
        "safe_area": {
          "left": 100,
          "right": 100,
          "top": 80,
          "bottom": 100
        },
        "camera": {
          "position": [
            0,
            0,
            0
          ],
          "focal_length": 1600,
          "animations": [
            {
              "property": "position",
              "keyframes": [
                {
                  "at_ms": 0,
                  "value": [
                    -100,
                    0,
                    0
                  ],
                  "easing": "cubic_in_out"
                },
                {
                  "at_ms": 6500,
                  "value": [
                    200,
                    80,
                    180
                  ],
                  "easing": "cubic_in_out"
                },
                {
                  "at_ms": 13000,
                  "value": [
                    0,
                    0,
                    0
                  ],
                  "easing": "cubic_in_out"
                }
              ]
            }
          ]
        },
        "nodes": [
          {
            "id": "map",
            "type": "group",
            "position": [
              100,
              120,
              300
            ],
            "params": {}
          },
          {
            "id": "region",
            "parent_id": "map",
            "type": "shape",
            "params": {
              "shape": "polygon",
              "points": [
                [
                  0,
                  80
                ],
                [
                  700,
                  0
                ],
                [
                  1500,
                  280
                ],
                [
                  1420,
                  720
                ],
                [
                  600,
                  800
                ],
                [
                  80,
                  520
                ]
              ],
              "fill": {
                "kind": "dna_palette",
                "index": 0
              },
              "stroke": {
                "kind": "dna_palette",
                "index": 1
              },
              "stroke_width": 3
            }
          },
          {
            "id": "route",
            "parent_id": "map",
            "type": "shape",
            "params": {
              "shape": "polyline",
              "points": [
                [
                  180,
                  520
                ],
                [
                  420,
                  430
                ],
                [
                  700,
                  460
                ],
                [
                  1050,
                  220
                ],
                [
                  1360,
                  280
                ]
              ],
              "fill": null,
              "stroke": {
                "kind": "dna_palette",
                "index": 2
              },
              "stroke_width": 12,
              "draw_progress": 0
            },
            "animations": [
              {
                "property": "draw_progress",
                "keyframes": [
                  {
                    "at_ms": 1500,
                    "value": 0,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 9000,
                    "value": 1,
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "marker",
            "parent_id": "map",
            "type": "path_follower",
            "params": {
              "path_ref": "route",
              "progress": 0,
              "shape": "ellipse",
              "width": 28,
              "height": 28,
              "fill": {
                "kind": "dna_palette",
                "index": 1
              }
            },
            "animations": [
              {
                "property": "progress",
                "keyframes": [
                  {
                    "at_ms": 1500,
                    "value": 0,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 9000,
                    "value": 1,
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          },
          {
            "id": "heading",
            "type": "text",
            "space": "screen",
            "position": [
              110,
              85,
              0
            ],
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "size": 72,
              "max_width": 1600,
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "method": "fade_slide"
            }
          },
          {
            "id": "source",
            "type": "text",
            "space": "screen",
            "position": [
              110,
              930,
              0
            ],
            "params": {
              "text": {
                "kind": "approved_claim_field",
                "claim_id": "${APPROVED_DEMONSTRATIVE_CLAIM_ID}",
                "field": "source_label"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "size": 36,
              "max_width": 1600,
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "method": "fade_slide"
            },
            "animations": [
              {
                "property": "opacity",
                "keyframes": [
                  {
                    "at_ms": 0,
                    "value": 0,
                    "easing": "cubic_in_out"
                  },
                  {
                    "at_ms": 800,
                    "value": 1,
                    "easing": "cubic_in_out"
                  }
                ]
              }
            ]
          }
        ],
        "cues": [
          {
            "id": "ambience",
            "at_ms": 0,
            "sound": {
              "asset_binding": "score",
              "source_in_ms": 0,
              "duration_ms": 15000,
              "gain": 0.6,
              "fade_in_ms": 300,
              "fade_out_ms": 800
            }
          },
          {
            "id": "start-route",
            "at_ms": 1500
          },
          {
            "id": "arrival",
            "at_ms": 9000
          }
        ]
      }
    }
  ]
}
```

Nos exemplos, type é o discriminador normalizado: group → TransformGroup,
text → TypographyReveal, shape → ShapeReveal, mask → MaskTransition,
image → ImageReveal e path_follower → PathAnimation. CameraMove é a animação
de camera. Referências mask.target_id/path_ref são arestas tipadas, não parentes:
validar escopo, ciclos e ordem de avaliação. Escala/posição nas animações substituem
o valor base da propriedade; params.opacity multiplica a opacidade do node.
A máscara inicial é curta e atinge progress=1 antes da janela principal de leitura.

Os tamanhos e larguras são constraints da receita. O compilador mede a fonte real:
texto que não cabe não é truncado silenciosamente. Retornar TEXT_OVERFLOW e pedir
edição/revisão ou selecionar uma variante permitida; não reduzir abaixo do mínimo.
Esses desenhos são intenções técnicas concretas, ainda precisam de render e revisão
humana para demonstrar diferença estética. Os exemplos não implementam o M4.

## 8. Compilação e integração com EDL v2

Fluxo proposto, sem gravações em Project.edl, Project.plan ou Project.script:

1. Buscar projeto, storyboard, CreativeReview e snapshot no servidor; comparar
   revisão/hash esperados sob a política de concorrência existente.
2. Resolver receita exata pelo ID/versão/hash. Validar bindings de DNA/direção,
   claims e assets contra o snapshot. Expansão nunca chama LLM nem rede.
3. Instanciar os graphs com defaults, limites, texto medido, fonte local e seed
   explícita. Rejeitar linguagem não suportada, overflow e complexidade excessiva.
4. Mapear cada shot para seu intervalo EDL existente. Produzir TimelineItems do
   preset motion_scene_v1 em track caption, compatível com a projeção atual.
   A base scene_title_v1 deve continuar neutra como na bridge M3. Não acrescentar
   um track graphic incompatível e esperar que to_legacy o aceite.
5. Expandir os SoundCues para itens sound_v1 nas tracks music/sfx existentes.
   O graph conserva IDs/tempos de cue para animações, mas não toca o som novamente.
   Mistura, fades, trims e gain usam o mixer atual; pan expressivo inicial deve
   estar no WAV estéreo original. Não presumir suporte a pan por cue no mixer.
6. Coletar referências recursivas. Separar staging de áudio/imagem/vídeo/fonte/
   geometria. Validar MIME/decodificação, direitos, existência, hash e dimensões.
   O worker M3 hoje pressupõe sons: generalizar isso é trabalho explícito do M4.
7. Produzir plano imutável com snapshot editorial, EDL derivada, receita expandida,
   parâmetros, assets, provenance, versão/hash do compilador/renderer/fontes,
   arredondamentos, canvas, perfil de encode e dependências.
8. Derivar hash canônico do plano; UUID/idempotency key reutilizam o mecanismo M3.
   Repetir a requisição devolve o mesmo job; uma receita/asset/render config diferente
   cria outro hash e outro job. Não confiar no hash declarado pelo cliente.
9. Preview e export recebem o mesmo render_props e MediaGridTimelineV2. Adicionar
   somente o dispatch motion_scene_v1 e o interpretador fechado ao renderer atual.
   Efeitos são funções de frame absoluto/local, nunca relógio, rede ou estado acumulado.
10. Antes da execução e antes de disponibilizar o artefato, revalidar snapshot,
    direitos/claims, bytes e runtime. Resultado obsoleto fica indisponível com causa;
    não reclassificar APPROVED_STORYBOARD nem apagar silenciosamente a prova anterior.

O grafo tem z_index interno. No renderer atual vídeo, overlays e base têm blocos
de composição separados. M4 v1 deve manter o graph autocontido; interleaving com
vídeos da EDL fora do graph fica fora do v1, salvo alteração explícita da ordenação
e testes de regressão. Nenhum campo z_index pode prometer ordem global inexistente.

Transições entre shots são construídas nos limites existentes: saída local e entrada
local complementares, sem sobreposição temporal que altere o EDL. Match cuts usam
o estado final/inicial declarado. Crossfade com overlap que estenda dois shots requer
contrato editorial próprio e fica fora do v1. Não inventar transições a partir de prosa.

### API e erros propostos

Estender a família /api/v1/creative/.../motion existente com um discriminador de
requisição para receita, preservando o request esportivo M3. Confirmar os paths
exatos no router ao implementar; não criar um segundo serviço de render.
Adicionar leitura de capabilities/receitas locais: versões, slots, canvases, limites,
fontes e status do runtime. Nenhum endpoint deste ADR existe por causa do documento.

- 422: contrato inválido, UNSUPPORTED_INTENT, TEXT_OVERFLOW,
  COMPLEXITY_LIMIT, RECIPE_NOT_SUPPORTED ou ASSET_KIND_UNSUPPORTED.
- 409: revisão/snapshot/asset/runtime divergente, aprovação ausente/obsoleta.
- Auth e isolamento: mesmos 401/403/404 e ownership das rotas Creative existentes.
- Worker indisponível: WAITING_FOR_WORKER com evidência; direitos/runtime/licença
  impeditivos: BLOCKED com causa. Mapear para estados reais existentes ou migrar
  explicitamente, sem introduzir strings de status ad hoc.
- Falha de encode é falha, nunca artefato concluído. Timeout/lease são os atuais.

## 9. Revisão audiovisual, direitos e persistência

A aprovação editorial M1 autoriza aquele storyboard e suas dependências.
Ela não aprova automaticamente o MP4. A revisão legada em Project.plan.review
**não deve ser reutilizada sem adaptação**, pois altera um campo do snapshot M1.

Proposta de integração persistente futura: tabela append-only de revisão de artefato
derivado, vinculando project_id, job_id, plan_sha256, video_sha256, snapshot_sha256,
digest de direitos/claims, decisão, ator autenticado, notas e created_at.
Constraint de unicidade para revisão/decisão idempotente e FK para Job/Project.
O estado vigente é calculado contra o artefato e as dependências atuais.
Aprovação não migra automaticamente para uma nova versão de receita ou vídeo.

Justificativa: há um objeto persistente novo (decisão humana sobre um artefato),
sem local correto hoje para guardá-lo sem invalidar M1. A tabela não contém shots,
keyframes ou uma segunda timeline. Não criar migration nesta rodada; ao implementar,
verificar heads Alembic reais, justificar nome/revisão e testar upgrade/downgrade/
restauração em cópias SQLite e PostgreSQL isoladas.

A publicação/exportação editorial futura exige os dois gates: aprovação atual do
storyboard e revisão positiva do artefato exato. Preview técnico pode ser visto sem
essa segunda decisão, claramente identificado como aguardando avaliação.
Não reutilizar a aprovação automática da fixture como aprovação artística humana.
Uma aprovação anterior permanece no histórico quando um direito é revogado;
o download/export vigente deve ficar bloqueado com causa rastreável.

Fonts e assets entram no manifesto: origem, licença, hash, autor/importador,
limitações e relação com claims. SVG externo deve ser sanitizado offline para
geometria tipada ou raster autorizado; proibir scripts/URLs/XML no graph.
Staging por job, path traversal e links externos rejeitados, orçamento de bytes/
pixels e limpeza dos temporários conforme infraestrutura atual. Nunca aceitar
caminho absoluto vindo do graph nem buscar arquivo do computador fora da biblioteca.

## 10. Limites v1 e desempenho Windows

Limites propostos para validar antes de abrir a API; não são capacidades já entregues:

| Recurso | Limite v1 proposto |
|---|---|
| Duração total | 3–30 segundos; cada shot com pelo menos 2 frames |
| FPS | somente 30/1, consistente com Root/to_legacy atuais |
| Canvas | 1080×1920, 1920×1080 ou 1080×1080; dimensões lógicas fixas |
| Shots | até 12, sem overlaps globais ou cortes adicionais |
| JSON expandido | até 2 MiB; sem dados binários embutidos |
| Nodes | 128 expandidos por cena e 512 totais; profundidade 6 |
| Keyframes | 32 por propriedade, 8 propriedades/node, 8192 pontos globais |
| Geometria | 512 vértices por path; 4096 na composição |
| Cues | até 64; até 8 sons simultâneos; ganho individual 0..1 |
| Mídia visual | 4 imagens / 2 vídeos simultâneos; imagens ≤4096² |
| Partículas/efeitos | 64 partículas/cena dentro da cota de nodes; 2 sweeps; 2 clips |
| Arquivo de vídeo | probe obrigatório, duração/trim compatíveis, 30 FPS inicial |
| Prévia | 540×960 equivalente por scale, mesma composição e frames lógicos |

O limite de 2 MiB não autoriza payloads progressivamente maiores via referência:
validar a expansão inteira. Fonts locais aprovadas com wait/delayRender; medir
cache, fallback e glyphs. Seed fixa por receita/plano; nenhuma chamada Math.random
na avaliação. Busca por frame funciona sem reproduzir frames anteriores.

Protocolo de benchmark antes de aceitar o M4: Windows 11, CPU com 4 núcleos/8 threads,
16 GiB RAM e SSD, sem GPU dedicada; registrar modelo, energia, versões, RSS e CPU.
Comparar concorrência 1 e 2, escolher a mais estável; não presumir que mais é melhor.
Meta inicial para as três fixtures de até 30 s: export em ≤10× duração e RSS do
conjunto de processos ≤4 GiB; preview em 540p equivalente ≥24 FPS medidos por 10 s
após warm-up. São metas de aceite, **ainda não medidas nem garantidas** nesse host.
Um teste abaixo disso exige reduzir a receita ou rever o orçamento/documentar
o hardware mínimo, sem baixar silenciosamente resolução/duração do export.

A prova M3.2 levou 40,612 s para render+validação de 12 s neste ambiente;
isso não prevê o custo de todos os graphs futuros. Filters/blur, vídeos simultâneos
e paths grandes podem ser caros em Chromium software. Benchmark inclui cold start,
hot render, seek, cancelamento e recuperação de worker. Nenhuma dependência obrigatória
de GPU, VPS, serviço pago ou mudança no instalador é proposta para o v1.

## 11. Plano incremental — implementação posterior à aprovação

| Etapa futura | Entrega vertical e gate |
|---|---|
| M4.A Contrato | Schema fechado + tipos gerados + três receitas/fixtures + validadores/limites; snapshot e compatibilidade M3 preservados |
| M4.B Interpretador | Primitivas mínimas, renderer atual/Player, medição de texto, staging de mídia; paridade de frames e busca determinística |
| M4.C Fluxo Creative | Seleção de receita/slots na UI existente, API, compilador, fila, revisão de artefato, migration isolada e docs/env somente se necessário |
| M4.D Generalização/QA | Três MP4 distintos em Sports/Music/Geo, provas/hash/áudio, benchmark Windows, regressões e avaliação humana |

Cada etapa deve ter teste automatizado e evidência concreta; M4.A/B podem usar
harness local, mas M4 só é entregue quando o fluxo completo C/D funcionar.
Não marcar um exemplo JSON como render pronto. Não implementar todas as primitivas
se os três casos já forem expressos por um subconjunto; qualquer ausência deve ser
declarada em capabilities. Nada dessas etapas é iniciado neste PR.

## 12. Estratégia de testes

- Contratos: unknown fields, tipos/coerção, NaN/Infinity, IDs duplicados, parent cycles,
  referências inválidas, cue fora do shot, keyframes colapsados e expansão excessiva.
- Adversariais: JS/HTML/URL em campos, paths absolutos, traversal, MIME falso, fontes
  externas, arquivo alterado após enqueue, arquivo ausente e imagem descomprimida grande.
- Compilador: mesmos inputs → JSON/hash iguais; defaults/seed/fonte/receita mudam hash;
  ordem de JSON key não muda hash; ordem dos nodes muda quando semântica mudar.
- Tempo: limites entre shots, 29/30/31 ms, cue no último frame, quantização absoluta,
  seeks fora de ordem; sem dependência da execução do frame anterior.
- API/DB: ownership, 409 concorrente, idempotência sob disputa, direitos/claims revogados,
  aprovação ausente, alteração durante encode, worker offline; migrações isoladas e restore.
- Imagem: frames determinísticos no mesmo runtime, tolerância documentada entre hosts;
  paridade preview/export sem somas de offset duplicadas, fontes prontas e sem clipping.
- Áudio: decode completo, canais/taxa, envelopes de cue dentro de 1 frame, LUFS/true peak;
  áudio original/licenciado real nos três filmes, sem fingir sync de vídeo silencioso.
- Render: MP4 H.264/AAC, duração/frames esperados, FFprobe, SHA, no accidental black,
  safe areas e legibilidade; limites de CPU/RSS e cancelamento.
- Regressões: testes Python/Ruff, web/renderer typecheck, build/preview e M3 original/
  editorial/broadcast/broadcast_final; zero mutação de Project.plan/script/edl na derivação.
- Revisão humana: composição/ritmo/transição/continuidade/som em cada filme, leitura
  em celular e fones/alto-falante. Métrica de movimento não aprova qualidade artística.

## 13. Critérios objetivos de aceite do M4

1. Três projetos descartáveis aprovados geram três vídeos completos e reproduzíveis
   pelo mesmo runtime, conjunto de primitivas e worker, sem criar componentes React
   específicos para cada vídeo. Diferenças vêm das três receitas e dados aprovados.
2. Sports usa hierarquia tipográfica e transições de impacto; Music organiza capa,
   órbitas e frases sonoras; Geo prioriza geometria, percurso e informação com fonte.
   Trocar texto/paleta no mesmo layout não satisfaz este gate; aprovação estética é humana.
3. Cada vídeo possui EDL derivada, receita/hash, snapshot, assets/licenças, cues,
   MP4/hash/FFprobe, frames e revisão de artefato exata; nada sobrescreve o projeto original.
4. Buscar frames fora de ordem reproduz a mesma imagem no runtime fixado; preview
   e export usam mesmos props. Diferenças de codec/tolerâncias são documentadas.
5. Specs inválidas/obsoletas são rejeitadas com erro verificável. Nenhum fallback
   silencioso, LLM ou interpretação de string gera sucesso fictício.
6. Testes, restauração isolada, benchmark e QA audiovisual descritos acima passam;
   limites de hardware medidos constam no relatório, sem prometer qualquer PC.
7. Revisão/publicação não pode ser contornada por receita; nova versão invalida somente
   a disponibilidade da aprovação dependente, mantendo histórico auditável.
8. Repositório mantém migrações lineares, compatibilidade de projetos legados e
   instalador/dados reais preservados durante as provas.

## 14. Riscos e decisões pendentes

| Risco | Tratamento proposto / decisão |
|---|---|
| Grafo vira segunda timeline | item temporal somente na EDL; revisão recusa start/end global em nodes |
| Projeção descarta/duplicação de textos | preset caption fechado; base neutra; fixtures com múltiplos shots |
| Ordem de layers inconsistente | graph autocontido no v1; sem prometer z global |
| Snapshot invalidado pela revisão legada | revisão por artefato, sem escrita em Project.plan |
| Receita injetar conteúdo factual | bindings fechados ao snapshot/claims aprovados |
| Fonts e medidas variáveis | fonte local/hash, espera explícita, overflow bloqueante |
| Resource exhaustion | limites pré/pós-expansão + probe + timeout + RSS benchmark |
| Audio overmix ou cue deslocado | um mixer, headroom medido, quantização única e QA de envelopes |
| Nova dependência alterar licença/custo | revisão oficial e pin antes de integrar; nenhuma nova neste ADR |
| Estética semelhante nos três estilos | gate humano obrigatório e receitas com gramática espacial diferente |
| Reprodução entre Chromium/FFmpeg distintos | manifesto de versões, não promessa de MP4 bit idêntico entre hosts |

Ficam pendentes para implementação: schema final dos erros/capabilities,
migration de revisão por artefato, protocolo de canonicalização numérica com vetores
de teste, cobertura de glyphs e benchmark no hardware mínimo. Resolver antes de
abrir cada superfície pública; nenhuma dessas lacunas deve ser escondida como pronta.

## 15. Fora do M4 v1

LLM automático, execução de scripts, editor livre/segunda timeline, marketplace,
detecção BPM automática, material 3D/PBR, Blender/WebGL obrigatório, Motion Canvas,
Cavalry/Jitter, pesquisa de fatos ao renderizar, mapas/tiles remotos ao renderizar,
postagem automática, serviço pago, deploy VPS, atualização da instalação principal,
redesign Lovable, suporte a FPS/formatos arbitrários e migração geral do projeto.

**Entrega desta rodada:** somente este ADR. Implementar o M4 exige avaliação humana
da prova M3.2 e autorização posterior; nenhum motor genérico foi criado.
