param(
    [Parameter(Mandatory=$true)][string]$TextFile,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [string]$VoiceName = "",
    [ValidateRange(-5, 5)][int]$Rate = 0
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $portugueseVoices = @($speaker.GetInstalledVoices() |
        Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq "pt-BR" })
    if ($VoiceName) {
        $portugueseVoice = $portugueseVoices |
            Where-Object { $_.VoiceInfo.Name -ceq $VoiceName } |
            Select-Object -First 1
    } else {
        $portugueseVoice = $portugueseVoices | Select-Object -First 1
    }
    if (-not $portugueseVoice) {
        throw "Nenhuma voz pt-BR compatível com a seleção está instalada."
    }
    $speaker.SelectVoice($portugueseVoice.VoiceInfo.Name)
    $speaker.Rate = $Rate
    $speaker.SetOutputToWaveFile($OutputFile)
    $speaker.Speak([System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8))
} finally {
    $speaker.Dispose()
}
