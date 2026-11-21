$ErrorActionPreference = 'Continue'
$archivoPids = Join-Path $PSScriptRoot 'logs\pids.txt'

if (-not (Test-Path -LiteralPath $archivoPids)) {
    Write-Host 'No se encontró logs/pids.txt; no hay procesos registrados para detener.'
    exit 0
}

foreach ($linea in Get-Content -LiteralPath $archivoPids) {
    if ($linea -match '^([^|]+)\|(\d+)$') {
        $nombre = $Matches[1]
        $pidServicio = [int]$Matches[2]
        & taskkill.exe /PID $pidServicio /T /F *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Detenido: $nombre"
        }
        else {
            Write-Warning "No se pudo detener $nombre (PID $pidServicio); quizá ya no estaba activo."
        }
    }
}

Remove-Item -LiteralPath $archivoPids -Force
Write-Host 'Se eliminó logs/pids.txt.'
