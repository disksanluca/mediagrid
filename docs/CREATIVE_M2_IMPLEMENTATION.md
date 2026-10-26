# MediaGrid M2 — Creative Director Workspace

Data: 25/10/2026 (America/Sao_Paulo). Base conferida antes das alterações: PR #43, `codex/creative-m1-foundation`, commit `152ccc01be7966d0a6eb040d124fece8a5b1a591`, árvore limpa. Branch de implementação: `codex/creative-m2-workspace`. Versões existentes: React 19.1.1, Next.js 16.3.8, TypeScript 5.9.2, FastAPI `>=0.115,<1`, SQLAlchemy `>=2,<3`, Python 3.12.10, Node 24.19.0. Nenhuma dependência foi adicionada.

## Arquivos e decisões

| Arquivo | Implementação |
| --- | --- |
| `apps/web/components/creative/creative-workspace.tsx` | Cinco etapas editáveis no projeto: brief, DNA do canal, três direções, storyboard e revisão. GETs iniciais aceitam 404 como ausência real. Salvamento explícito com revisão esperada. Revisão mostra status, bloqueios e SHA-256 reais. |
| `apps/web/components/creative/storyboard-draft.ts` | Operações imutáveis de divisão, ajuste de duração adjacente, movimentação, remoção e sincronização da duração do brief, mantendo IDs e tempos contíguos. |
| `apps/web/components/creative/storyboard-draft.test.ts` | Três testes de invariantes temporais e proteção contra duração inválida. |
| `apps/web/components/creative/creative-workspace.css` | Estética dark Atelier OS com tokens existentes, contraste, foco, layout adaptável e redução de movimento. |
| `apps/web/components/control-panel.tsx` | Entrada pelo projeto no Studio/Editor/Motions e abas **Creative Director / Editor e produção**. O editor existente continua acessível; o workspace criativo permanece montado ao alternar abas, preservando o rascunho. |
| `apps/web/lib/types.ts`, `apps/web/lib/api.ts` | Tipos fiéis aos contratos Pydantic do M1, sete pares de operações REST e erro HTTP tipado. Erros 422 mostram campo e causa; 409 exige resolução explícita. |
| `docs/testing/creative-m2/*.jpg` | Capturas do navegador real conectado ao FastAPI e SQLite descartável. |

Não houve novo endpoint, migração, modelo de banco, worker, alteração no EDL, Remotion, FFmpeg, instalador ou dependência externa. O storyboard é planejamento; não é uma segunda timeline renderizável nem um player. `APPROVED_STORYBOARD` aprova somente a revisão de storyboard.

## Comportamentos entregues

1. **Brief:** todos os campos `CreativeBrief` do M1, fontes declaradas, confirmação humana por fonte, seleção de assets existentes, duração/FPS e revisão. O formato acompanha o projeto. Não são gerados fatos ou URLs.
2. **DNA:** paleta hexadecimal, tipografia, tom, energia, itens obrigatórios, itens a evitar e limite de palavras por cartão. Aviso visível de invalidação de projetos do canal; só grava pelo botão.
3. **Direções:** GET/POST originais, três cartões completos, origem `deterministic_reference` visível, status `CURRENT`/`STALE`, seleção para o rascunho do storyboard. Nenhuma thumbnail/IA audiovisual é simulada.
4. **Storyboard:** planos com beat, texto, visual, câmera, movimento, áudio, assets e claims existentes. Régua proporcional e tempos calculados. Dividir, mover, remover, ajustar par de planos e ajustar o último plano à nova duração do brief operam só no rascunho até **Salvar storyboard**.
5. **Revisão:** snapshot/hash e bloqueios do backend, decisão APPROVE/REVISE/REJECT com nome do operador e revisões esperadas. Aprovação exige três confirmações explícitas e não libera publicação ou MP4.
6. **Concorrência:** em 409, o rascunho continua visível; após atualizar metadados, salvar fica bloqueado até escolher **Carregar versão do servidor** ou **Aplicar meu rascunho sobre a revisão atual**. A segunda opção avisa que pode substituir mudanças concorrentes. Atualização manual também reconhece mudança remota de revisão.

## Fluxo ponta a ponta executado

Banco em `data/creative-m2-proof/workspace.db` (ignorado pelo Git), criado com `DATABASE_URL` e `MEDIAGRID_DATA_DIR` específicos e `python -m apps.api.migrate`. API em `127.0.0.1:8000`, Next dev em `127.0.0.1:3000`. Canal e projeto sintéticos criados para este ensaio, sem mídia do usuário. O material factual de bloqueio usa `example.org` **apenas como entrada sintética não revisada**.

No navegador real: 404 inicial apresentado como revisão 0; brief salvo na revisão 1; DNA salvo na revisão 1; três direções retornadas na revisão 1; direção `evidence-led` selecionada; storyboard de 30 s dividido em 12 s + 18 s e salvo na revisão 1; revisão retornou `REVIEW_REQUIRED`; aprovação humana de teste retornou `APPROVED_STORYBOARD`; recarga da página manteve brief e aprovação; edição de um plano gravou revisão 2 e retornou `STALE`. Duas gravações concorrentes foram simuladas contra o banco descartável: a UI recebeu HTTP 409, manteve o texto local, atualizou para revisão 4 e exigiu a escolha explícita. Escolher a versão do servidor preservou a alteração concorrente. Uma URL inválida produziu 422 com `content › fontes › 0 › URL: URL inválida`. Uma fonte não revisada, claim pendente e asset com direitos `UNKNOWN` produziram `DIRECTIONS_STALE`, `RIGHTS_BLOCKED`, `Factual claims need individual approval` e `Factual brief needs reviewed sources`; o botão de aprovação permaneceu desabilitado. Nenhum MP4 foi renderizado neste M2.

## Capturas e inspeção visual

- [Direções em 1440 px](testing/creative-m2/directions-1440.jpg), [1280 px](testing/creative-m2/directions-1280.jpg), [1000 px](testing/creative-m2/directions-1000.jpg) e [390 px](testing/creative-m2/directions-390.jpg).
- [Régua e primeiro plano no navegador móvel](testing/creative-m2/storyboard-ruler-mobile.jpg).
- [Status de aprovação do storyboard](testing/creative-m2/review-status-mobile.jpg) e [bloqueios reais do backend](testing/creative-m2/review-blocked-mobile.jpg).

As capturas são JPEGs retornados pelo navegador, sem mock. O ensaio de viewport mediu `innerWidth` de 1440/1280/1000/390 e `scrollWidth` de 1425/1265/985/375, respectivamente: sem overflow horizontal da página. Os cartões mediram 422 px em 1440, 367 px em 1280, 875 px em 1000 e 306 px em 390, indicando 3 colunas largas e 1 coluna nos dois menores tamanhos. O navegador de teste captura apenas a porção visível em 390 px; o DOM foi medido no viewport configurado de 390 × 900. Logs de console `error`/`warn`: lista vazia durante o ensaio. Foco visível e `prefers-reduced-motion` estão no CSS; a revisão por teclado foi inspecionada no DOM e CSS, sem automação completa de leitor de tela.

## Testes executados

| Comando / verificação | Resultado |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests` | **135 passed, 1 skipped** (Blender opt-in), 123,12 s. Inclui testes M1 de concorrência, reinício, rights/facts e migração. |
| `.venv/Scripts/python.exe -m ruff check .` | Passou. |
| `node node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json` | Passou. |
| `node node_modules/typescript/bin/tsc --noEmit -p apps/renderer/tsconfig.json` | Passou. |
| `node node_modules/vitest/vitest.mjs run apps/web` | **3 passed**. |
| `node node_modules/next/dist/bin/next build apps/web` | Passou: compilação, TypeScript e geração estática. |
| Navegador real + API + SQLite isolado | Passou: criação, persistência, aprovação, STALE, 409, 422 e bloqueios. |
| `git diff --check` | Passou. |

O workflow Windows em PR inclui build Tauri e smoke do instalador; registrar o resultado da CI quando a branch remota for aberta. O workflow PostgreSQL filtra apenas alterações de API/migrações/workers e não é acionado por este M2 de frontend. O M1 já validou o schema PostgreSQL na PR #43; não houve mudança de schema nesta etapa.

## Limitações e M3

- **REAL local:** UI, API, SQLite, revisão por hash, roteamento de erros e estados. O backend M1 continua a autoridade sobre validade e bloqueios.
- **Não implementado neste M2:** geração audiovisual automática, animatic, renderização a partir do storyboard, LLM, bibliotecas de motion externas, exportação e publicação pelo Creative Director.
- **Limite editorial:** `fact_reviewed`, rights e confirmations são declarações de operador; nenhum serviço externo atesta a veracidade. O caso de aprovação do ensaio foi ficcional e sintético; não deve ser usado como prova de conteúdo político publicável.
- **Rascunho local:** sobrevive à troca entre abas do projeto. Recarregar a página descarta mudanças que não foram salvas; a interface exibe aviso de rascunho, mas não oferece recuperação após fechar o navegador.
- **M3:** poderá consumir brief/DNA/direção/storyboard versionados e o snapshot aprovado, com composição audiovisual real, proveniência de assets e revisão de artefato. O EDL v2 e o gate de publicação existentes devem continuar sendo as autoridades de render e entrega.

Para verificar manualmente: configure um banco descartável, migre, inicie FastAPI e Next, crie canal e projeto pelas telas existentes, abra o projeto e selecione **Creative Director**. Salve DNA e brief, gere direções, escolha uma, preencha e salve storyboard, então consulte Revisão. Para voltar ao pipeline anterior, use **Editor e produção**. Nenhum banco instalado, deploy, VPS, serviço pago ou merge foi alterado.
