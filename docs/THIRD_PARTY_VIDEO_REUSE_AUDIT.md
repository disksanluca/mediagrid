# Auditoria de reuso para agentes criativos locais

Consulta em 2026-11-03/04 aos repositórios oficiais e respectivos arquivos de licença. **Nenhum código, receita, prompt, modelo ou asset desses projetos foi copiado ou executado nesta entrega.** A MediaGrid usa seus próprios contratos M1/M4, FastAPI, worker e Remotion já existentes.

| Projeto | Commit examinado | Licença observada | Decisão nesta entrega |
| --- | --- | --- | --- |
| [Remotion skills](https://github.com/remotion-dev/skills) | `c7cb2fdcacd134fb2ccb9b7a44f9ffa44e467271` | O endpoint oficial `/license` devolveu 404; licença do repositório não verificada | Consultar conceitos de boas práticas apenas; não copiar skills. |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | `1266a3ec4831289c4d893d42dd5102723658039a` | [Apache-2.0](https://github.com/Vincentwei1021/video-shotcraft/blob/main/LICENSE) | Referência de decomposição em shots; integração de runtime não avaliada. |
| [Jellyfish](https://github.com/Forget-C/Jellyfish) | `a9678194ddf2d9be3ccbe78d4287d87d5089e123` | [Apache-2.0](https://github.com/Forget-C/Jellyfish/blob/main/LICENSE) | Referência de fluxo de roteiro/storyboard; não instalar outra aplicação. |
| [VideoClaw](https://github.com/HITsz-TMG/VideoClaw) | `16c1ce0b553e30eff90ff1274e8a8a63c1d548a3` | [MIT](https://github.com/HITsz-TMG/VideoClaw/blob/main/LICENSE) | Referência de orquestração; não incorporar por sobreposição com o worker MediaGrid. |
| [OpenMontage](https://github.com/calesthio/OpenMontage) | `d21f5d4eaa08422b09c7091757a05affcbabb35b` | [AGPL-3.0](https://github.com/calesthio/OpenMontage/blob/main/LICENSE) | Não incorporar diretamente; impacto de distribuição e obrigações de licença precisam de revisão específica. |
| [video-talkcraft](https://github.com/Vincentwei1021/video-talkcraft) | `a7c29edfb2404612dde6a5a1c8aa94232e85625b` | [PolyForm Noncommercial 1.0.0](https://github.com/Vincentwei1021/video-talkcraft/blob/main/LICENSE); uso comercial requer autorização do autor | Não incorporar diretamente. |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | `2c75dc1b379a59e0880619d029607af5169a62ef` | [GPL-3.0](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE) | Candidato futuro para geração visual local em processo isolado; modelo, GPU, licença dos pesos e distribuição ainda não avaliados. |

Os SHAs identificam o HEAD remoto visto no momento da consulta, não uma dependência fixada do projeto. Para qualquer incorporação futura, revisar licença no commit exato, dependências transitivas, pesos e assets, custos de memória, termos de uso e testes de isolamento com a Biu. As decisões acima não concedem autorização de reuso comercial de materiais externos.
