param(
    [Parameter(Mandatory = $true)]
    [string]$VmHost,

    [Parameter(Mandatory = $true)]
    [string]$SshKeyPath,

    [string]$VmUser = "ubuntu",
    [int]$ScheduleHour = 8,
    [int]$ScheduleMinute = 30,
    [string]$TimeZone = "Europe/Budapest"
)

$ErrorActionPreference = "Stop"

$RepoRoot = "D:\cv_portofolio"
$BotDir = Join-Path $RepoRoot "linkedin_bot"
$CvPath = Join-Path $RepoRoot "Mikhael_CV.pdf"
$RemoteBase = "~/cv_portofolio"
$RemoteTarget = "$VmUser@$VmHost"

if (-not (Test-Path $SshKeyPath)) {
    throw "SSH key not found: $SshKeyPath"
}
if (-not (Test-Path $BotDir)) {
    throw "Bot directory not found: $BotDir"
}
if (-not (Test-Path $CvPath)) {
    throw "CV not found: $CvPath"
}

Write-Host "[1/4] Creating remote directory..."
ssh -o StrictHostKeyChecking=accept-new -i $SshKeyPath $RemoteTarget "mkdir -p $RemoteBase"

Write-Host "[2/4] Uploading linkedin_bot folder..."
scp -o StrictHostKeyChecking=accept-new -i $SshKeyPath -r $BotDir "$RemoteTarget`:$RemoteBase/"

Write-Host "[3/4] Uploading CV PDF..."
scp -o StrictHostKeyChecking=accept-new -i $SshKeyPath $CvPath "$RemoteTarget`:$RemoteBase/"

Write-Host "[4/4] Running Oracle bootstrap script..."
$remoteCmd = "bash $RemoteBase/linkedin_bot/oracle/oracle_bootstrap.sh $ScheduleHour $ScheduleMinute '$TimeZone'"
ssh -o StrictHostKeyChecking=accept-new -i $SshKeyPath $RemoteTarget $remoteCmd

Write-Host "Deployment complete."
Write-Host "To run immediately on Oracle VM:"
Write-Host "ssh -i $SshKeyPath $RemoteTarget 'bash ~/cv_portofolio/linkedin_bot/oracle/oracle_guard_run.sh'"
