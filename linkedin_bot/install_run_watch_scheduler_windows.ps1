#Requires -Version 5.1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$schedulerScript = Join-Path $PSScriptRoot "run_watch_scheduler.py"
$configFile = Join-Path $PSScriptRoot ".scheduler.env"
$configExample = Join-Path $PSScriptRoot ".scheduler.env.example"

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

if (-not (Test-Path $configFile) -and (Test-Path $configExample)) {
    Copy-Item $configExample $configFile
    Write-Host "Created $configFile from template. Fill in your dashboard email/password before relying on automatic runs." -ForegroundColor Yellow
}

$taskName = "AutoApply_RunWatchScheduler"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupCmd = Join-Path $startupDir "AutoApply_RunWatchScheduler.cmd"

function Install-StartupLauncher {
    $launcher = "@echo off`r`nstart `"`" `"$pythonExe`" `"$schedulerScript`" --daemon`r`n"
    Set-Content -Path $startupCmd -Value $launcher -Encoding ASCII
    Write-Host "Task Scheduler registration was unavailable. Installed Startup launcher instead:" -ForegroundColor Yellow
    Write-Host "  $startupCmd" -ForegroundColor Yellow
}

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "`"$schedulerScript`" --daemon" `
    -WorkingDirectory $repoRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Highest

try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Start the AutoApply Run and Watch desktop scheduler at Windows logon." | Out-Null

    if (Test-Path $startupCmd) {
        Remove-Item $startupCmd -Force -ErrorAction SilentlyContinue
    }

    Write-Host "Registered scheduled task: $taskName" -ForegroundColor Green
}
catch {
    Install-StartupLauncher
}

Write-Host "The scheduler will start when you log in and will check your local dashboard schedule every minute." -ForegroundColor Cyan
Write-Host "Config file: $configFile" -ForegroundColor Cyan
