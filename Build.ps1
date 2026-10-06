[CmdletBinding()]
param([string]$OutputDirectory = $PSScriptRoot, [string]$PythonExecutable)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskOutput = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskVersion = (Get-Content -LiteralPath (Join-Path $taskRoot 'VERSION') -Raw).Trim()
if ($taskVersion -notmatch '^\d+\.\d+\.\d+(-[a-z0-9.]+)?$') { throw 'Invalid VERSION.' }
$taskAssemblyVersion = ($taskVersion -split '-')[0] + '.0'
$taskAssemblyInfo = Join-Path $taskOutput 'AssemblyInfo.g.cs'
@"
using System.Reflection;
[assembly: AssemblyTitle("Codex Token HUD")]
[assembly: AssemblyProduct("Codex Token HUD")]
[assembly: AssemblyDescription("Local token speed and cache measurements for Codex Desktop on Windows")]
[assembly: AssemblyVersion("$taskAssemblyVersion")]
[assembly: AssemblyFileVersion("$taskAssemblyVersion")]
[assembly: AssemblyInformationalVersion("$taskVersion")]
"@ | Set-Content -LiteralPath $taskAssemblyInfo -Encoding UTF8
$taskCsc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $taskCsc)) { throw '.NET Framework 4.x compiler is required on Windows x64.' }
$taskWpf = Join-Path (Split-Path -Parent $taskCsc) 'WPF'
$taskExe = Join-Path $taskOutput 'CodexTokenHud.exe'
$taskArgs = @('/nologo', '/target:winexe', '/platform:x64', '/optimize+',
    "/out:$taskExe", "/win32manifest:$taskRoot\app.manifest", '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
    '/r:System.Web.Extensions.dll', '/r:Microsoft.CSharp.dll',
    "/r:$taskWpf\UIAutomationClient.dll", "/r:$taskWpf\UIAutomationTypes.dll", "/r:$taskWpf\WindowsBase.dll",
    "$taskRoot\CodexTokenHud.cs", "$taskRoot\RuntimeConfiguration.cs", $taskAssemblyInfo)
& $taskCsc @taskArgs
if ($LASTEXITCODE -ne 0) { throw 'HUD compilation failed. Stop this copy of the HUD before rebuilding it.' }
if ($PythonExecutable) {
    $taskPython = (Get-Command $PythonExecutable -ErrorAction Stop).Source
    $taskPythonw = Join-Path (Split-Path -Parent $taskPython) 'pythonw.exe'
    if (-not (Test-Path -LiteralPath $taskPythonw)) { throw 'pythonw.exe is required next to python.exe.' }
    @{ pythonw = $taskPythonw } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOutput 'settings.json') -Encoding UTF8
}
Write-Output $taskExe
