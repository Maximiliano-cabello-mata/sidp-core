# Deja la PC 4 trabajando sola desde que se enciende, sin monitor y sin iniciar sesión.
#
# Servicios de la PC 4:
#   - PostgreSQL (la base de datos): ya es un servicio de Windows; aquí solo se asegura que arranque solo.
#   - Ollama (los modelos de IA): tarea programada "SIDP-Ollama", solo en 127.0.0.1.
#   - El cerebro (puerto 8771): tarea programada "SIDP-Cerebro". Espera a PostgreSQL y, si no la encuentra o se
#     cae, vuelve a arrancar a los 10 segundos: nunca se queda trabajando sin base.
#   - El vigía: tarea "SIDP-Vigia" (cuenta del sistema) que al encender y cada 2 minutos revisa que los tres
#     contesten y levanta al que no (cerebro/pc4/vigia.ps1). Anota en C:\SIDP-datos\registros\vigia.log.
# Ollama y el cerebro corren con la cuenta de este usuario aunque nadie haya iniciado sesión (S4U: no guarda la
# contraseña). Si Windows no deja arrancar así (vigia.log lo dice), -ComoSistema los corre con la cuenta del sistema.
# Los registros quedan en C:\SIDP-datos\registros; la clave del cerebro no se escribe en ellos.
#
# Se corre en PowerShell como administrador, desde la carpeta del repositorio:
#   powershell -ExecutionPolicy Bypass -File cerebro\pc4\instalar_servicios.ps1
#   powershell -ExecutionPolicy Bypass -File cerebro\pc4\instalar_servicios.ps1 -ComoSistema
# Para quitarlo todo y volver a como estaba:
#   powershell -ExecutionPolicy Bypass -File cerebro\pc4\instalar_servicios.ps1 -Quitar
# En el servidor que también es el cerebro (Tarea 019), con -MismaPC: el cerebro escucha solo en esta PC, Ollama y el
# cerebro trabajan con prioridad baja para que el panel no se alente, y un solo modelo a la vez ocupa la memoria.
#   powershell -ExecutionPolicy Bypass -File cerebro\pc4\instalar_servicios.ps1 -MismaPC
param([switch]$Quitar, [switch]$ComoSistema, [switch]$MismaPC)
$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Abre PowerShell como administrador (clic derecho > Ejecutar como administrador) y vuelve a correrlo.'
    exit 1
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$datos = 'C:\SIDP-datos'
$servicios = Join-Path $datos 'servicios'
$registros = Join-Path $datos 'registros'
$inicio = [Environment]::GetFolderPath('Startup')
$guardados = Join-Path $servicios 'accesos_de_inicio_guardados'
$tareas = 'SIDP-Ollama', 'SIDP-Cerebro'
$vigia = 'SIDP-Vigia'

if ($Quitar) {
    foreach ($tarea in @($tareas) + $vigia) {
        if (Get-ScheduledTask -TaskName $tarea -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $tarea -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $tarea -Confirm:$false
            Write-Host "Quitada la tarea $tarea"
        }
    }
    if (Test-Path $guardados) {
        Get-ChildItem $guardados -Filter *.lnk | Move-Item -Destination $inicio -Force
        Write-Host 'Regresé el acceso de Ollama al inicio de sesión.'
    }
    exit 0
}

# 1. Dónde está cada cosa (se buscan una vez y se escriben fijas en los lanzadores).
$python = (Get-Command python -ErrorAction Stop).Source
$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Test-Path $ollama)) { $ollama = (Get-Command ollama -ErrorAction Stop).Source }
$modelos = if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $env:USERPROFILE '.ollama\models' }
$clave = Join-Path $env:USERPROFILE '.sidp\clave_cerebro.txt'
$base = Join-Path $env:USERPROFILE '.sidp\base_cerebro.txt'
foreach ($archivo in $clave, $base) {
    if (-not (Test-Path $archivo)) { Write-Host "Falta $archivo (lo crean las tareas 006 y 008)."; exit 1 }
}
Write-Host "Repositorio: $repo"
Write-Host "Python: $python"
Write-Host "Ollama: $ollama (modelos en $modelos)"
New-Item -ItemType Directory -Force $servicios, $registros, (Join-Path $datos 'respaldo') | Out-Null

# 2. Lanzadores: un ciclo por servicio que arranca el programa y lo vuelve a arrancar si se cae.
#    Lo que imprime queda en C:\SIDP-datos\registros\<nombre>.log (y .error.log); lo de la corrida
#    anterior se guarda como .anterior.log, así no crece sin límite.
#    Primero se cargan los ajustes de C:\SIDP-datos\servicios\ajustes.ps1 (modelo que ve, etc.); OLLAMA_HOST va
#    después para que Ollama siga solo en 127.0.0.1 aunque alguien lo cambie ahí.
$plantilla = @'
$ajustes = 'C:\SIDP-datos\servicios\ajustes.ps1'
if (Test-Path $ajustes) { . $ajustes }
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = '__MODELOS__'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
$registro = 'C:\SIDP-datos\registros\__NOMBRE__'
while ($true) {
    foreach ($fin in '.log', '.error.log') {
        if (Test-Path "$registro$fin") { Move-Item "$registro$fin" ($registro + '.anterior' + $fin) -Force }
    }
    Add-Content "$registro.ciclo.log" ((Get-Date -Format s) + ' arranca')
    $p = Start-Process -FilePath '__PROGRAMA__' -ArgumentList '__ARGUMENTOS__' -WorkingDirectory '__CARPETA__' `
        -NoNewWindow -PassThru -RedirectStandardOutput "$registro.log" -RedirectStandardError "$registro.error.log"
    if ($env:SIDP_PRIORIDAD) { try { $p.PriorityClass = $env:SIDP_PRIORIDAD } catch { } }  # Lo que abra después la hereda.
    $p.WaitForExit()
    Add-Content "$registro.ciclo.log" ((Get-Date -Format s) + " se detuvo (código $($p.ExitCode)); vuelve a arrancar en 10 s")
    Start-Sleep -Seconds 10
}
'@

# Ollama: solo en esta PC (127.0.0.1) y con los modelos de este usuario.
[Environment]::SetEnvironmentVariable('OLLAMA_HOST', '127.0.0.1:11434', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $modelos, 'User')

# Ajustes que se conservan: este script nunca sobrescribe ajustes.ps1. La primera vez se llena con lo que se
# haya agregado a mano a los lanzadores (para no perderlo) y con valores para una PC sin tarjeta de video.
# Con -MismaPC se agregan los del servidor que también es el cerebro (solo los que falten).
$archivoAjustes = Join-Path $servicios 'ajustes.ps1'
$deMismaPC = @(
    "`$env:SIDP_CEREBRO_ANFITRION = '127.0.0.1'",
    "`$env:SIDP_PRIORIDAD = 'BelowNormal'",
    "`$env:OLLAMA_MAX_LOADED_MODELS = '1'",
    "`$env:OLLAMA_NUM_PARALLEL = '1'",
    "`$env:SIDP_SIN_PADDLE = '1'"
)
if (Test-Path $archivoAjustes) {
    Write-Host "Ajustes: se conservan los de $archivoAjustes"
    if ($MismaPC) {
        $yaPuestos = @(Get-Content $archivoAjustes | Where-Object { $_ -match '^\s*\$env:' } | ForEach-Object { ($_ -split '=')[0].Trim() })
        $faltan = @($deMismaPC | Where-Object { $yaPuestos -notcontains ($_ -split '=')[0].Trim() })
        if ($faltan.Count) {
            Add-Content -Encoding UTF8 $archivoAjustes $faltan
            Write-Host "Ajustes del servidor que también es cerebro agregados: $($faltan.Count)"
        }
    }
} else {
    $previos = @()
    foreach ($nombre in 'ollama.ps1', 'cerebro.ps1') {
        $archivo = Join-Path $servicios $nombre
        if (Test-Path $archivo) {
            $previos += Get-Content $archivo | Where-Object { $_ -match '^\s*\$env:(SIDP|OLLAMA)_\w+\s*=' -and $_ -notmatch '\$env:OLLAMA_(HOST|MODELS)\b' } |
                ForEach-Object { $_.Trim() }
        }
    }
    $previos = @($previos | Select-Object -Unique)
    $yaPuestos = @($previos | ForEach-Object { ($_ -split '=')[0].Trim() })
    $porOmision = @(@(
        "`$env:SIDP_MODELO_VISION = 'qwen2.5vl:3b'",
        "`$env:SIDP_LADO_VISION = '960'",
        "`$env:SIDP_LECTURAS_VISION = '1'",
        "`$env:OLLAMA_FLASH_ATTENTION = '1'",
        "`$env:OLLAMA_KEEP_ALIVE = '$(if ($MismaPC) { '30m' } else { '24h' })'"
    ) + @($deMismaPC | Where-Object { $MismaPC }) | Where-Object { $yaPuestos -notcontains ($_ -split '=')[0].Trim() })
    $encabezado = @(
        '# Ajustes de la PC 4. instalar_servicios.ps1 no toca este archivo: lo que cambies aquí se queda.',
        '# Después de cambiar algo, reinicia la PC 4 (o vuelve a correr instalar_servicios.ps1).',
        '#   SIDP_MODELO_VISION: el modelo que ve (python -m validacion.vision modelos dice cuáles hay).',
        '#   SIDP_LADO_VISION: píxeles de la hoja para el modelo (menos = más rápido, pero la letra chica se pierde).',
        '#   SIDP_LECTURAS_VISION: 1 (aceptado); 2 = lee cada hoja dos veces y lo que no coincide queda por confirmar (más lento).',
        '#   SIDP_RESPALDO y SIDP_RESPALDOS: carpetas del respaldo del servidor y de la copia diaria de la base (por omisión en C:\SIDP-datos).',
        '#   Servidor que también es cerebro (-MismaPC): SIDP_CEREBRO_ANFITRION, SIDP_PRIORIDAD, OLLAMA_MAX_LOADED_MODELS, SIDP_SIN_PADDLE.',
        '#   OLLAMA_HOST y OLLAMA_MODELS no van aquí: los pone el lanzador (Ollama solo en 127.0.0.1).'
    )
    Set-Content -Encoding UTF8 $archivoAjustes ($encabezado + $previos + $porOmision)
    Write-Host "Ajustes guardados en $archivoAjustes ($($previos.Count) tomados de los lanzadores anteriores)"
}

$lanzadores = @{
    'SIDP-Ollama'  = @{ Nombre = 'ollama'; Programa = $ollama; Argumentos = 'serve'; Carpeta = $servicios; Retraso = 'PT0S' }
    'SIDP-Cerebro' = @{ Nombre = 'cerebro'; Programa = $python; Carpeta = $repo; Retraso = 'PT30S'
                        Argumentos = "-m validacion.cerebro_red --clave `"$clave`" --base `"$base`" --esperar-base 120 --exigir-base --sin-mostrar-clave" }
}
foreach ($tarea in $tareas) {
    $l = $lanzadores[$tarea]
    $texto = $plantilla.Replace('__MODELOS__', $modelos).Replace('__NOMBRE__', $l.Nombre).Replace('__PROGRAMA__', $l.Programa)
    $texto = $texto.Replace('__ARGUMENTOS__', $l.Argumentos.Replace("'", "''")).Replace('__CARPETA__', $l.Carpeta)
    Set-Content -Encoding UTF8 (Join-Path $servicios "$($l.Nombre).ps1") $texto
}

# 3. Las tareas programadas: al encender, sin iniciar sesión, sin límite de tiempo.
$usuario = "$env:USERDOMAIN\$env:USERNAME"
foreach ($tarea in $tareas) {
    $l = $lanzadores[$tarea]
    $argumentos = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$servicios\$($l.Nombre).ps1`""
    $accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argumentos -WorkingDirectory $l.Carpeta
    $disparo = New-ScheduledTaskTrigger -AtStartup
    $disparo.Delay = $l.Retraso
    if ($ComoSistema) { $quien = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest }
    else { $quien = New-ScheduledTaskPrincipal -UserId $usuario -LogonType S4U -RunLevel Limited }
    $ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    if (Get-ScheduledTask -TaskName $tarea -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $tarea -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $tarea -Confirm:$false
    }
    Register-ScheduledTask -TaskName $tarea -Action $accion -Trigger $disparo -Principal $quien -Settings $ajustes `
        -Description 'SIDP: arranca al encender la PC 4 (cerebro/pc4/instalar_servicios.ps1)' | Out-Null
    Write-Host "Tarea $tarea lista$(if ($ComoSistema) { ' (cuenta del sistema)' })."
}

# 3b. El vigía: con la cuenta del sistema, al encender y luego cada 2 minutos, sin fin.
Copy-Item (Join-Path $PSScriptRoot 'vigia.ps1') (Join-Path $servicios 'vigia.ps1') -Force
$argumentos = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$servicios\vigia.ps1`" -ArchivoClave `"$clave`""
$accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argumentos -WorkingDirectory $servicios
$cada = (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)).Repetition
$alEncender = New-ScheduledTaskTrigger -AtStartup
$alEncender.Delay = 'PT2M'
$alEncender.Repetition = $cada
$desdeYa = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)
$quien = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
if (Get-ScheduledTask -TaskName $vigia -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $vigia -Confirm:$false }
Register-ScheduledTask -TaskName $vigia -Action $accion -Trigger $alEncender, $desdeYa -Principal $quien -Settings $ajustes `
    -Description 'SIDP: revisa cada 2 minutos que Ollama, PostgreSQL y el cerebro contesten (cerebro/pc4/vigia.ps1)' | Out-Null
Write-Host "Tarea $vigia lista (revisa cada 2 minutos; anota en $registros\vigia.log)."

# 4. PostgreSQL arranca solo (ya es servicio; se asegura).
Get-Service -Name 'postgresql*' | ForEach-Object {
    Set-Service -Name $_.Name -StartupType Automatic
    if ($_.Status -ne 'Running') { Start-Service $_.Name }
    Write-Host "PostgreSQL ($($_.Name)): arranque automático."
}

# 5. El Ollama del inicio de sesión ya no hace falta (chocaría con la tarea). No se borra: se guarda aparte.
New-Item -ItemType Directory -Force $guardados | Out-Null
Get-ChildItem $inicio -Filter 'Ollama*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
    Move-Item $_.FullName $guardados -Force
    Write-Host "Acceso de inicio $($_.Name) guardado en $guardados"
}

# 6. Energía: nunca dormir ni hibernar, y sin "inicio rápido" (con él, Windows no siempre corre las tareas de arranque).
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -Value 0
Write-Host 'Energía: sin suspensión, sin hibernación y sin inicio rápido.'

# 7. Arranca ya, sin esperar a reiniciar: cierra lo que se haya abierto a mano y lo de la corrida anterior.
#    Detener la tarea no cierra a sus hijos (Tarea 013): primero los lanzadores, para que no los vuelvan a abrir,
#    y luego Ollama con todo su árbol, para que no quede uno viejo ocupando el puerto 11434.
Get-CimInstance Win32_Process -Filter "Name like 'powershell%'" | Where-Object { $_.CommandLine -like '*SIDP-datos\servicios\*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
cmd.exe /c 'taskkill /F /T /IM ollama.exe >nul 2>&1'  # Dentro de cmd: si no hay ninguno, su aviso no detiene el script.
Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like '*validacion.cerebro_red*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3
foreach ($tarea in $tareas) { Start-ScheduledTask -TaskName $tarea }
Write-Host 'Listo. En un minuto corre: powershell -ExecutionPolicy Bypass -File cerebro\pc4\estado_servicios.ps1'
