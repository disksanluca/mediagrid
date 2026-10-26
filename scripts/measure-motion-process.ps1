param(
  [Parameter(Mandatory=$true)][int]$RootProcessId,
  [Parameter(Mandatory=$true)][string]$StopPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = "Stop"
$peakBytes = 0L
$samples = 0
$cpu = @{}
$cpuInitial = @{}
$observed = [System.Collections.Generic.HashSet[int]]::new()
$timer = [System.Diagnostics.Stopwatch]::StartNew()
while (-not (Test-Path -LiteralPath $StopPath)) {
  $all = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId)
  $ids = [System.Collections.Generic.HashSet[int]]::new()
  [void]$ids.Add($RootProcessId)
  do {
    $added = $false
    foreach ($item in $all) {
      if ($item.ProcessId -ne $PID -and $ids.Contains([int]$item.ParentProcessId)) {
        if ($ids.Add([int]$item.ProcessId)) { $added = $true }
      }
    }
  } while ($added)
  $bytes = 0L
  foreach ($processId in $ids) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
      $bytes += $process.WorkingSet64
      if (-not $cpuInitial.ContainsKey($processId)) {
        $cpuInitial[$processId] = $process.TotalProcessorTime.TotalSeconds
      }
      $cpu[$processId] = $process.TotalProcessorTime.TotalSeconds
      [void]$observed.Add($processId)
    }
  }
  $peakBytes = [Math]::Max($peakBytes,$bytes)
  $samples++
  Start-Sleep -Milliseconds 500
}
$cpuDelta = 0.0
foreach ($processId in $cpu.Keys) { $cpuDelta += $cpu[$processId] - $cpuInitial[$processId] }
@{
  measurement="sampled Windows process-tree working sets; shared pages may be counted twice"
  interval_ms=500
  samples=$samples
  peak_working_set_mib=[Math]::Round($peakBytes/1MB,2)
  observed_processes=$observed.Count
  observed_cpu_seconds=[Math]::Round($cpuDelta,3)
  equivalent_one_core_percent=[Math]::Round(100*$cpuDelta/$timer.Elapsed.TotalSeconds,2)
  logical_cores=[Environment]::ProcessorCount
  measured_seconds=[Math]::Round($timer.Elapsed.TotalSeconds,3)
  caveat="CPU deltas from first to last observed sample; excludes startup before first sample and missed short-lived children. RSS sums Windows working sets, not private bytes."
} | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding utf8
