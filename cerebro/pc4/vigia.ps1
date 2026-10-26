# El vigía de la PC 4: cada 2 minutos revisa que Ollama, PostgreSQL y el cerebro contesten y, si no, los levanta.
# Lo registra instalar_servicios.ps1 como la tarea "SIDP-Vigia" (cuenta del sistema, al encender y cada 2 minutos).
# Anota en C:\SIDP-datos\registros\vigia.log cuándo se encendió la PC, cuándo quedó listo el cerebro y qué levantó.
# No imprime la clave del cerebro: la lee del archivo, que solo está en esta PC.
param([string]$ArchivoClave = (Join-Path $env:USERPROFILE '.sidp\clave_cerebro.txt'))

$registros = 'C:\SIDP-datos\registros'
$estadoArchivo = 'C:\SIDP-datos\servicios\vigia.estado.json'
$registro = Join-Path $registros 'vigia.log'
New-Item -ItemType Directory -Force $registros | Out-Null

function Anota($texto) { Add-Content $registro ((Get-Date -Format s) + ' ' + $texto) }

$estado = @{ encendido = ''; listo = $false; fallas_cerebro = 0; fallas_ollama = 0 }
if (Test-Path $estadoArchivo) {
    try {
        $leido = Get-Content $estadoArchivo -Raw | ConvertFrom-Json
        foreach ($k in 'encendido', 'listo', 'fallas_cerebro', 'fallas_ollama') { if ($null -ne $leido.$k) { $estado[$k] = $leido.$k } }
    } catch { }
}

# 1. ¿Se encendió la PC desde la última vuelta? Se anota una vez por encendido.
$encendido = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('s')
if ($estado.encendido -ne $encendido) {
    Anota "la PC se encendió a las $encendido"
    $estado = @{ encendido = $encendido; listo = $false; fallas_cerebro = 0; fallas_ollama = 0 }
}

# 2. PostgreSQL es un servicio de Windows: si está detenido, se arranca.
Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Where-Object { $_.Status -ne 'Running' } | ForEach-Object {
    Anota "PostgreSQL ($($_.Name)) estaba $($_.Status): lo arranco"
    try { Start-Service $_.Name } catch { Anota "no pude arrancar PostgreSQL: $($_.Exception.Message)" }
}

function Lanzador-Vivo($nombre) {
    [bool](Get-CimInstance Win32_Process -Filter "Name like 'powershell%'" |
        Where-Object { $_.CommandLine -like "*SIDP-datos\servicios\$nombre.ps1*" })
}

# 3. Ollama.
try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 20 | Out-Null
    $estado.fallas_ollama = 0
} catch {
    $estado.fallas_ollama = [int]$estado.fallas_ollama + 1
    if (-not (Lanzador-Vivo 'ollama')) {
        Anota 'Ollama no estaba corriendo: arranco la tarea SIDP-Ollama'
        Start-ScheduledTask -TaskName 'SIDP-Ollama' -ErrorAction SilentlyContinue
        $estado.fallas_ollama = 0
    } elseif ($estado.fallas_ollama -ge 3) {
        Anota 'Ollama no contesta desde hace 3 vueltas: lo cierro y su lanzador lo vuelve a abrir'
        cmd.exe /c 'taskkill /F /T /IM ollama.exe >nul 2>&1'
        $estado.fallas_ollama = 0
    }
}

# 4. El cerebro, con su base de datos.
$sano = $false
$motivo = ''
try {
    $clave = (Get-Content $ArchivoClave -Raw).Trim()
    $salud = Invoke-RestMethod -Uri 'http://127.0.0.1:8771/salud' -Headers @{ 'X-SIDP-Clave' = $clave } -TimeoutSec 30
    if ($salud.base.motor) { $sano = $true } else { $motivo = 'contesta, pero sin base de datos' }
} catch { $motivo = "no contesta ($($_.Exception.Message))" }

if ($sano) {
    if (-not $estado.listo) {
        $minutos = [math]::Round(((Get-Date) - [datetime]$estado.encendido).TotalMinutes, 1)
        Anota "el cerebro quedó listo con su base, $minutos minutos después de encender"
        $estado.listo = $true
    }
    $estado.fallas_cerebro = 0
} else {
    $estado.fallas_cerebro = [int]$estado.fallas_cerebro + 1
    if (-not (Lanzador-Vivo 'cerebro')) {
        Anota "el cerebro $motivo y su lanzador no corre: arranco la tarea SIDP-Cerebro"
        Start-ScheduledTask -TaskName 'SIDP-Cerebro' -ErrorAction SilentlyContinue
        $estado.fallas_cerebro = 0
    } elseif ($estado.fallas_cerebro -ge 3) {
        # El cerebro tarda en arrancar (espera a PostgreSQL), por eso se le dan 3 vueltas (unos 6 minutos).
        Anota "el cerebro $motivo desde hace 3 vueltas: lo cierro y su lanzador lo vuelve a abrir"
        Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like '*validacion.cerebro_red*' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        $estado.fallas_cerebro = 0
    }
}

$estado | ConvertTo-Json | Set-Content -Encoding UTF8 $estadoArchivo
