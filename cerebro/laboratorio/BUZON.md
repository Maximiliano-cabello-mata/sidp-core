# Buzón: tareas de Claude para el agente de la PC 4

Una tarea está hecha cuando su informe está en `resultados/`. Las reglas están en [LEEME.md](LEEME.md#cómo-se-comunican-claude-y-el-agente-de-la-pc-4).

## Tarea 001: crear el modelo y correr las fichas (2026-10-14)

1. En la carpeta del repositorio `sidp-core`, actualiza y cambia a la rama de trabajo:
   ```
   git fetch origin
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Crea el modelo con el Modelfile. `ollama` no está en el PATH, así que usa la ruta completa del ejecutable:
   ```
   & "<ruta>\ollama.exe" create sidp-revisor -f cerebro\laboratorio\Modelfile
   ```
   Comprueba que `sidp-revisor` aparece en `ollama list`.
3. Corre solo los procesos. Debe decir "11 de 11":
   ```
   python -m cerebro.laboratorio.correr --sin-modelo
   ```
4. Anota la RAM libre y corre con el modelo:
   ```
   python -m cerebro.laboratorio.correr
   ```
5. Al final del informe que quedó en `cerebro/laboratorio/resultados/`, agrega una sección "## Notas del agente" con:
   - la RAM libre antes y después;
   - si la PC se puso lenta;
   - cualquier error, completo.
6. Sube solo ese informe:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 001"
   git pull --rebase
   git push
   ```
7. Avísale a Maximiliano que ya se subió.

Resultado (2026-10-14): procesos 11 de 11; con `sidp-revisor`, 9 de 12 opiniones acertadas y ninguna peligrosa, 6.3 s por opinión. Falló el error de una letra (ficha 9): dijo "no" cuando era "si".

## Tarea 002: zona gris con más casos y el modelo con ejemplos (2026-10-15)

Antes había solo 4 comparaciones en zona gris, muy pocas para saber si el modelo sirve. Ahora son 18 pares, y hay una segunda versión del modelo con ejemplos.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Crea la segunda versión del modelo (no descarga nada):
   ```
   & "<ruta>\ollama.exe" create sidp-revisor-2 -f cerebro\laboratorio\Modelfile.2
   ```
3. Comprueba los procesos. Debe decir "11 de 11" y "18 de 18":
   ```
   python -m cerebro.laboratorio.correr --sin-modelo
   python -m cerebro.laboratorio.correr --pares --sin-modelo
   ```
4. Corre los 18 pares con las dos versiones, una después de otra:
   ```
   python -m cerebro.laboratorio.correr --pares --modelo sidp-revisor
   python -m cerebro.laboratorio.correr --pares --modelo sidp-revisor-2
   ```
5. Agrega "## Notas del agente" al final de cada informe nuevo (RAM libre antes y después, errores).
6. Sube solo los dos informes nuevos de `cerebro/laboratorio/resultados/`:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 002"
   git pull --rebase
   git push origin claude/project-thread-vp6ab8
   ```
7. Avísale a Maximiliano que ya se subió.

Resultado (2026-10-15): `sidp-revisor` acertó 27 de 54 y `sidp-revisor-2` 42 de 54, en unos 5 s por opinión. Los dos dijeron "si" cuando era "no" 12 veces. Con `sidp-revisor-2` fue cuando faltaba un apellido (pares 3 y 12), con el nombre al revés (par 10) y con Reyes / Reyna (par 8). Desde ahora esos casos los reconoce el proceso y quedan en "duda" sin preguntar al modelo.

## Tarea 003: el modelo solo opina donde los procesos no saben (2026-10-15)

Ahora el proceso deja en "duda", sin preguntar al modelo, los nombres en otro orden, los que tienen un nombre o apellido de más o de menos y los que cambian más de una letra en una palabra. Hay 12 pares nuevos (19 a 30) que no se usaron para ajustar nada: sirven para ver si el modelo acierta en casos que no conoce. El modelo de siempre ahora es `sidp-revisor-2`; no hay que crear otro.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Comprueba los procesos. Debe decir "11 de 11", "30 de 30" y "5 de 5":
   ```
   python -m cerebro.laboratorio.correr --sin-modelo
   python -m cerebro.laboratorio.correr --pares --sin-modelo
   ```
3. Corre los 30 pares y luego las 11 fichas con el modelo:
   ```
   python -m cerebro.laboratorio.correr --pares
   python -m cerebro.laboratorio.correr
   ```
   Mientras corren, mira en el Administrador de tareas cuánto CPU usa Ollama.
4. Agrega "## Notas del agente" al final de cada informe nuevo (RAM libre antes y después, uso de CPU, errores).
5. Sube solo los dos informes nuevos de `cerebro/laboratorio/resultados/`:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 003"
   git pull --rebase
   git push origin claude/project-thread-vp6ab8
   ```
6. Avísale a Maximiliano que ya se subió.

## Tarea 004: probar el validador de expedientes con el ejemplo (2026-10-15)

El validador revisa expedientes completos: lo que el padre capturó contra el texto de sus documentos. La guía está en [docs/guias/PRUEBA_VALIDACION.md](../../docs/guias/PRUEBA_VALIDACION.md). Esta tarea solo usa el ejemplo inventado; la prueba con documentos reales la arma Maximiliano después.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Anota qué herramientas tiene la PC 4 (no instales nada):
   ```
   python -c "from validacion import lector; print(lector.herramientas())"
   ```
3. Corre el ejemplo sin modelo. Debe decir "Falsos que pasaron como listos (peligroso): 0 de 6":
   ```
   python -m validacion.prueba validacion\ejemplo --hoy 2026-10-14 --sin-modelo
   ```
4. Córrelo con el modelo:
   ```
   python -m validacion.prueba validacion\ejemplo --hoy 2026-10-14
   ```
5. Abre `validacion\ejemplo\informe_local.html` en el navegador y revisa que se vea bien.
6. Copia `validacion\ejemplo\resumen_para_repo.md` como `cerebro\laboratorio\resultados\2026-10-15_validador_ejemplo.md`. Agrega al final "## Notas del agente" con lo que dijo el paso 2, cuánto tardó y cualquier error.
7. Sube solo ese archivo:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 004"
   git pull --rebase
   git push origin claude/project-thread-vp6ab8
   ```
8. Avísale a Maximiliano que ya se subió.

## Tarea 005: dejar la PC 4 como validación y cerebro por IP (2026-10-15)

Maximiliano autorizó instalar en la PC 4 lo que haga falta. Desde ahora la PC 4 valida los
expedientes y es el cerebro: SIDP-Validador.exe, en la PC del administrador, le manda cada
expediente por la red y ella responde. Tú solo preparas la PC y arrancas el cerebro; no participas
en la validación. La guía completa, con todos los comandos, está en
[docs/guias/ENTORNO_PRUEBAS.md](../../docs/guias/ENTORNO_PRUEBAS.md), Parte 1.

1. Actualiza la rama (Parte 1, paso 1).
2. Instala pypdf, opencv y Tesseract con español, y comprueba que las cuatro herramientas digan `True` (paso 2).
3. Revisa que exista `sidp-revisor-2` en Ollama (paso 3). No cambies a Ollama de `127.0.0.1`.
4. Pon la red como Privada, abre el puerto 8771 solo en red Privada y quita la suspensión (paso 4).
5. Arranca el cerebro con `validacion\iniciar_cerebro.bat` y deja la ventana abierta (paso 5).
6. Prueba `/salud` con la clave (paso 6).
7. Muéstrale a Maximiliano, **en la pantalla**, la dirección y la clave. **Nunca** escribas la clave
   en un archivo del repositorio, en el informe ni en un mensaje.
8. Corre el ejemplo con todo instalado. Debe decir "Falsos que pasaron como listos (peligroso): 0 de 6":
   ```
   python -m validacion.prueba validacion\ejemplo --hoy 2026-10-14
   ```
9. Escribe `cerebro\laboratorio\resultados\2026-10-15_entorno_pc4.md` con: lo que dijo `lector.herramientas()`,
   lo que respondió `/salud` (sin la clave), si la red quedó Privada, si se creó la regla del firewall,
   el resumen del paso 8 y cualquier error. No pongas la IP ni la clave.
10. Sube solo ese archivo:
    ```
    git add cerebro/laboratorio/resultados/
    git commit -m "laboratorio: resultado de la tarea 005"
    git pull --rebase
    git push origin claude/project-thread-vp6ab8
    ```
11. Avísale a Maximiliano que ya se subió y que el cerebro quedó encendido.

## Tarea 006: mejor lectura de fotos y escaneos en la PC 4 (2026-10-15)

En la primera prueba real casi no se leyeron las fotos ni los escaneos. Ya está el lector nuevo:
convierte las páginas del PDF en imagen, recorta la hoja, quita la perspectiva y las sombras, la
gira si viene de lado, lee QR y códigos de barras, y la franja `<<<` de la INE. Con 49 fotos
inventadas, los avisos de "no parece" bajaron de 8 a 0. Esta tarea lo instala y lo mide en la PC 4.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Instala lo nuevo (PowerShell):
   ```
   python --version
   python -m pip install -r validacion/requisitos.txt
   python -m pip install -r validacion/requisitos_paddle.txt
   ```
   Si PaddleOCR no se instala (por ejemplo, por la versión de Python), anota el error completo y sigue: el lector usa Tesseract.
3. Comprueba las herramientas. La primera vez PaddleOCR baja sus modelos:
   ```
   python -m validacion.lector
   ```
4. Crea las fotos inventadas **fuera del repositorio** y mídelas dos veces, con Tesseract y con PaddleOCR:
   ```
   python -m validacion.ejemplo.fotos "$env:USERPROFILE\SIDP-fotos"
   $env:SIDP_SIN_PADDLE = "1"
   python -m validacion.prueba "$env:USERPROFILE\SIDP-fotos" --hoy 2026-10-14 --sin-modelo
   Copy-Item "$env:USERPROFILE\SIDP-fotos\resumen_para_repo.md" "$env:USERPROFILE\SIDP-fotos\resumen_tesseract.md"
   Remove-Item Env:SIDP_SIN_PADDLE
   python -m validacion.prueba "$env:USERPROFILE\SIDP-fotos" --hoy 2026-10-14 --sin-modelo
   ```
5. Reinicia el cerebro para que use el lector nuevo: cierra su ventana y abre otra vez
   `validacion\iniciar_cerebro.bat`. La clave no cambia.
6. Escribe `cerebro\laboratorio\resultados\2026-10-15_lectura_pc4.md` con: la versión de Python, lo que dijo
   `python -m validacion.lector`, los dos resúmenes del paso 4 (el de Tesseract y el de PaddleOCR), cuánto
   tardó cada uno y cualquier error. No pongas la IP ni la clave.
7. Sube solo ese archivo:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 006"
   git pull --rebase
   git push origin claude/project-thread-vp6ab8
   ```
8. Avísale a Maximiliano que ya se subió y que el cerebro quedó encendido con el lector nuevo.

## Tarea 007: el cerebro lee los escaneos del día de escaneo (2026-10-15)

El Validador ahora tiene un cuadro "Escanear expediente (ya revisado en papel)". Los escaneos son PDF de
pura imagen: los lee la PC 4 con Tesseract por la ruta nueva `/leer` del cerebro. Esta tarea solo actualiza
y reinicia; no hay que medir ni subir nada.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Reinicia el cerebro: cierra su ventana y abre otra vez `validacion\iniciar_cerebro.bat`. La clave y la
   dirección no cambian.
3. Comprueba que está encendido. Sin la clave responde `clave incorrecta`, y eso basta:
   ```
   curl.exe http://127.0.0.1:8771/salud
   ```
4. Avísale a Maximiliano que el cerebro quedó encendido con el código del día de escaneo.

## Tarea 008: base de datos PostgreSQL para el cerebro (2026-10-15)

Maximiliano decidió que la PC 4 tenga su propia base de datos, PostgreSQL, para hacer mejores procesos. Ahí
el cerebro guarda el padrón de alumnos (lo manda SIDP-Validador.exe) y compara lo que lee contra los
nombres y CURP reales: una CURP con una o dos letras mal leídas, o un apellido mal escrito, se reconocen.
PostgreSQL escucha **solo en 127.0.0.1**, como Ollama: nadie de la red entra a la base, todo pasa por el
cerebro y su clave. Las contraseñas se quedan en `%USERPROFILE%\.sidp\` y **nunca** van al repositorio ni
al informe.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Crea las dos contraseñas (quedan solo en esta PC):
   ```
   New-Item -ItemType Directory -Force "$env:USERPROFILE\.sidp" | Out-Null
   $admin = [guid]::NewGuid().ToString('N'); $admin | Set-Content -NoNewline -Encoding ascii "$env:USERPROFILE\.sidp\postgres_admin.txt"
   $clave = [guid]::NewGuid().ToString('N')
   ```
3. Instala PostgreSQL 17 sin pgAdmin. Baja el instalador de Windows x86-64 de
   https://www.enterprisedb.com/downloads/postgres-postgresql-downloads (la versión 17 más nueva) y córrelo así,
   cambiando el nombre del archivo por el que bajaste:
   ```
   & ".\postgresql-17.X-X-windows-x64.exe" --mode unattended --unattendedmodeui none --superpassword $admin `
     --serverport 5432 --disable-components pgAdmin,stackbuilder
   ```
   Si `winget` está disponible, también sirve `winget install -e --id PostgreSQL.PostgreSQL.17`; en ese caso
   anota qué contraseña quedó para el usuario `postgres` y guárdala en `postgres_admin.txt`.
4. Que escuche solo en esta PC. En `C:\Program Files\PostgreSQL\17\data\postgresql.conf` deja la línea
   `listen_addresses = 'localhost'` (sin `#` al inicio) y reinicia el servicio:
   ```
   Get-Service postgresql* | Restart-Service
   netstat -ano | findstr :5432
   ```
   Solo deben salir `127.0.0.1:5432` y `[::1]:5432`. Si hay una regla del firewall para PostgreSQL, desactívala:
   `Get-NetFirewallRule | Where-Object DisplayName -like '*Postgre*' | Disable-NetFirewallRule`.
5. Crea el usuario y la base del cerebro:
   ```
   $env:PGPASSWORD = $admin
   $psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
   & $psql -U postgres -h 127.0.0.1 -c "CREATE ROLE sidp LOGIN PASSWORD '$clave'"
   & $psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE sidp_cerebro OWNER sidp"
   Remove-Item Env:PGPASSWORD
   "postgresql://sidp:$clave@127.0.0.1:5432/sidp_cerebro" | Set-Content -NoNewline -Encoding ascii "$env:USERPROFILE\.sidp\base_cerebro.txt"
   ```
6. Instala el conector (pg8000, solo Python: sirve con cualquier versión) y crea las tablas:
   ```
   python -m pip install -r validacion/requisitos.txt
   python -m validacion.base_cerebro
   ```
   Debe decir `Base lista: PostgreSQL 17..., 0 alumnos en el padrón`.
7. Reinicia el cerebro: cierra su ventana y abre otra vez `validacion\iniciar_cerebro.bat`. Ahora debe decir
   `Base de datos: PostgreSQL 17... con 0 alumnos en el padrón`. La clave del cerebro y la dirección no cambian.
8. Escribe `cerebro\laboratorio\resultados\2026-10-15_base_pc4.md` con: la versión de PostgreSQL, lo que dijo el
   paso 6, lo que dijo el cerebro al arrancar (sin la clave), lo que salió de `netstat` en el paso 4 y cualquier
   error completo. No pongas contraseñas, la clave del cerebro ni la IP.
9. Sube solo ese archivo:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 008"
   git pull --rebase
   git push origin claude/project-thread-vp6ab8
   ```
10. Avísale a Maximiliano que la base quedó lista. Él abre **Ajustes** en el panel y da **Conectar**: el panel debe
    decir `Padrón en la base del cerebro (PostgreSQL ...): N alumnos`.

## Tarea 009: base de datos completa y carga de todos los alumnos (2026-10-15)

La base de la PC 4 pasa a la versión 2: el expediente completo (alumnos, grupos, tutores, inscripciones,
documentos, revisiones, lecturas y bitácora) con sus procesos dentro de PostgreSQL. Explicación en
`docs/arquitectura/base_cerebro.md`. Después se cargan todos los alumnos desde la lista oficial de la SEP.

**La lista oficial tiene datos de menores: nunca va dentro de la carpeta del repositorio, nunca se sube y
sus nombres o CURP nunca van al informe.** Los comandos de esta tarea solo imprimen números.

No hace falta PowerShell de administrador.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Maximiliano te da el PDF de la lista oficial (USB o carpeta compartida). Guárdalo **fuera del
   repositorio**, en `C:\SIDP-datos\lista_oficial.pdf`:
   ```
   New-Item -ItemType Directory -Force C:\SIDP-datos | Out-Null
   ```
3. Actualiza la base a la versión 2. Lo que ya había pasa solo y nada se borra:
   ```
   python -m validacion.base_cerebro
   ```
   Debe decir `Base lista: PostgreSQL 17..., esquema 2, ...`.
4. Carga la lista oficial:
   ```
   python -m validacion.base_cerebro cargar C:\SIDP-datos\lista_oficial.pdf --ciclo 2026-2027
   ```
   Deben salir 6 grupos, de 1° A a 6° A, con sus alumnos, y al final cuántos son nuevos. Si lo corres otra
   vez, debe decir que ese archivo ya se había cargado.
5. Saca el informe (solo números):
   ```
   python -m validacion.base_cerebro informe
   ```
6. Reinicia el cerebro: cierra su ventana y abre otra vez `validacion\iniciar_cerebro.bat`. Debe decir
   `Base de datos: PostgreSQL 17... con N alumnos inscritos`. La clave y la dirección no cambian.
7. Escribe `cerebro\laboratorio\resultados\2026-10-15_base_v2_pc4.md` con lo que imprimieron los pasos 3, 4,
   5 y 6 (sin la clave) y cualquier error completo. Antes de subirlo, revisa que no tenga ningún nombre ni
   CURP. No pongas contraseñas ni la IP.
8. Sube solo ese archivo:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 009"
   git pull --rebase
   git push origin claude/project-thread-vp6ab8
   ```
9. Avísale a Maximiliano que la base quedó cargada.
