$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskExe = Join-Path $taskRoot 'CodexTokenHud.exe'
if (-not (Test-Path -LiteralPath $taskExe)) { & (Join-Path $taskRoot 'Build.ps1') }
$taskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskName = 'CodexTokenHud-' + $env:USERNAME
$taskExisting = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($taskExisting -and $taskExisting.Actions.Execute -ne $taskExe) {
    throw "同名启动任务 $taskName 指向其他程序，未覆盖。"
}
$taskAction = New-ScheduledTaskAction -Execute $taskExe -WorkingDirectory $taskRoot
$taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
$taskTrigger.Delay = 'PT10S'
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Highest
$taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings -Description 'Codex 当前对话 token 速率和缓存命中率状态条' -Force | Out-Null
$taskShell = New-Object -ComObject WScript.Shell
$taskLink = $taskShell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex Token 状态条.lnk'))
$taskLink.TargetPath = $taskExe
$taskLink.WorkingDirectory = $taskRoot
$taskLink.Description = '显示当前 Codex 对话的 token 速率与缓存命中率，支持拖动和调整大小'
$taskLink.WindowStyle = 7
$taskLink.Save()
[Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskLink) | Out-Null
[Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskShell) | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output '已创建桌面入口并启用登录后自动启动。可在状态条右键菜单关闭自动启动。'
