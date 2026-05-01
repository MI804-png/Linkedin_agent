$ErrorActionPreference = "Stop"

$botDir = "D:\cv_portofolio\linkedin_bot"
$pythonExe = "D:\cv_portofolio\.venv\Scripts\python.exe"
$runHistoryPath = Join-Path $botDir "run_history.json"
$logPath = Join-Path $botDir "scheduler_output.log"

Set-Location $botDir

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
    Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Skipped: already ran today."
    exit 0
}

$cmd = "`"$pythonExe`" main.py --headless --limit 25"
Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Starting: $cmd"

& $pythonExe main.py --headless --limit 25 *>> $logPath
$exitCode = $LASTEXITCODE

Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Finished with exit code: $exitCode"

# Hibernate after bot completes so the PC uses zero power but can wake again
# automatically tomorrow via the Task Scheduler WakeToRun timer.
Add-Content -Path $logPath -Value "[$(Get-Date -Format o)] Hibernating PC..."
shutdown /h

exit $exitCode
