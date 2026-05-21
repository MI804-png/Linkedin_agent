$logPath = 'D:\cv_portofolio\android2_2026_6semester\enable-whpx.log'

Start-Transcript -Path $logPath -Force

try {
	Write-Host 'Stopping legacy HAXM service...'
	& sc.exe stop intelhaxm

	Write-Host 'Deleting legacy HAXM service...'
	& sc.exe delete intelhaxm

	Write-Host 'Enabling Windows Hypervisor Platform...'
	& dism.exe /online /enable-feature /featurename:HypervisorPlatform /all /norestart

	Write-Host 'Enabling Virtual Machine Platform...'
	& dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
}
finally {
	Stop-Transcript
}
