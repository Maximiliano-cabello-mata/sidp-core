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
El panel tiene una barra azul a la izquierda con pestañas, en el orden en que se trabaja.
**Inicio** dice qué falta y lleva a la pestaña que toca.

3. **Ajustes.** En **Cerebro de la PC 4** escribe la dirección (`http://192.168.1.40:8771`) y la
   clave que muestra la ventana del cerebro. Da **Conectar**: debe decir **Conectado**. Ahí mismo
   aparece la dirección para los padres, por ejemplo `http://192.168.1.30:8770/padres`. Se abre
   desde un celular conectado al mismo Wi-Fi.
4. **1 · Listas de grupo** (primero que todo). Da **Subir la lista de un grupo**, suelta la lista
   escaneada (o escribe los nombres, uno por renglón) y da **Leer la lista**. El sistema separa
   apellidos y nombres y encuentra el grado y el grupo. Revisa la tabla (lo dudoso sale en amarillo),
   corrige y da **Guardar lista**. Los grupos quedan por grado; al abrir uno se ven sus alumnos, quién
   ya tiene expediente y quién no. Guardar la misma lista otra vez no repite a nadie.
5. **2 · Escanear expediente** (validación manual, para lo que la escuela ya revisó en papel).
   1. Elige el grupo y el alumno (o desde la lista del grupo da **Escanear** en su renglón).
   2. Suelta los escaneos del alumno: todo en un PDF o en varios.
   3. El sistema reconoce cada hoja y llena los datos. En **¿De qué alumno es?** confirma el alumno
      de la lista: si el nombre del acta no se parece al que elegiste, te avisa. Si no está en las
      listas, marca "alumno nuevo" y elige su grupo.
   4. Revisa, corrige y da **Guardar expediente**. El alumno de la lista recibe la CURP, la fecha y
      el sexo (no se crea otro), y el sistema te pone al siguiente alumno del grupo.

   Para leer escaneos (PDF que son solo imagen) se necesita el cerebro **conectado** (paso 3), con
   el código actualizado (Parte 1, pasos 1 y 5). Sin cerebro, esta PC solo lee los PDF que traen
   texto, y el panel lo avisa.
6. **3 · Fila de revisión** (validación automática, lo que suben los padres). Da **Revisar todo**.
   La lista sale dividida por grupo; arriba se filtra por grupo y por estado ("Por decidir" de
   inicio). Tú autorizas o rechazas; al rechazar, el panel muestra el reporte que recibiría el
   padre. El tutor queda vinculado al alumno **solo cuando autorizas**. Si el padre escribió el
   nombre igual que en la lista, el expediente cae solo en su grupo; si no, el expediente dice
   "no está en ninguna lista" y propone al alumno parecido: da clic en **Es ...** o elige su grupo.
7. **4 · CURP y RENAPO.** Da **Copiar CURP y abrir RENAPO**, pega la CURP en la página oficial
   (Ctrl + V), resuelve el captcha, descarga el PDF y suéltalo en esa pestaña. El sistema encuentra
   al alumno por la CURP, compara el nombre y la marca **Validada en RENAPO**; la constancia se
   guarda en `SIDP-prueba\renapo\`. Si RENAPO no la encuentra, da **RENAPO no la encontró**.
8. **Análisis, 911 y SAID.** Matrícula por grado y sexo, lo que falta por alumno (CURP, sexo,
   fecha, documentos) y descargas para Excel: la lista de alumnos (una hoja por grupo) y la
   matrícula por grado. Se guardan en Descargas; tienen datos personales.
9. **Plantillas.** Da **Agregar un documento**. Escribe su nombre, elige si es del alumno o del
   tutor y suelta una muestra (el formato en blanco, o dos llenos de personas distintas). El sistema
   propone sus textos fijos: quita los que tengan datos de alguien, elige qué más se revisa y da
   **Guardar plantilla**. La página de padres lo pide desde ese momento, el escaneo lo reconoce y la
   revisión lo valida. A los documentos del sistema (por ejemplo, el comprobante) se les pueden
   agregar textos con **Abrir**.

Los archivos se pueden soltar en cualquier parte de la pestaña abierta: van a lo que toca ahí
(lista, escaneo, constancia o muestra).

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
