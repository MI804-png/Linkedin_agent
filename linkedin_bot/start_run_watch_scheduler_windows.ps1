#Requires -Version 5.1

param(
    [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$schedulerScript = Join-Path $PSScriptRoot "run_watch_scheduler.py"
$pythonExe = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found under $repoRoot\.venv\Scripts."
}

if (-not (Test-Path $schedulerScript)) {
    throw "Scheduler script not found: $schedulerScript"
}

$alreadyRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*run_watch_scheduler.py*" }
if ($alreadyRunning) {
    exit 0
}

$startScheduler = $AutoApprove.IsPresent
if (-not $startScheduler) {
    Add-Type -AssemblyName System.Windows.Forms
    $message = @(
        "Allow AutoApply scheduler to start for this Windows session?",
        "",
        "Yes: start the scheduler and let it watch your saved bot schedule.",
        "No: keep the scheduler off until you start it manually."
    ) -join [Environment]::NewLine

    $result = [System.Windows.Forms.MessageBox]::Show(
        $message,
        "AutoApply Scheduler Permission",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question,
        [System.Windows.Forms.MessageBoxDefaultButton]::Button2
    )
    $startScheduler = $result -eq [System.Windows.Forms.DialogResult]::Yes
}

if (-not $startScheduler) {
    exit 0
}

Start-Process `
    -FilePath $pythonExe `
    -ArgumentList "`"$schedulerScript`" --daemon" `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden