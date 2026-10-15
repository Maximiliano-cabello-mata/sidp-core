# Entorno de pruebas de validación (PC 4 y PC del administrador)

Esto es un **entorno de pruebas**, no la escuela en producción. Sirve para medir qué tan bien se
validan los documentos de inscripción, qué datos se extraen y cómo queda el expediente del alumno.

## Cómo se acomoda

```
 Padres (celular o PC, mismo Wi-Fi)
        │  suben captura + fotos o PDF
        ▼
 PC del administrador ── SIDP-Validador.exe (puerto 8770)
   · guarda los archivos y la base de datos (39 tablas)       ◄── almacenamiento
   · muestra el panel: el administrador autoriza o rechaza
        │  manda cada expediente por IP, con clave
        ▼
 PC 4 ── cerebro (puerto 8771): procesos + llama3.1 (Ollama)   ◄── validación y análisis
   · lee QR, texto del PDF y fotos (OCR), cruza datos
   · llama solo opina "si/no/duda" en la zona gris
   · no se queda con nada: trabaja en una carpeta temporal y la borra
```

- La **PC 4** valida y es el cerebro. No guarda documentos.
- La **PC del administrador** guarda todo: los archivos en `C:\Users\<usuario>\SIDP-prueba\expedientes\`
  y los datos extraídos en `plataforma_prueba.db`.
- Si la PC 4 está apagada, el .exe corre los procesos solo (sin llama) y lo dice en cada expediente.
- La comunicación es **directa por IP**, sin Antigravity ni internet.
- Antigravity solo prepara la PC 4 y arranca el cerebro. No participa en la validación.

## Reglas que no cambian

1. La **clave del cerebro** nunca va al repositorio, a un informe ni a un mensaje público. El
   repositorio es público. La clave vive en `C:\Users\<usuario>\.sidp\clave_cerebro.txt` y solo la
   copia Maximiliano al .exe.
2. Los **documentos reales** (fotos, PDF, capturas) nunca van al repositorio ni a la nube. Solo se
   usan con permiso de sus dueños. Al repositorio solo suben números.
3. Ollama se queda en `127.0.0.1:11434`. Lo único que se abre a la red es el puerto **8771** del
   cerebro, y solo en red **Privada**.

---

## Parte 1. PC 4 (la hace el agente Antigravity)

Todo en **PowerShell como administrador**, dentro de la carpeta del repositorio `sidp-core`.

### 1. Actualizar el código

```powershell
git checkout claude/project-thread-vp6ab8
git pull
```

### 2. Instalar lo que necesita la validación

```powershell
python -m pip install -r validacion/requisitos.txt
python -m pip install -r validacion/requisitos_paddle.txt
winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
```

- `requisitos.txt`: PDF (pypdf, pypdfium2), fotos (opencv, Pillow) y códigos QR y de barras (zxing-cpp).
- `requisitos_paddle.txt`: PaddleOCR, el lector principal de fotos. Es pesado y la primera vez baja sus
  modelos (unos 100 MB). Si no se puede instalar, todo sigue funcionando con Tesseract.
- Tesseract es el respaldo y el que decide si una foto viene de lado.

El instalador de Tesseract solo trae inglés. Agrega el español:

```powershell
Invoke-WebRequest https://github.com/tesseract-ocr/tessdata_fast/raw/main/spa.traineddata `
  -OutFile "C:\Program Files\Tesseract-OCR\tessdata\spa.traineddata"
```

Comprueba. Todas deben decir `true` (PaddleOCR puede tardar la primera vez):

```powershell
python -m validacion.lector
```

Para ver qué lee de un documento: `python -m validacion.lector C:\ruta\foto.jpg` (se queda en la pantalla).

### 3. Revisar que el modelo esté listo

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags | Select-Object -ExpandProperty models | Select-Object name
```

Debe aparecer `sidp-revisor-2:latest`. Si no aparece, créalo (Ollama no está en el PATH):

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" create sidp-revisor-2 -f cerebro\laboratorio\Modelfile.2
```

### 4. Preparar la red

a) La red debe ser **Privada**:

```powershell
Get-NetConnectionProfile
```

Si `NetworkCategory` dice `Public`, cámbiala (usa el `InterfaceAlias` que salió, por ejemplo `Wi-Fi`):

```powershell
Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private
```

b) Abre el puerto del cerebro en el firewall, solo en red Privada:

```powershell
New-NetFirewallRule -DisplayName "SIDP Cerebro 8771" -Direction Inbound -Protocol TCP -LocalPort 8771 -Action Allow -Profile Private
```

c) Que la PC no se duerma mientras esté conectada a la corriente:

```powershell
powercfg /change standby-timeout-ac 0
```

d) Anota la IP de la PC 4: en `ipconfig`, la "Dirección IPv4" del adaptador Wi-Fi o Ethernet
(por ejemplo `192.168.1.40`). Recomendación para Maximiliano: en el módem, reservar esa IP
para la PC 4 ("reserva DHCP"), así no cambia al reiniciar.

### 5. Arrancar el cerebro

Doble clic en `validacion\iniciar_cerebro.bat`, o:

```powershell
python -m validacion.cerebro_red
```

La ventana muestra dos líneas:

```
Cerebro escuchando en http://192.168.1.40:8771  (modelo sidp-revisor-2)
Clave para SIDP-Validador.exe: ....
```

La ventana se queda abierta mientras dure la prueba. La primera vez crea la clave y la guarda en
`C:\Users\<usuario>\.sidp\clave_cerebro.txt`; las siguientes veces usa la misma.

**La dirección y la clave se le dan solo a Maximiliano**, en la pantalla de la PC 4. No se
escriben en ningún archivo del repositorio ni en el informe.

### 6. Probar que responde

En otra ventana de PowerShell:

```powershell
$clave = Get-Content "$env:USERPROFILE\.sidp\clave_cerebro.txt"
Invoke-RestMethod http://127.0.0.1:8771/salud -Headers @{ 'X-SIDP-Clave' = $clave }
```

Debe decir `ok: True`, el modelo y las herramientas. Con una clave equivocada responde 401: así
debe ser.

Para probarlo desde la PC del administrador (cuando ya tenga la IP):

```powershell
Test-NetConnection 192.168.1.40 -Port 8771
```

`TcpTestSucceeded : True` significa que el firewall y la red están bien.

### 7. (Opcional) Que arranque solo al iniciar sesión

```powershell
schtasks /create /tn "SIDP Cerebro" /tr "\"$PWD\validacion\iniciar_cerebro.bat\"" /sc onlogon /rl highest
```

---

## Parte 2. PC del administrador (Maximiliano)

1. Descarga `SIDP-Validador.exe`. En GitHub ve a **Actions**, abre la última ejecución verde de
   la rama `claude/project-thread-vp6ab8` y baja el artefacto `sidp-windows`. Descomprímelo en
   una carpeta, por ejemplo `C:\SIDP`.
2. Doble clic en `SIDP-Validador.exe`.
   - Si Windows dice "Windows protegió su PC": **Más información** y luego **Ejecutar de todas formas**.
   - Si el firewall pregunta: marca **Redes privadas** y da **Permitir**. Sin esto los padres no llegan.
   - Se abre el navegador con el panel. La ventana negra se queda abierta mientras dure la prueba.
3. En el panel, en **Cerebro de la PC 4**, escribe la dirección (`http://192.168.1.40:8771`) y la
   clave que muestra la ventana del cerebro. Da **Conectar**. Debe decir **Conectado**.
4. Abajo de ese cuadro aparece la dirección para los padres, por ejemplo
   `http://192.168.1.30:8770/padres`. Ábrela desde un celular conectado al mismo Wi-Fi. Ahí se
   capturan los datos y se toman las fotos o se suben los PDF.
5. Cada envío aparece en el panel con su resultado. Tú autorizas o rechazas; al rechazar, el panel
   muestra el reporte que recibiría el padre.
6. **CURP ante RENAPO.** En el cuadro "CURP: validar en RENAPO" aparece cada alumno con su CURP
   "Sin validar". Da **Copiar CURP y abrir RENAPO**, pega la CURP en la página oficial (Ctrl + V),
   resuelve el captcha, descarga el PDF y arrástralo a cualquier parte del panel. El sistema
   encuentra al alumno por la CURP, compara el nombre y la marca **Validada en RENAPO**; la
   constancia se guarda en `SIDP-prueba\renapo\`. Si el nombre no coincide, queda "Revisar: no
   coincide" con lo que falta. Si RENAPO no la encuentra, da **RENAPO no la encontró**.
7. El tutor queda vinculado al alumno (principal y puede recoger) **solo cuando autorizas** su
   expediente.
8. **Escanear expedientes que ya revisaron en papel.** Para los alumnos que ya tienen su carpeta
   revisada por la escuela no hace falta la validación completa:
   1. Escanea los documentos de **un alumno**: todo en un PDF o en varios, como salgan del escáner.
   2. Arrástralos al cuadro **Escanear expediente (ya revisado en papel)**.
   3. El sistema separa las hojas, reconoce cada documento (acta, INE, comprobante, certificado,
      boleta, constancia de la CURP) y llena los datos del alumno y del tutor: nombre, CURP, fecha
      de nacimiento, sexo y parentesco. Lo que no alcanzó a leer aparece en un aviso amarillo.
   4. Revisa, corrige lo que haga falta y da **Guardar expediente**. Queda como "Escaneado
      (validado en papel)", con sus PDF en `SIDP-prueba\expedientes\` y los datos en la base.
      "Revisar todo" ya no lo vuelve a revisar. La CURP sigue apareciendo "Sin validar" en RENAPO
      hasta que alguien haga el paso 6.

   Para leer escaneos (PDF que son solo imagen) se necesita el cerebro **conectado** (paso 3), con
   el código actualizado (Parte 1, pasos 1 y 5). Sin cerebro, esta PC solo lee los PDF que traen
   texto, y el panel lo avisa.
9. **Agregar un documento con plantilla.** Al final del panel, en **Plantillas de documentos**, da
   **Agregar un documento**. Escribe su nombre, elige si es del alumno o del tutor y suelta una muestra (el
   formato en blanco, o dos llenos de personas distintas). El sistema propone sus textos fijos: quita los
   que tengan datos de alguien, elige qué más se revisa y da **Guardar plantilla**. La página de padres lo
   pide desde ese momento, el escaneo lo reconoce y la revisión lo valida. A los documentos del sistema
   (por ejemplo, el comprobante) se les pueden agregar textos con **Abrir**.

Si el celular no abre la página, revisa que la red de esta PC también sea **Privada** (paso 4a de
la Parte 1) y que la regla del firewall exista:

```powershell
New-NetFirewallRule -DisplayName "SIDP Validador 8770" -Direction Inbound -Protocol TCP -LocalPort 8770 -Action Allow -Profile Private
```

---

## Parte 3. Análisis del cerebro sobre lo guardado

Cuando ya haya expedientes revisados, en la PC 4:

```powershell
python -m validacion.analisis --exe http://192.168.1.30:8770
```

La PC 4 lee del .exe, con su clave, lo que se extrajo y lo que decidió la persona (sin archivos).
Cuenta qué reglas se activan, qué documentos no se pudieron leer y en cuántos casos la persona
coincidió con el sistema. El informe se guarda en la PC del administrador, en
`SIDP-prueba\analisis\`. No lleva nombres ni CURP; aun así, antes de subirlo al repositorio
Maximiliano lo revisa.

---

## Y GitHub Pages

La página pública es `https://maximiliano-cabello-mata.github.io/sidp-core/`.
Para publicarla (una vez): Settings > Pages > Source: **GitHub Actions**, y luego Actions >
"Página de demostración" > **Run workflow** sobre `main`. Cada cambio a la página se publica igual, a mano.

- Es una **demostración**: corre en el navegador el mismo código de validación, con 10 expedientes
  inventados. También deja subir PDF y los revisa ahí mismo; no los manda a ningún lado.
- Una página pública de internet **no puede mandar archivos a las PCs de la escuela**: el
  navegador lo bloquea (de una página `https` de internet a una dirección local `http`) y las PCs
  no tienen dirección pública. Por eso los envíos reales de la prueba entran por la página de
  padres del .exe, dentro del Wi-Fi.
- Para que los padres empiecen en GitHub Pages: la página de padres pública tiene el cuadro
  "¿Estás en la red de la escuela?". Escriben la dirección del .exe y los lleva a la página real.
  El panel muestra ese enlace ya armado (`.../padres.html?escuela=192.168.1.30:8770`), listo para
  mandarlo por WhatsApp o ponerlo en un QR.
- Recibir documentos desde fuera de la escuela es el buzón en la nube (ADR-028) y queda para
  después: falta decidir quién lo paga.
