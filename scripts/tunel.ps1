param(
    [int]$Puerto = 8000
)

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Host "cloudflared no está instalado. Instálalo con: winget install Cloudflare.cloudflared"
    exit 1
}

& $cloudflared.Source tunnel --url "http://127.0.0.1:$Puerto" 2>&1 | ForEach-Object {
    $linea = "$_"
    Write-Host $linea
    if ($linea -match '(https://[a-zA-Z0-9-]+\.trycloudflare\.com)') {
        $direccion = $Matches[1]
        Write-Host ''
        Write-Host '==============================================' -ForegroundColor Cyan
        Write-Host ('DIRECCIÓN PÚBLICA: ' + $direccion) -ForegroundColor Yellow
        Write-Host '==============================================' -ForegroundColor Cyan
        Write-Host 'Pega esta dirección en URL_PUBLICA de tu .env y reinicia tu agente; pásasela a tu compañero para que la ponga en su URLS_AGENTES.'
        Write-Host ''
    }
}
