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

## Tarea 010: base de la PC 4 desde cero con la lista revisada (2026-10-15)

Maximiliano pidió borrar todo lo que tiene la base de la PC 4 y volver a cargar la lista de alumnos ya
revisada. Esa lista sale del mismo PDF oficial que ya está en `C:\SIDP-datos\lista_oficial.pdf`: con el
código nuevo se separan los nombres pegados y se respetan las Ñ, y salen los 191 alumnos revisados uno por
uno. Después, el panel de la PC del administrador trae la lista desde la PC 4 al conectarse al cerebro.

**La lista tiene datos de menores: no se copia al repositorio, no se sube a GitHub y ningún nombre ni CURP
va en el informe.** Todos los comandos de esta tarea imprimen solo números.

No hace falta PowerShell de administrador.

1. Actualiza la rama:
   ```
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Revisa que el PDF siga en su lugar (debe decir `True`):
   ```
   Test-Path C:\SIDP-datos\lista_oficial.pdf
   ```
3. Borra toda la base. Esto quita alumnos, grupos, lecturas y bitácora, y la deja vacía con el esquema nuevo:
   ```
   python -m validacion.base_cerebro borrar --si-borrar-todo
   ```
   Debe decir `Base borrada: quedó vacía, con el esquema nuevo.` y luego `... 0 alumnos inscritos ...`.
4. Carga la lista:
   ```
   python -m validacion.base_cerebro cargar C:\SIDP-datos\lista_oficial.pdf --ciclo 2026-2027
   ```
   Debe decir: 1° A 34, 2° A 31, 3° A 33, 4° A 32, 5° A 32, 6° A 29; `191 alumnos nuevos`, `191 inscritos`,
   `0 renglones rechazados`. Si sale otro número, detente y anótalo en el informe.
5. Saca el informe (solo números):
   ```
   python -m validacion.base_cerebro informe
   ```
   Debe haber 93 hombres y 98 mujeres en total, y una sola alerta `curp_digito` (una CURP del PDF que la
   escuela debe confirmar).
6. Reinicia el cerebro: cierra su ventana y abre otra vez `validacion\iniciar_cerebro.bat`. Debe decir
   `Base de datos: PostgreSQL 17... con 191 alumnos inscritos`. La clave y la dirección no cambian.
7. Comprueba que el cerebro entrega la lista al panel. Cambia `CLAVE` por la clave del cerebro (no la
   escribas en el informe). Solo imprime cuántos alumnos hay por grupo:
   ```
   python -c "import json,sys,urllib.request as u; r=u.Request('http://127.0.0.1:8771/alumnos', headers={'X-SIDP-Clave': sys.argv[1]}); d=json.load(u.urlopen(r)); print(d['ciclo'], [(g['grado'], g['letra'], len(g['filas'])) for g in d['grupos']])" CLAVE
   ```
   Debe decir `2026-2027 [(1, 'A', 34), (2, 'A', 31), (3, 'A', 33), (4, 'A', 32), (5, 'A', 32), (6, 'A', 29)]`.
8. Escribe `cerebro\laboratorio\resultados\2026-10-15_lista_pc4.md` con lo que imprimieron los pasos 3 a 7
   (sin la clave) y cualquier error completo. Antes de subirlo, revisa que no tenga ningún nombre ni CURP.
   No pongas contraseñas ni la IP.
9. Sube solo ese archivo:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 010"
   git pull --rebase
   git push origin claude/project-thread-vp6ab8
   ```
10. Avísale a Maximiliano que la lista ya está en la PC 4 y que ya puede abrir el panel.

## Tarea 011: PC 4 como respaldo, análisis de datos e inventario; base optimizada (2026-10-16)

La PC 4 no es la base principal: la principal es la del .exe en la PC del administrador. La PC 4 guarda
(1) la copia de respaldo de todo lo que guarda el .exe (llega sola cada hora a `C:\SIDP-datos\respaldo`),
(2) la base PostgreSQL de alumnos y expedientes, que ahora también trae el inventario de la escuela, y
(3) hace el análisis de datos con pandas (solo números; llama3.1 puede redactar un resumen, pero es opcional).

**Nada de nombres, CURP, clave del cerebro, contraseñas ni IP en el informe.** Un borrado no se deshace:
en esta tarea solo se borra lo que dice el paso 7, y antes se respalda la base (paso 3).

1. Actualiza la rama (en la carpeta del repositorio):
   ```
   git pull origin claude/project-thread-vp6ab8
   ```
2. Instala pandas (hay versión para Python 3.15):
   ```
   python -m pip install -r validacion/requisitos.txt
   ```
3. **Antes de todo**, respalda la base (usa pg_dump de PostgreSQL):
   ```
   python -m validacion.base_cerebro respaldar
   ```
   Debe decir `Respaldo listo: C:\SIDP-datos\respaldos\... (N MB)`. Si dice `No se respaldó`, detente aquí,
   anota el error completo en el informe y no hagas los pasos 5 y 7.
4. Aplica el esquema nuevo (tablas del inventario e índices). No borra nada:
   ```
   python -m validacion.base_cerebro
   ```
   Debe decir `... 191 alumnos inscritos ...`.
5. Optimiza la base (limpia filas muertas, rehace índices y estadísticas):
   ```
   python -m validacion.base_cerebro optimizar
   ```
6. Prueba el análisis (imprime solo frases con números):
   ```
   python -m validacion.base_cerebro analisis
   ```
   Debe empezar con `Análisis con pandas ...` y decir que hay 191 alumnos.
7. Limpieza. **Primero solo mide** y anota los tamaños en el informe:
   ```
   python -m pip cache info
   Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum
   ```
   Después borra **solo** estas dos cosas, que son temporales y se vuelven a crear solas:
   ```
   python -m pip cache purge
   Get-ChildItem $env:TEMP -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
   ```
   **No borres** `C:\SIDP-datos`, la carpeta del repositorio, la carpeta de datos de PostgreSQL, los modelos de
   Ollama ni ningún programa. Si ves algo más grande que parezca sobrar, solo anótalo (ruta y tamaño) en el
   informe; Maximiliano decide.
8. Crea la carpeta donde llega la copia del .exe:
   ```
   New-Item -ItemType Directory -Force C:\SIDP-datos\respaldo
   ```
9. Reinicia el cerebro: cierra su ventana y abre otra vez `validacion\iniciar_cerebro.bat`.
10. Comprueba el análisis y el inventario. Cambia `CLAVE` por la clave del cerebro (no la escribas en el
    informe). Solo imprime números:
    ```
    python -c "import json,sys,urllib.request as u; p=lambda r: json.load(u.urlopen(u.Request('http://127.0.0.1:8771'+r, headers={'X-SIDP-Clave': sys.argv[1]}))); a=p('/analisis'); i=p('/inventario'); print('alumnos', a['kpis']['alumnos'], 'piezas', len(i['piezas']), 'respaldo', p('/respaldo'))" CLAVE
    ```
    Debe decir `alumnos 191 piezas 0 respaldo {...}`.
11. Escribe `cerebro\laboratorio\resultados\2026-10-16_tarea011_pc4.md` con lo que imprimieron los pasos 3 a
    10 (tamaños antes y después) y cualquier error completo. Revisa que no tenga nombres, CURP, clave ni IP.
12. Sube solo ese archivo:
    ```
    git add cerebro/laboratorio/resultados/
    git commit -m "laboratorio: resultado de la tarea 011"
    git pull --rebase origin claude/project-thread-vp6ab8
    git push origin claude/project-thread-vp6ab8
    ```
13. Avísale a Maximiliano que la PC 4 ya está lista para el inventario, el análisis y los respaldos.

## Tarea 012: la PC 4 arranca sola sin monitor, y el modelo que ve (2026-10-16)

La PC 4 va a trabajar sin monitor: se enciende y debe tener listos, sin que nadie inicie sesión, la base
(PostgreSQL), los modelos (Ollama) y el cerebro (puerto 8771). El script `cerebro\pc4\instalar_servicios.ps1`
lo deja así con tareas programadas de Windows; se puede deshacer con `-Quitar`. Además se instala el modelo
que ve (lee letra a mano) para el escaneo.

**No se borra nada en esta tarea.** El acceso de Ollama del inicio de sesión no se borra: el script lo mueve a
`C:\SIDP-datos\servicios\accesos_de_inicio_guardados`. Nada de nombres, CURP, clave, contraseñas ni IP en el informe.

1. Actualiza la rama (en la carpeta del repositorio):
   ```
   git pull origin claude/project-thread-vp6ab8
   ```
2. Cierra la ventana del cerebro si está abierta. Abre **PowerShell como administrador** (clic derecho >
   Ejecutar como administrador; si tú no puedes, pídeselo a Maximiliano), entra a la carpeta del repositorio y corre:
   ```
   powershell -ExecutionPolicy Bypass -File cerebro\pc4\instalar_servicios.ps1
   ```
   Debe terminar con `Tarea SIDP-Ollama lista.`, `Tarea SIDP-Cerebro lista.`, `PostgreSQL (...): arranque
   automático.` y `Listo.`. Si sale un error en rojo, cópialo completo al informe y detente.
3. Espera un minuto y revisa (PowerShell normal):
   ```
   powershell -ExecutionPolicy Bypass -File cerebro\pc4\estado_servicios.ps1
   ```
   Debe decir que PostgreSQL, Ollama y el cerebro escuchan, `Cerebro: responde. Base: PostgreSQL ..., 191 alumnos`
   y la lista de modelos.
4. Instala el modelo que ve (pesa unos 6 GB; puede tardar). Ollama no está en el PATH, así que usa la ruta completa:
   ```
   & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen3-vl:8b
   ```
   Si dice que no existe o falla, instala este otro en su lugar:
   ```
   & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen2.5vl:7b
   ```
   Luego comprueba cuál quedó:
   ```
   python -m validacion.vision modelos
   ```
5. Mide cuánto tarda en leer una hoja (con documentos inventados, fuera del repositorio):
   ```
   python -m validacion.ejemplo.fotos C:\SIDP-datos\fotos_inventadas
   Get-ChildItem C:\SIDP-datos\fotos_inventadas -Recurse -Include *.jpg,*.png | Select-Object -First 3 | ForEach-Object { python -m validacion.vision prueba $_.FullName }
   ```
   Cada renglón dice en cuántos segundos leyó la hoja. Anota los tres.
6. Prueba de verdad (con Maximiliano): reinicia la PC 4 (`Restart-Computer`) y **no inicies sesión**. Después de
   3 minutos, en la PC del administrador abre el panel de SIDP-Validador y revisa que diga que el cerebro está
   conectado. Luego inicia sesión en la PC 4 y vuelve a correr el paso 3.
7. Escribe `cerebro\laboratorio\resultados\2026-10-16_tarea012_pc4.md` con lo que imprimieron los pasos 2 a 6
   (sin la clave ni la IP) y cualquier error completo. Revisa que no tenga nombres ni CURP.
8. Sube solo ese archivo:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 012"
   git pull --rebase origin claude/project-thread-vp6ab8
   git push origin claude/project-thread-vp6ab8
   ```

## Tarea 013: código nuevo del escaneo, modelo que ve más rápido y medición de la letra a mano (2026-10-16)

Gracias por la Tarea 012: con tu desglose de tiempos se cambió el código. Ahora el modelo que ve **no "piensa"**
antes de contestar (eso era lo que hacía tardar 9 minutos a qwen3-vl), la hoja se le manda de 1280 px en lugar
de 1600 (menos tokens de imagen) y, si los procesos ya leyeron todo de un PDF con texto o QR, ni se le pregunta.
El escaneo saca el dato de cada campo (nombre, teléfonos, tipo de sangre, alergias, domicilio...) y lo guarda en la
base de la PC 4; el modelo lee cada hoja **dos veces** y lo que no coincide queda "por confirmar". Aquí se mide
cuánto acierta con letra a mano, con fichas **inventadas** (meta: 80 % bien, solo o con un clic, y casi cero
"peligrosos").

Los ajustes que pusiste a mano en los lanzadores (`SIDP_MODELO_VISION` y los de Ollama) ya no se pierden: al
volver a correr `instalar_servicios.ps1` se pasan solos a `C:\SIDP-datos\servicios\ajustes.ps1`, que el script ya
nunca sobrescribe. Desde ahora los ajustes se cambian **en ese archivo**.

**No se borra nada en esta tarea.** Todo lo que se genera queda en `C:\SIDP-datos\manuscritos` (fuera del
repositorio). Al repositorio solo sube el informe con números: nada de nombres, CURP, clave, contraseñas ni IP.
Los `detalle_local*.csv` traen lo que se leyó de cada hoja: **no se suben**.

1. Actualiza la rama:
   ```
   git pull origin claude/project-thread-vp6ab8
   ```
2. Reinicia los servicios con el código nuevo. En **PowerShell como administrador**, en la carpeta del repositorio:
   ```
   powershell -ExecutionPolicy Bypass -File cerebro\pc4\instalar_servicios.ps1
   ```
   Debe decir `Ajustes guardados en C:\SIDP-datos\servicios\ajustes.ps1 (N tomados de los lanzadores anteriores)`.
   Espera un minuto y revisa (PowerShell normal):
   ```
   powershell -ExecutionPolicy Bypass -File cerebro\pc4\estado_servicios.ps1
   ```
   Debe decir que el cerebro responde y mostrar la línea `Ajustes (...)` con `SIDP_MODELO_VISION = 'qwen2.5vl:3b'`.
   Si no aparece, abre `C:\SIDP-datos\servicios\ajustes.ps1` con el Bloc de notas, agrega esa línea
   (`$env:SIDP_MODELO_VISION = 'qwen2.5vl:3b'`) y vuelve a correr `instalar_servicios.ps1`. Al arrancar, el cerebro
   pone solo la base al día (tablas nuevas para los datos de cada campo; no borra nada).
3. Instala lo que falta para leer PDF hoja por hoja:
   ```
   python -m pip install -r validacion/requisitos.txt
   ```
4. Genera 24 hojas inventadas "a mano" (12 fichas de inscripción y 12 certificados médicos, con letra clara y fea,
   como foto de celular o escaneo):
   ```
   python -m validacion.ejemplo.manuscritos C:\SIDP-datos\manuscritos --cuantas 12
   ```
5. Mide sin el modelo que ve (rápido, para comparar):
   ```
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --sin-vision --etiqueta sin_vision
   ```
6. Mide como trabajará el taller (qwen2.5vl:3b, dos lecturas, 1280 px) con las 24 hojas. **Tarda** (calculo de 1 a
   3 minutos por hoja); no cierres la ventana. Cada renglón dice cuántos campos salieron bien en esa hoja y en
   cuántos segundos.
   ```
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen2.5vl:3b --etiqueta taller
   ```
7. Comparaciones con las primeras 6 hojas, para escoger el mejor ajuste. Hazlas en este orden; si se hace tarde,
   lo que falte queda para después (dilo en el informe):
   ```
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen2.5vl:3b --hojas 6 --etiqueta base6
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen2.5vl:3b --hojas 6 --lecturas 1 --etiqueta una_lectura
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen2.5vl:3b --hojas 6 --lado 960 --etiqueta lado960
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen2.5vl:3b --hojas 6 --lado 1600 --etiqueta lado1600
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen3-vl:8b --hojas 6 --lecturas 1 --etiqueta qwen3_8b
   ```
   El último prueba si qwen3-vl, ya sin "pensar", lee la letra fea bastante mejor como para valer lo que tarda.
8. Opcional, con Maximiliano (la prueba de verdad, con letra de personas):
   ```
   python -m validacion.ejemplo.manuscritos C:\SIDP-datos\manuscritos_reales --en-blanco
   ```
   Imprime `ficha_en_blanco.pdf` unas 5 veces y que distintas personas la llenen con **datos inventados** (con
   letra fea incluida). Tómales foto con el celular y pon las fotos en `C:\SIDP-datos\manuscritos_reales` como
   `01_ficha_inscripcion.jpg`, `02_ficha_inscripcion.jpg`... Escribe ahí `respuestas.csv` con lo que dice cada
   ficha, un renglón por campo, con el mismo formato que `C:\SIDP-datos\manuscritos\respuestas.csv` (columnas
   archivo, tipo, clave, valor, letra, variante; tipo = `ficha_inscripcion`; letra = quién la llenó, por ejemplo
   "persona 1"; variante = `foto`). Luego:
   ```
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos_reales --modelo qwen2.5vl:3b --etiqueta reales
   ```
9. Escribe `cerebro\laboratorio\resultados\2026-10-16_tarea013_lectura.md` con: lo que imprimió el paso 2 (sin
   la clave ni la IP), el contenido completo de cada `resumen_lectura_*.md` que salió (cada uno con su etiqueta
   como título) y cualquier error completo. Esos resúmenes solo traen números y nombres de campos; revisa de todos
   modos que no haya nombres de personas, CURP, teléfonos ni IP.
10. Sube solo ese archivo:
    ```
    git add cerebro/laboratorio/resultados/2026-10-16_tarea013_lectura.md
    git commit -m "laboratorio: resultado de la tarea 013"
    git pull --rebase origin claude/project-thread-vp6ab8
    git push origin claude/project-thread-vp6ab8
    ```

## Tarea 013, segunda parte: la letra fea y el modelo grande (2026-10-16)

Gracias: con 6 hojas, `qwen2.5vl:3b` con dos lecturas sacó bien el 99 % y no hubo ningún peligroso. Pero esas 6
hojas eran todas de **letra clara**; la letra fea está en las familias 04, 05, 06, 10, 11 y 12. Falta medirla,
que es lo que más importa. Es para la corrida nocturna, en este orden. No se borra nada.

1. Actualiza la rama (`git pull origin claude/project-thread-vp6ab8`). No hace falta reiniciar servicios.
2. Las 24 hojas como trabaja el taller (la más importante; unos 40 minutos):
   ```
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen2.5vl:3b --etiqueta taller
   ```
3. qwen3-vl:8b con una lectura, en 6 hojas, para saber si vale lo que tarda:
   ```
   python -m validacion.medir_lectura C:\SIDP-datos\manuscritos --modelo qwen3-vl:8b --hojas 6 --lecturas 1 --etiqueta qwen3_8b
   ```
4. Si sobra tiempo: `--hojas 6 --lado 1600 --etiqueta lado1600` con `qwen2.5vl:3b`.
5. Escribe `cerebro\laboratorio\resultados\2026-10-16_tarea013b_lectura.md` con el contenido completo de cada
   `resumen_lectura_*.md` nuevo (sobre todo las tablas "Por letra" y "Por campo"). Solo números; revisa que no
   haya nombres, CURP, teléfonos ni IP. Súbelo solo a él:
   ```
   git add cerebro/laboratorio/resultados/2026-10-16_tarea013b_lectura.md
   git commit -m "laboratorio: resultado de la tarea 013, segunda parte"
   git pull --rebase origin claude/project-thread-vp6ab8
   git push origin claude/project-thread-vp6ab8
   ```

## Tarea 014: corta (2026-10-16)

Maximiliano probó el modelo optimizado y lo aceptó: se queda como lo dejaste (960 px, una lectura). La Tarea 013,
segunda parte, **ya no se hace**.

1. Regla: no cambies archivos fuera de `cerebro/laboratorio/resultados/`. Si quieres proponer un cambio de código,
   déjalo como `.patch` en `resultados/` y dilo en el informe; Claude lo revisa y lo sube.
2. Actualiza la rama y revisa los servicios. No hace falta reiniciar nada: lo nuevo (el Excel por grado) va dentro
   del SIDP.exe del servidor, no en la PC 4. No se borra nada.
   ```
   git pull origin claude/project-thread-vp6ab8
   powershell -ExecutionPolicy Bypass -File cerebro\pc4\estado_servicios.ps1
   ```
3. Escribe `cerebro\laboratorio\resultados\2026-10-16_tarea014.md` con la salida del paso 2 (sin IP ni claves) y súbelo
   solo a él, como siempre (`git add` de ese archivo, `commit`, `pull --rebase`, `push`).
