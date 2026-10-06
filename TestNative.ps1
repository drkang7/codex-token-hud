# Optional, read-only hit-test verification of an already-running HUD window.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskOutput = Join-Path $PSScriptRoot 'build\tests'
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskExe = Join-Path $taskOutput 'NativeHudCheck.exe'
$taskCsc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $taskCsc /nologo /target:exe /platform:x64 "/out:$taskExe" (Join-Path $PSScriptRoot 'tests\NativeHudCheck.cs')
if ($LASTEXITCODE -ne 0) { throw 'Native check compilation failed.' }
& $taskExe
if ($LASTEXITCODE -ne 0) { throw 'Native HUD checks failed. Start a HUD beside a local Codex window first.' }
