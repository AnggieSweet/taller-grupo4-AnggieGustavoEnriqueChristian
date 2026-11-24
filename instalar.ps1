$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot

function Obtener-ComandoPython {
    foreach ($candidato in @(
        @{ Exe = 'py'; Args = @('-3.13') },
        @{ Exe = 'py'; Args = @('-3.12') },
        @{ Exe = 'python'; Args = @() },
        @{ Exe = 'python3'; Args = @() }
    )) {
        $cmd = Get-Command $candidato.Exe -ErrorAction SilentlyContinue
        if ($cmd) {
            try {
                $ver = & $candidato.Exe @($candidato.Args + @('-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')) 2>$null
                if ($LASTEXITCODE -eq 0 -and $ver -match '^3\.(12|13|14)$') {
                    return $candidato
                }
            }
            catch {}
        }
    }
    throw 'No se encontró Python 3.12 o 3.13 en el sistema. Instala Python >= 3.12 y vuelve a intentarlo.'
}

function Instalar-Entorno {
    param(
        [hashtable]$PythonBase,
        [string]$RutaEntorno,
        [string]$ArchivoRequisitos
    )

    $python = Join-Path $RutaEntorno 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        Write-Host "Creando $RutaEntorno..."
        & $PythonBase.Exe @($PythonBase.Args + @('-m', 'venv', $RutaEntorno))
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudo crear $RutaEntorno."
        }
    }

    Write-Host "Instalando dependencias de $ArchivoRequisitos..."
    & $python -m pip install -r (Join-Path $raiz $ArchivoRequisitos)
    if ($LASTEXITCODE -ne 0) {
        throw "Falló la instalación desde $ArchivoRequisitos."
    }
}

try {
    $pyBase = Obtener-ComandoPython
    Instalar-Entorno -PythonBase $pyBase -RutaEntorno (Join-Path $raiz '.venv') -ArchivoRequisitos 'requirements.txt'
    Instalar-Entorno -PythonBase $pyBase -RutaEntorno (Join-Path $raiz '.venv-crew') -ArchivoRequisitos 'requirements-crew.txt'

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
    Write-Host 'Completa en .env las variables obligatorias: GOOGLE_API_KEY (o USAR_OAUTH=true), API_KEY y AGENT_API_KEY (si expones los agentes).'
    Write-Host 'Opcionales para Telegram: TELEGRAM_TOKEN, TELEGRAM_SECRET y TELEGRAM_PERMITIDOS.'
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
