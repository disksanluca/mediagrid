param([Parameter(Mandatory=$true)][string]$TextFile, [Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speaker.SetOutputToWaveFile($OutputFile)
    $speaker.Speak([System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8))
} finally {
    $speaker.Dispose()
}
