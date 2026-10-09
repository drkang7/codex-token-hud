[CmdletBinding()]
param([switch]$SkipTests, [switch]$SkipSmokeTest, [string]$PythonExecutable = 'python.exe',
    [ValidateSet('x64', 'arm64', 'x86')][string]$Architecture = 'x64')
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
if (-not $SkipTests) { & (Join-Path $taskRoot 'Test.ps1') -PythonExecutable $PythonExecutable }
$taskVersion = (Get-Content -LiteralPath (Join-Path $taskRoot 'VERSION') -Raw).Trim()
$taskName = "CodexTokenHud-$taskVersion-win-$Architecture"
$taskDist = Join-Path $taskRoot 'dist'
$taskStage = Join-Path $taskDist $taskName
# Delete only this exact, validated package staging directory, never runtime or source data.
$taskResolvedStage = [IO.Path]::GetFullPath($taskStage)
$taskResolvedDist = [IO.Path]::GetFullPath($taskDist) + [IO.Path]::DirectorySeparatorChar
if (-not $taskResolvedStage.StartsWith($taskResolvedDist, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe staging path.' }
if (Test-Path -LiteralPath $taskStage) { Remove-Item -LiteralPath $taskStage -Recurse -Force }
New-Item -ItemType Directory -Path $taskStage -Force | Out-Null
& (Join-Path $taskRoot 'Build.ps1') -OutputDirectory $taskStage
Remove-Item -LiteralPath (Join-Path $taskStage 'AssemblyInfo.g.cs')
# Explicit allowlist: no account data, debug extracts, local settings, or conversation logs.
$taskFiles = @('metrics.py', 'history.py', 'dashboard.py', 'stats.py', 'StartDashboard.ps1', 'start-dashboard.sh', 'VERSION', 'README.md', 'README.zh-CN.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
    'CHANGELOG.md', 'PRIVACY.md', 'SECURITY.md', 'CONTRIBUTING.md', 'settings.example.json',
    'Install.ps1', 'Uninstall.ps1', 'Start.ps1', 'Stop.ps1')
foreach ($taskFile in $taskFiles) { Copy-Item -LiteralPath (Join-Path $taskRoot $taskFile) -Destination $taskStage }
Copy-Item -LiteralPath (Join-Path $taskRoot 'docs') -Destination $taskStage -Recurse
Copy-Item -LiteralPath (Join-Path $taskRoot 'web') -Destination $taskStage -Recurse
$taskRuntimeFile = if ($Architecture -eq 'x64') { 'python-runtime.json' } else { "python-runtime-$Architecture.json" }
$taskRuntimeInfo = Get-Content -LiteralPath (Join-Path $taskRoot $taskRuntimeFile) -Raw | ConvertFrom-Json
$taskCache = Join-Path $taskRoot 'build\cache'
New-Item -ItemType Directory -Path $taskCache -Force | Out-Null
$taskRuntimeZip = Join-Path $taskCache $taskRuntimeInfo.file
if (-not (Test-Path -LiteralPath $taskRuntimeZip)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri $taskRuntimeInfo.url -OutFile $taskRuntimeZip
}
if ((Get-FileHash -LiteralPath $taskRuntimeZip -Algorithm SHA256).Hash -ne $taskRuntimeInfo.sha256) {
    throw 'Python runtime SHA256 mismatch. The cached download was not extracted.'
}
Expand-Archive -LiteralPath $taskRuntimeZip -DestinationPath (Join-Path $taskStage 'python')
$taskZip = Join-Path $taskDist ($taskName + '.zip')
Compress-Archive -LiteralPath $taskStage -DestinationPath $taskZip -Force
$taskHash = (Get-FileHash -LiteralPath $taskZip -Algorithm SHA256).Hash.ToLowerInvariant()
"$taskHash  $taskName.zip" | Set-Content -LiteralPath ($taskZip + '.sha256') -Encoding ASCII
if (-not $SkipSmokeTest) { & (Join-Path $taskRoot 'SmokeTest.ps1') -PackageZip $taskZip }
Write-Output "Ready: $taskZip"
