[CmdletBinding()]
param([string]$PythonExecutable = 'python.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = (Get-Command $PythonExecutable -ErrorAction Stop).Source
Push-Location $taskRoot
try {
    & $taskPython -X utf8 -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    $taskBuild = Join-Path $taskRoot 'build\tests'
    New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
    $taskCsc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    $taskWpf = Join-Path (Split-Path -Parent $taskCsc) 'WPF'
    $taskTestExe = Join-Path $taskBuild 'PresentationTests.exe'
    $taskArgs = @('/nologo', '/target:exe', '/platform:x64', '/main:PresentationTests',
        "/out:$taskTestExe", '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
        '/r:System.Web.Extensions.dll', '/r:Microsoft.CSharp.dll',
        "/r:$taskWpf\UIAutomationClient.dll", "/r:$taskWpf\UIAutomationTypes.dll", "/r:$taskWpf\WindowsBase.dll",
        "$taskRoot\CodexTokenHud.cs", "$taskRoot\RuntimeConfiguration.cs", "$taskRoot\tests\PresentationTests.cs")
    & $taskCsc @taskArgs
    if ($LASTEXITCODE -ne 0) { throw 'Presentation test compilation failed.' }
    & $taskTestExe
    if ($LASTEXITCODE -ne 0) { throw 'Presentation tests failed.' }
    Write-Output 'All tests passed.'
} finally { Pop-Location }
