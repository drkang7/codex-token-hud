$taskExe = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'CodexTokenHud.exe'))
Get-CimInstance Win32_Process -Filter "Name = 'CodexTokenHud.exe'" | ForEach-Object {
    if ($_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath) -eq $taskExe) {
        Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    }
}
