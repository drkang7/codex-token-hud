$ErrorActionPreference = 'Stop'
$taskExe = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'CodexTokenHud.exe'))
$taskName = 'CodexTokenHud-' + $env:USERNAME
$taskExisting = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($taskExisting -and $taskExisting.Actions.Execute -eq $taskExe) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
& (Join-Path $PSScriptRoot 'Stop.ps1')
$taskLinkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex Token 状态条.lnk'
if (Test-Path -LiteralPath $taskLinkPath) {
    $taskShell = New-Object -ComObject WScript.Shell
    $taskLink = $taskShell.CreateShortcut($taskLinkPath)
    if ($taskLink.TargetPath -eq $taskExe) { Remove-Item -LiteralPath $taskLinkPath }
    [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskLink) | Out-Null
    [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskShell) | Out-Null
}
Write-Output '状态条已停止，启动任务和桌面入口已移除。源码与布局配置已保留。'
