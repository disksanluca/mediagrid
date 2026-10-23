# Voz local configurável no Windows

O ambiente Settings mostra as vozes pt-BR habilitadas em `System.Speech` e
permite salvar uma voz e velocidade de -5 a 5. A escolha fica em
`data/settings.json` (`voice_name`, `voice_rate`), preservada no backup. O
servidor recusa essa configuração: ela pertence ao desktop que sintetiza.
Não há download de modelos, conta externa nem custo de API.

O job VOICE recebe o digest da escolha ao entrar na fila. Se a preferência
mudar antes ou durante a síntese, o job falha com motivo explícito; Retry
adota a preferência atual. O manifesto do WAV agora contém hash do roteiro,
hash do áudio e digest da configuração. A mudança da escolha marca o WAV
anterior como não pronto para novos renders, sem apagar o MP4 existente.
Manifestos antigos com um ou dois digests continuam legíveis quando a
configuração permanece no padrão. A promoção cria a pasta `voice/` em um
workspace novo; isso também corrige a falha de primeiro uso descoberta pelo
teste de integração.

## Verificação executada em 23/10/2026

```powershell
.venv\Scripts\python.exe scripts/prove_official_politics.py --proposal-id 2648811 --voice-name "Microsoft Maria Desktop" --voice-rate -1
```

Na pasta local `data/politics-proof/20261023T203345Z/`, o PL 5650/2026 da
Câmara gerou quatro cenas, quatro alegações pendentes, WAV com manifesto de
três digests e MP4 H.264/AAC 1080×1920 de 48,004 s, SHA-256
`e8ff9de696d95c3d9c22ad4f5698f3cd5cca224080ee88142c9947c797849984`.
O projeto permaneceu em QC e exportação sem revisão foi negada com 409.
O áudio foi sintetizado de fato, mas sua naturalidade não recebeu aprovação
auditiva humana completa. Esta instalação expôs somente a voz `Microsoft Maria
Desktop` para o processo de síntese; novas opções dependem das vozes pt-BR
instaladas e habilitadas no Windows.

A implementação usa `GetInstalledVoices`, `SelectVoice` e `Rate` de
[System.Speech.Synthesis.SpeechSynthesizer](https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer?view=netframework-4.8.1).
A documentação da Microsoft confirma que [SelectVoice](https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.selectvoice?view=netframework-4.8.1)
seleciona uma voz instalada pelo nome. O script exige correspondência exata e
cultura pt-BR antes de chamar essa API. Nenhum protocolo externo foi alterado.

Não há migração SQL nem nova variável em `.env.example`. Sem instalação de
build novo no PC do usuário, VPS, serviço pago ou publicação.
