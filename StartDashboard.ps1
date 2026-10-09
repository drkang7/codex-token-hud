[CmdletBinding()]
param([string]$PythonExecutable, [string]$CodexHome, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$taskPython = if ($PythonExecutable) { $PythonExecutable } elseif (Test-Path -LiteralPath "$PSScriptRoot\python\python.exe") {
    "$PSScriptRoot\python\python.exe"
} else { 'python.exe' }
$taskArgs = @('-I', '-X', 'utf8', (Join-Path $PSScriptRoot 'dashboard.py'))
if ($CodexHome) { $taskArgs += @('--codex-home', $CodexHome) }
if ($NoBrowser) { $taskArgs += '--no-browser' }
& $taskPython @taskArgs
