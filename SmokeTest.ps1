[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PackageZip)
$ErrorActionPreference = 'Stop'
$taskSmoke = Join-Path $PSScriptRoot 'build\portable smoke'
$taskResolved = [IO.Path]::GetFullPath($taskSmoke)
$taskBuildRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'build')) + [IO.Path]::DirectorySeparatorChar
if (-not $taskResolved.StartsWith($taskBuildRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe smoke-test path.' }
if (Test-Path -LiteralPath $taskSmoke) { Remove-Item -LiteralPath $taskSmoke -Recurse -Force }
Expand-Archive -LiteralPath $PackageZip -DestinationPath $taskSmoke
$taskPackage = @(Get-ChildItem -LiteralPath $taskSmoke -Directory)
if ($taskPackage.Count -ne 1) { throw 'Expected one package directory.' }
$taskPython = Join-Path $taskPackage[0].FullName 'python\python.exe'
& $taskPython -I -X utf8 (Join-Path $PSScriptRoot 'tests\portable_smoke.py') --package $taskPackage[0].FullName --zip $PackageZip
if ($LASTEXITCODE -ne 0) { throw 'Portable package smoke test failed.' }
