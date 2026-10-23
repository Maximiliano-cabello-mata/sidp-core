# Muestra si los servicios de la PC 4 están trabajando. Solo lee: no cambia nada.
#   powershell -ExecutionPolicy Bypass -File cerebro\pc4\estado_servicios.ps1
# No imprime la clave del cerebro ni la dirección de la base.
$puertos = @{ 5432 = 'PostgreSQL'; 11434 = 'Ollama'; 8771 = 'Cerebro' }

foreach ($tarea in 'SIDP-Ollama', 'SIDP-Cerebro', 'SIDP-Vigia') {
    $t = Get-ScheduledTask -TaskName $tarea -ErrorAction SilentlyContinue
    if ($t) {
        $info = Get-ScheduledTaskInfo -TaskName $tarea
        Write-Host "Tarea $tarea : $($t.State) (último arranque $($info.LastRunTime), resultado $('0x{0:X}' -f $info.LastTaskResult), cuenta $($t.Principal.UserId))"
    } else {
        Write-Host "Tarea $tarea : NO EXISTE (corre instalar_servicios.ps1)"
    }
}
Write-Host "La PC se encendió: $((Get-CimInstance Win32_OperatingSystem).LastBootUpTime)"
Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "Servicio $($_.Name): $($_.Status), arranque $($_.StartType)" }

foreach ($puerto in $puertos.Keys | Sort-Object) {
    $escucha = Get-NetTCPConnection -State Listen -LocalPort $puerto -ErrorAction SilentlyContinue | Select-Object -First 1
    $donde = if ($escucha) { "escuchando en $($escucha.LocalAddress)" } else { 'NO ESCUCHA' }
    Write-Host "$($puertos[$puerto]) (puerto $puerto): $donde"
}

try {
    $modelos = (Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10).models | ForEach-Object { $_.name }
    Write-Host "Modelos de Ollama: $($modelos -join ', ')"
} catch { Write-Host "Ollama no respondió: $($_.Exception.Message)" }

$archivoAjustes = 'C:\SIDP-datos\servicios\ajustes.ps1'
if (Test-Path $archivoAjustes) {
    $lineas = Get-Content $archivoAjustes | Where-Object { $_ -match '^\s*\$env:' } | ForEach-Object { $_.Trim() -replace '^\$env:', '' }
    Write-Host "Ajustes ($archivoAjustes): $($lineas -join '; ')"
} else {
    Write-Host 'Ajustes: no hay ajustes.ps1 (se crea al correr instalar_servicios.ps1)'
}

$version = 'C:\SIDP-datos\actualizaciones\actual.json'
if (Test-Path $version) {
    $v = Get-Content $version -Raw | ConvertFrom-Json
    Write-Host "Actualización que ofrece al servidor: SIDP $($v.version) ($($v.origen), $($v.guardada))"
} else {
    Write-Host 'Actualización que ofrece al servidor: ninguna todavía (se baja sola de GitHub al fusionar a main)'
}

$archivoClave = Join-Path $env:USERPROFILE '.sidp\clave_cerebro.txt'
try {
    $clave = (Get-Content $archivoClave -Raw).Trim()
    $salud = Invoke-RestMethod -Uri 'http://127.0.0.1:8771/salud' -Headers @{ 'X-SIDP-Clave' = $clave } -TimeoutSec 20
    $base = if ($salud.base.motor) { "$($salud.base.motor), $($salud.base.alumnos) alumnos" } else { 'sin base' }
    Write-Host "Cerebro: responde. Base: $base"
} catch { Write-Host "Cerebro no respondió: $($_.Exception.Message)" }

foreach ($nombre in 'vigia', 'ollama', 'cerebro') {
    foreach ($fin in '.ciclo.log', '.log', '.error.log') {
        $registro = "C:\SIDP-datos\registros\$nombre$fin"
        if (Test-Path $registro) {
            Write-Host "--- Últimas líneas de $registro"
            Get-Content $registro -Tail 6 | Where-Object { $_ -notmatch 'Clave' } | ForEach-Object { Write-Host "  $_" }
        }
    }
}
