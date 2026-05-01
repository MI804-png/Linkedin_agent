powercfg /hibernate on
$regPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Explorer"
if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
Set-ItemProperty -Path $regPath -Name "ShowHibernateOption" -Value 1 -Type DWord -Force
Write-Host "Hibernate enabled and added to Start menu."
