param(
    [switch]$TestAlarm
)

$ErrorActionPreference = "Continue"

$botDir    = "D:\cv_portofolio\linkedin_bot"
$webappDir = "D:\cv_portofolio\webapp"
$pythonExe = "D:\cv_portofolio\.venv\Scripts\python.exe"
$runHistoryPath = Join-Path $botDir "run_history.json"
$logPath   = Join-Path $botDir "scheduler_output.log"
$alarmPath = Join-Path $botDir "fbi_police_alarm.wav"

Set-Location $botDir

function Write-GuardLog {
    param([string]$Message)

    $line = "[$(Get-Date -Format o)] $Message"
    try {
        Add-Content -Path $logPath -Value $line -ErrorAction Stop
    }
    catch {
        # If the main log is temporarily locked by another run, append to a fallback log.
        try {
            Add-Content -Path (Join-Path $botDir "scheduler_output_fallback.log") -Value $line -ErrorAction SilentlyContinue
        }
        catch {
            # Intentionally ignore logging failures to keep the automation running.
        }
    }
}

# ── Ensure Flask webapp is running ───────────────────────────────────────────
function Start-FlaskIfNotRunning {
    $running = Get-Process -Name "python" -ErrorAction SilentlyContinue |
        Where-Object { try { $_.CommandLine -like "*webapp*app.py*" } catch { $false } }

    if (-not $running) {
        Write-GuardLog "Starting Flask webapp..."
        Start-Process -FilePath $pythonExe `
            -ArgumentList "app.py" `
            -WorkingDirectory $webappDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $webappDir "flask_stdout.log") `
            -RedirectStandardError  (Join-Path $webappDir "flask_stderr.log")
        Write-GuardLog "Flask webapp started."
    } else {
        Write-GuardLog "Flask webapp already running (PID $($running[0].Id))."
    }
}

Start-FlaskIfNotRunning

function Invoke-RunAlarm {
    param([string]$SoundPath)

    try {
        if (Test-Path $SoundPath) {
            $player = New-Object System.Media.SoundPlayer $SoundPath
            $player.Load()
            $player.PlaySync()
            return
        }
    }
    catch {
        # Ignore and use console beep fallback below.
    }

    # Fallback alarm pattern if custom WAV is missing or cannot play.
    try { [console]::beep(1200, 400) } catch { }
    Start-Sleep -Milliseconds 150
    try { [console]::beep(900,  500) } catch { }
    Start-Sleep -Milliseconds 150
    try { [console]::beep(1200, 400) } catch { }
}

if ($TestAlarm) {
    Write-GuardLog "Test alarm requested."
    Invoke-RunAlarm -SoundPath $alarmPath
    Write-GuardLog "Test alarm completed."
    exit 0
}

function Get-LastRunDate {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }

    try {
        $content = Get-Content $Path -Raw
        if ([string]::IsNullOrWhiteSpace($content)) {
            return $null
        }

        $runs = $content | ConvertFrom-Json
        if ($null -eq $runs) {
            return $null
        }

        if ($runs -isnot [System.Array]) {
            $runs = @($runs)
        }

        if ($runs.Count -eq 0) {
            return $null
        }

        $last = $runs[-1]
        if ($null -eq $last.started_at) {
            return $null
        }

        return ([DateTimeOffset]::Parse($last.started_at)).ToLocalTime().Date
    }
    catch {
        return $null
    }
}

$today = (Get-Date).Date
$lastRunDate = Get-LastRunDate -Path $runHistoryPath

# Guard against duplicate same-day runs when both triggers (daily + startup) fire.
if ($lastRunDate -eq $today) {
    Write-GuardLog "Skipped: already ran today."
    exit 0
}

$cmd = "`"$pythonExe`" main.py --headless --limit 25"
Write-GuardLog "Starting: $cmd"
Invoke-RunAlarm -SoundPath $alarmPath

& $pythonExe main.py --headless --limit 25 *>> $logPath
$exitCode = $LASTEXITCODE

Write-GuardLog "Finished with exit code: $exitCode"

# Hibernation disabled by request.
Write-GuardLog "Hibernation skipped (disabled in guard script)."

exit $exitCode
