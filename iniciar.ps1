$env:PYTHONUTF8 = '1'
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$archivoEnv = Join-Path $raiz '.env'
$directorioLogs = Join-Path $raiz 'logs'
$archivoPids = Join-Path $directorioLogs 'pids.txt'

if (-not (Test-Path -LiteralPath $archivoEnv)) {
    Write-Error 'No existe .env. Ejecuta primero .\instalar.ps1 y completa su configuración.'
    exit 1
}
if (Test-Path -LiteralPath $archivoPids) {
    Write-Error 'Ya existe logs/pids.txt. Ejecuta .\detener.ps1 antes de iniciar otra vez.'
    exit 1
}

$pythonGeneral = Join-Path $raiz '.venv\Scripts\python.exe'
$pythonCrew = Join-Path $raiz '.venv-crew\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonGeneral) -or -not (Test-Path -LiteralPath $pythonCrew)) {
    Write-Error 'Faltan entornos virtuales. Ejecuta .\instalar.ps1.'
    exit 1
}

function Leer-VariablesEnv {
    param([string]$Ruta)
    $mapa = @{}
    foreach ($linea in Get-Content -LiteralPath $Ruta -Encoding UTF8) {
        $limpia = $linea.Trim()
        if (-not $limpia -or $limpia.StartsWith('#')) { continue }
        $idx = $limpia.IndexOf('=')
        if ($idx -gt 0) {
            $k = $limpia.Substring(0, $idx).Trim()
            $v = $limpia.Substring($idx + 1).Trim()
            $mapa[$k] = $v
        }
    }
    return $mapa
}

function Obtener-PuertoUrl {
    param([string]$Url, [int]$PorDefecto)
    if ($Url -and $Url -match ':(\d+)(/|$)') {
        return [int]$Matches[1]
    }
    return $PorDefecto
}

$varsEnv = Leer-VariablesEnv -Ruta $archivoEnv
$puertoApi = if ($env:PORT) { [int]$env:PORT } elseif ($varsEnv['PORT']) { [int]$varsEnv['PORT'] } elseif ($varsEnv['API_PUERTO']) { [int]$varsEnv['API_PUERTO'] } else { 8010 }
$hostApi = if ($varsEnv['API_HOST']) { $varsEnv['API_HOST'] } else { '127.0.0.1' }
$hostChequeoApi = if ($hostApi -eq '0.0.0.0') { '127.0.0.1' } else { $hostApi }

New-Item -ItemType Directory -Path $directorioLogs -Force | Out-Null
Set-Content -LiteralPath $archivoPids -Value '' -Encoding ASCII
$fallidos = New-Object 'System.Collections.Generic.List[string]'

function Escapar-CadenaPowerShell {
    param([string]$Texto)
    return $Texto.Replace("'", "''")
}

function Iniciar-Servicio {
    param(
        [string]$Nombre,
        [string]$Python,
        [string]$Modulo,
        [string]$HostEscucha,
        [string]$HostSalud,
        [int]$Puerto,
        [string]$RutaSalud
    )

    $archivoLog = Join-Path $directorioLogs ($Nombre + '.log')
    $escuchas = @(Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue)
    if ($escuchas.Count -gt 0) {
        Write-Warning "Puerto $Puerto ocupado: cierra ese proceso o ejecuta .\detener.ps1"
        [void]$fallidos.Add($Nombre)
        return
    }

    $pythonSeguro = Escapar-CadenaPowerShell $Python
    $logSeguro = Escapar-CadenaPowerShell $archivoLog
    $comando = "& '$pythonSeguro' -m uvicorn $Modulo --host $HostEscucha --port $Puerto *>> '$logSeguro'"
    $codificado = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($comando))

    try {
        $proceso = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList @('-NoProfile', '-EncodedCommand', $codificado) `
            -WorkingDirectory $raiz `
            -WindowStyle Hidden `
            -PassThru
    }
    catch {
        Write-Warning "No se pudo iniciar $Nombre."
        [void]$fallidos.Add($Nombre)
        return
    }

    Add-Content -LiteralPath $archivoPids -Value ($Nombre + '|' + $proceso.Id) -Encoding ASCII
    Write-Host "Esperando $Nombre en el puerto $Puerto..."
    $url = "http://${HostSalud}:$Puerto$RutaSalud"
    $inicio = Get-Date
    $respondio = $false
    while (((Get-Date) - $inicio).TotalSeconds -lt 60) {
        $restante = 60 - [int][Math]::Floor(((Get-Date) - $inicio).TotalSeconds)
        if ($restante -le 0) {
            break
        }
        $timeoutPeticion = [Math]::Min(3, $restante)
        try {
            $respuesta = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutPeticion
            if ($respuesta.StatusCode -ge 200 -and $respuesta.StatusCode -lt 300) {
                $respondio = $true
                break
            }
        }
        catch {
            $restante = 60 - [int][Math]::Floor(((Get-Date) - $inicio).TotalSeconds)
            if ($restante -gt 0) {
                Start-Sleep -Seconds ([Math]::Min(2, $restante))
            }
        }
    }

    if ($respondio) {
        Write-Host "$Nombre responde correctamente."
    }
    else {
        Write-Warning "$Nombre no respondió a $RutaSalud en 60 segundos."
        [void]$fallidos.Add($Nombre)
    }
}

$servicios = @(
    @{ Nombre = 'viajes'; Python = $pythonGeneral; Modulo = 'src.agente_viajes.server:app'; Puerto = (Obtener-PuertoUrl $varsEnv['URL_VIAJES'] 8000); Ruta = '/.well-known/agent-card.json' },
    @{ Nombre = 'anggie'; Python = $pythonGeneral; Modulo = 'src.agente_anggie.server:app'; Puerto = (Obtener-PuertoUrl $varsEnv['URL_ANGGIE'] 8003); Ruta = '/.well-known/agent-card.json' },
    @{ Nombre = 'enrique'; Python = $pythonGeneral; Modulo = 'src.agente_enrique.server:app'; Puerto = (Obtener-PuertoUrl $varsEnv['URL_ENRIQUE'] 8004); Ruta = '/.well-known/agent-card.json' },
    @{ Nombre = 'algomarket'; Python = $pythonGeneral; Modulo = 'src.agente_algomarket.server:app'; Puerto = (Obtener-PuertoUrl $varsEnv['URL_ALGOMARKET'] 8005); Ruta = '/.well-known/agent-card.json' },
    @{ Nombre = 'christian'; Python = $pythonGeneral; Modulo = 'src.agente_christian.server:app'; Puerto = (Obtener-PuertoUrl $varsEnv['URL_CHRISTIAN'] 8006); Ruta = '/.well-known/agent-card.json' },
    @{ Nombre = 'restaurantes'; Python = $pythonCrew; Modulo = 'src.agente_restaurantes.server:app'; Puerto = (Obtener-PuertoUrl $varsEnv['URL_RESTAURANTES'] 8001); Ruta = '/.well-known/agent-card.json' }
)

foreach ($servicio in $servicios) {
    Iniciar-Servicio -Nombre $servicio.Nombre -Python $servicio.Python `
        -Modulo $servicio.Modulo -HostEscucha '127.0.0.1' -HostSalud '127.0.0.1' `
        -Puerto $servicio.Puerto -RutaSalud $servicio.Ruta
}

Iniciar-Servicio -Nombre 'api' -Python $pythonGeneral -Modulo 'api.app:app' `
    -HostEscucha $hostApi -HostSalud $hostChequeoApi -Puerto $puertoApi -RutaSalud '/health'

if ($fallidos.Count -gt 0) {
    Write-Warning ('Servicios que no respondieron: ' + ($fallidos -join ', '))
}

Write-Host "Swagger: http://localhost:$puertoApi/docs"
Write-Host 'para detener: .\detener.ps1'
