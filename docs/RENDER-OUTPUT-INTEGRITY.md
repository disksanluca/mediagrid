# Integridade da saída do render local

O download do MP4 em `GET /api/v1/projects/{id}/output`, a aprovação humana e
o export manual conferem o arquivo em `data/renders` contra o SHA-256 e o hash
do EDL registrados no job `RENDER` concluído mais recente. Quando o job traz
hash de revisão EDL v2, a revisão atual também precisa corresponder. Ausência
de job verificável, MP4 alterado ou timeline divergente devolvem `409` e não
transformam um arquivo avulso em render aprovado. O download válido inclui
`ETag` com o SHA-256 do vídeo.

Projetos já aprovados antes de existir hash no job continuam acessíveis se a
revisão humana persistida confere com os hashes atuais de MP4 e EDL. Essa
compatibilidade não permite criar uma aprovação nova sem job verificável.

## Prova local em 23/10/2026

- `python scripts/prove_video_pipeline.py --format vertical` gerou, em base
  SQLite isolada, voz Windows e MP4 local com `VOICE`/`RENDER` em `SUCCEEDED`.
  A prova agora chama a rota de download e compara resposta, `ETag`, bytes do
  MP4 e hash do job.
- Arquivo ignorado pelo Git: `data/rea-proof/20261023T201524Z/renders/`
  (`b0e32368-a984-4b5a-a361-efa611d20bfa.mp4`). FFprobe: H.264/AAC,
  1080×1920, 31,0 s. SHA-256:
  `57ee11c5c4259e59d97b01979fc18a477c9fd75a52bc1664f20dfe465822eaec`.
- Quadro de 15 s inspecionado: texto legível, composição tipográfica esparsa.
  A prova não equivale a direção criativa aprovada; áudio não foi ouvido
  integralmente nesta rodada. Não houve material de terceiros, publicação,
  API paga nem instalação no PC do usuário.
- Testes de rota rejeitam MP4 órfão e arquivo alterado após o job. Testes de
  revisão factual usam job e hash sintéticos persistidos para isolar o gate
  editorial. A suíte completa e CI estão registradas no PR desta etapa.

Sem migração de banco ou variável nova em `.env.example`. O hash é calculado
na leitura, o que aumenta I/O para downloads grandes; otimização precisa manter
verificação de integridade. A checagem de arquivo e o streaming HTTP não são
atômicos entre processos; reconciliação de artefatos após queda ainda é etapa
separada antes do worker remoto.
