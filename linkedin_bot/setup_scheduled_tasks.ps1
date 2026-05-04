#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Registers (or re-registers) Task Scheduler tasks for:
      1. LinkedIn bot + Flask webapp at 08:30 daily – wakes PC from hibernate/sleep
      2. Flask webapp at every logon (fallback so it's always running after login)
    
    Run this script once as Administrator. Re-run to refresh after changes.
#>

$ErrorActionPreference = "Stop"

$psExe     = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$guardScript = "D:\cv_portofolio\linkedin_bot\run_daily_guard.ps1"
$webappDir   = "D:\cv_portofolio\webapp"
$pythonExe   = "D:\cv_portofolio\.venv\Scripts\python.exe"
$logPath     = "D:\cv_portofolio\linkedin_bot\scheduler_output.log"

# ── Enable wake timers in power settings (required for hibernate wake) ────────
Write-Host "Enabling wake timers in power settings..." -ForegroundColor Cyan
# Active power scheme
$scheme = (powercfg /getactivescheme) -replace '.*GUID: ([0-9a-f-]+).*', '$1'

# Enable wake timers for both AC and DC (hibernate uses RTCWAKE under the hood)
powercfg /setacvalueindex $scheme SUB_SLEEP RTCWAKE 1  2>$null
powercfg /setdcvalueindex $scheme SUB_SLEEP RTCWAKE 1  2>$null
powercfg /setactive $scheme

Write-Host "Wake timers enabled." -ForegroundColor Green

# ── Helper: delete task if it already exists ──────────────────────────────────
function Remove-TaskIfExists([string]$Name) {
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
        Write-Host "Removed old task: $Name"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# TASK 1: LinkedIn bot + Flask at 08:30 – wakes from hibernate
# ─────────────────────────────────────────────────────────────────────────────
$task1Name = "LinkedInBot_Daily_0830"
Remove-TaskIfExists $task1Name

$action1 = New-ScheduledTaskAction `
    -Execute $psExe `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$guardScript`"" `
    -WorkingDirectory "D:\cv_portofolio\linkedin_bot"

# Daily trigger at 08:30, WakeToRun = $true (wakes PC from sleep AND hibernate)
$trigger1 = New-ScheduledTaskTrigger -Daily -At "08:30"

$settings1 = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

# Run as SYSTEM so it works even at the lock screen / after hibernate resume
$principal1 = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $task1Name `
    -Action   $action1 `
    -Trigger  $trigger1 `
    -Settings $settings1 `
    -Principal $principal1 `
    -Description "Wake PC at 08:30, start Flask webapp, run LinkedIn bot" | Out-Null

Write-Host "Registered: $task1Name (wakes from hibernate at 08:30)" -ForegroundColor Green

# ─────────────────────────────────────────────────────────────────────────────
# TASK 2: Flask webapp at logon (ensures Flask is always up after any login)
# Use SYSTEM to avoid credential prompts on password-protected user accounts.
# ─────────────────────────────────────────────────────────────────────────────
$task2Name = "FlaskWebapp_AtLogon"
Remove-TaskIfExists $task2Name

$flaskArgs = "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command " +
    "& { Set-Location '$webappDir'; " +
    "Start-Process -FilePath '$pythonExe' -ArgumentList 'app.py' " +
    "-WorkingDirectory '$webappDir' -WindowStyle Hidden " +
    "-RedirectStandardOutput '$webappDir\flask_stdout.log' " +
    "-RedirectStandardError '$webappDir\flask_stderr.log' }"

$action2 = New-ScheduledTaskAction `
    -Execute $psExe `
    -Argument $flaskArgs `
    -WorkingDirectory $webappDir

$trigger2 = New-ScheduledTaskTrigger -AtLogOn

$settings2 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew

$principal2 = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $task2Name `
    -Action   $action2 `
    -Trigger  $trigger2 `
    -Settings $settings2 `
    -Principal $principal2 `
    -Description "Start Flask webapp automatically after every login" | Out-Null

Write-Host "Registered: $task2Name (starts Flask at every logon)" -ForegroundColor Green

# ─────────────────────────────────────────────────────────────────────────────
# TASK 3: On-resume-from-hibernate trigger (Event ID 107 in System log)
# This fires the guard script whenever the PC wakes from any sleep/hibernate
# ─────────────────────────────────────────────────────────────────────────────
$task3Name = "LinkedInBot_OnWake"
Remove-TaskIfExists $task3Name

$action3 = New-ScheduledTaskAction `
    -Execute $psExe `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$guardScript`"" `
    -WorkingDirectory "D:\cv_portofolio\linkedin_bot"

# Event 107 in Microsoft-Windows-Power-Troubleshooter = system resume from sleep/hibernate
$wakeEventXml = @"
<QueryList>
  <Query Id="0" Path="System">
    <Select Path="System">*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]</Select>
  </Query>
</QueryList>
"@

$trigger3 = Get-CimClass -Namespace ROOT\Microsoft\Windows\TaskScheduler -ClassName MSFT_TaskEventTrigger |
    New-CimInstance -ClientOnly -Property @{
        Subscription  = $wakeEventXml
        Enabled       = $true
        Delay         = "PT3M"   # wait 3 min after wake so network is ready
    }

$settings3 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

$principal3 = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $task3Name `
    -Action   $action3 `
    -Trigger  $trigger3 `
    -Settings $settings3 `
    -Principal $principal3 `
    -Description "Run guard script 3 min after PC wakes from hibernate/sleep" | Out-Null

Write-Host "Registered: $task3Name (runs 3 min after wake from hibernate)" -ForegroundColor Green

Write-Host ""
Write-Host "All tasks registered successfully." -ForegroundColor Cyan
Write-Host "To verify: Get-ScheduledTask | Where-Object TaskName -like 'LinkedIn*','Flask*' | Format-Table"
