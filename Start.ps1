$ErrorActionPreference = 'Stop'
$taskExe = Join-Path $PSScriptRoot 'CodexTokenHud.exe'
if (-not (Test-Path -LiteralPath $taskExe)) { & (Join-Path $PSScriptRoot 'Build.ps1') }
Start-Process -FilePath $taskExe -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
