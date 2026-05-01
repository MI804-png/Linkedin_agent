$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$python = "d:\cv_portofolio\.venv\Scripts\python.exe"

& $python -m pip install --upgrade pyinstaller

# Build a one-file Windows executable with a GUI entry point.
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name LinkedInAutoApply `
  --collect-all playwright `
  --add-data "linkedin_bot\applied_jobs.json;." `
  --add-data "linkedin_bot\run_history.json;." `
  --add-data "linkedin_bot\state.json;." `
  --add-data "Mikhael_CV.pdf;." `
  linkedin_bot\exe_runner.py

Write-Host "Build finished. EXE path: $repoRoot\dist\LinkedInAutoApply.exe"
