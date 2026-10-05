param([Parameter(Mandatory=$true)][string]$AudioFile, [Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
try {
    $engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
    $engine.SetInputToWaveFile($AudioFile)
    $lines = New-Object System.Collections.Generic.List[string]
    while ($true) {
        $result = $engine.Recognize()
        if ($null -eq $result) { break }
        if ($result.Confidence -ge 0.35) { $lines.Add($result.Text) }
    }
    [System.IO.File]::WriteAllText($OutputFile, ($lines -join " "), [System.Text.Encoding]::UTF8)
} finally {
    $engine.Dispose()
}
