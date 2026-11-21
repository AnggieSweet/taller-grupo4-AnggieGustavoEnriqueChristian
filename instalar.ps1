$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot

function Instalar-Entorno {
    param(
        [string]$RutaEntorno,
        [string]$ArchivoRequisitos
    )

    $python = Join-Path $RutaEntorno 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        Write-Host "Creando $RutaEntorno..."
        & py -3.13 -m venv $RutaEntorno
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudo crear $RutaEntorno. Comprueba que Python 3.13 esté instalado."
        }
    }

    Write-Host "Instalando dependencias de $ArchivoRequisitos..."
    & $python -m pip install -r (Join-Path $raiz $ArchivoRequisitos)
    if ($LASTEXITCODE -ne 0) {
        throw "Falló la instalación desde $ArchivoRequisitos."
    }
}

try {
    Instalar-Entorno -RutaEntorno (Join-Path $raiz '.venv') -ArchivoRequisitos 'requirements.txt'
    Instalar-Entorno -RutaEntorno (Join-Path $raiz '.venv-crew') -ArchivoRequisitos 'requirements-crew.txt'

    $envEjemplo = Join-Path $raiz '.env.example'
    $envLocal = Join-Path $raiz '.env'
    if (-not (Test-Path -LiteralPath $envLocal)) {
        Copy-Item -LiteralPath $envEjemplo -Destination $envLocal
        Write-Host 'Se creó .env desde .env.example.'
    }

    $brunoEjemplo = Join-Path $raiz 'bruno\.env.example'
    $brunoEnv = Join-Path $raiz 'bruno\.env'
    if ((Test-Path -LiteralPath $brunoEjemplo) -and -not (Test-Path -LiteralPath $brunoEnv)) {
        Copy-Item -LiteralPath $brunoEjemplo -Destination $brunoEnv
        Write-Host 'Se creó bruno/.env desde bruno/.env.example.'
    }

    Write-Host ''
    Write-Host 'Completa en .env las variables obligatorias: GOOGLE_API_KEY y API_KEY.'
    Write-Host 'Opcionales para Telegram: TELEGRAM_TOKEN, TELEGRAM_SECRET y TELEGRAM_PERMITIDOS.'
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
