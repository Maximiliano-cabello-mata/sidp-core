# Registro de sesión — Puesta en marcha de la PC 4 (Cerebro y Validación) — 2026-10-14

Bitácora técnica de la puesta en marcha de la **PC 4** (`DESKTOP-8RJIA6B`) como nodo de validación y servicio de inferencia local ("cerebro") para el sistema SIDP. Se documenta todo el hardware, software y dependencias instaladas, las tareas ejecutadas (Tareas 001, 002, 005 y 006) y el catálogo completo de todos los errores encontrados, sus causas y sus soluciones.

> **Entorno:** PC 4 = Estación de validación y cerebro (`192.168.100.15:8771`, Windows 11 Enterprise). Inferencia ejecutada 100% en CPU con Ollama en `127.0.0.1:11434`. Por seguridad, la clave de acceso del servicio reside en `~/.sidp/clave_cerebro.txt` y nunca se incluye en el repositorio.

---

## 1. Inventario del Equipo y Estado Actual

### 1.1 Hardware Base
| Componente | Especificación Técnica | Notas |
|---|---|---|
| **Equipo** | `DESKTOP-8RJIA6B` (PC 4) | Usuario local: `DELFINO_PANDO_13` |
| **Sistema Operativo** | Windows 11 Enterprise (Compilación 10.0.22000) | 64 bits |
| **CPU** | AMD Ryzen 5 5600G with Radeon Graphics | 6 núcleos / 12 hilos, hasta 3.9 GHz |
| **RAM** | 23.3 GB total | ~15.3 GB libres en reposo; ~10 GB con modelo cargado |
| **GPU** | AMD Radeon Graphics (integrada) | 512 MB VRAM dedicada (sin CUDA; inferencia en CPU) |
| **Disco** | Unidad C: | ~90 GB libres al finalizar |

### 1.2 Software y Herramientas Base Instaladas
| Herramienta | Versión | Ubicación |
|---|---|---|
| **Chocolatey** | v2.7.4 | `C:\ProgramData\chocolatey\bin\choco.exe` |
| **Git for Windows** | v2.56.0.windows.2 | `C:\Program Files\Git\cmd\git.exe` |
| **Python** | 3.15.0 | `C:\Python315\python.exe` |
| **Tesseract OCR** | 5.5.3 (UB-Mannheim) | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| **Ollama** | 0.40.4 | `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` |

### 1.3 Bibliotecas Python Instaladas (Entorno de Usuario)
- `numpy` (2.5.4)
- `opencv-python-headless` (5.0.0.93)
- `pypdf` (6.20.1)
- `pypdfium2` (5.14.0)
- `pillow` (12.3.0)
- `zxing-cpp` (3.1.1)

### 1.4 Modelos Locales en Ollama
- `llama3.1:latest` (4.9 GB, base original GGUF Q4)
- `sidp-revisor:latest` (4.9 GB, creado en Tarea 001)
- `sidp-revisor-2:latest` (4.9 GB, creado en Tarea 002 con ejemplos sintácticos mexicanos)

### 1.5 Configuración de Red y Seguridad
- **Red:** Adaptador `Ethernet` configurado en categoría **Privada** (`Set-NetConnectionProfile -NetworkCategory Private`).
- **Firewall:** Regla de entrada `SIDP Cerebro 8771` activa en perfil Privado para puerto TCP 8771.
- **Energía:** `powercfg /change standby-timeout-ac 0` aplicado para evitar suspensión del equipo.
- **Servicio Cerebro:** Demonio HTTP en [validacion/iniciar_cerebro.bat](file:///C:/Users/DELFINO_PANDO_13/.gemini/antigravity/scratch/sidp-core/validacion/iniciar_cerebro.bat) (puerto 8771).

---

## 2. Catálogo de Errores Encontrados, Causas y Soluciones

A lo largo de la sesión se identificaron y resolvieron 15 incidencias técnicas:

| # | Error / Síntoma | Causa raíz | Solución aplicada |
|---|---|---|---|
| **1** | Subproceso de diagnóstico WMI/CIM congelado sin responder | Consulta simultánea pesada de múltiples clases CIM en PowerShell | Se canceló el subproceso y se consultó cada clase de hardware por separado |
| **2** | `ollama : CommandNotFoundException` | Ollama no estaba en la variable `PATH` de la consola | Se usó la ruta absoluta del binario y llamadas directas a su API REST local (`127.0.0.1:11434`) |
| **3** | `git : CommandNotFoundException` | Git no estaba instalado en el equipo | Se autorizó e instaló Git for Windows con Chocolatey |
| **4** | `python : CommandNotFoundException` | Python no estaba instalado en el equipo | Se autorizó e instaló Python 3.15 con Chocolatey |
| **5** | `winget : CommandNotFoundException` | `winget.exe` ausente o deshabilitado en Windows 11 Enterprise | Se utilizó Chocolatey (`choco`) como gestor de paquetes alternativo |
| **6** | `Get-Counter : El objeto especificado no se encontró en el equipo` | Contadores de rendimiento de CPU dañados o deshabilitados en el SO | Se documentó la incidencia y se evaluó el uso de CPU mediante pruebas de carga y memoria |
| **7** | `NativeCommandError` en PowerShell con `git` y `ollama` | PowerShell trata cualquier salida en `stderr` de ejecutables como error nativo | Se canalizaron los flujos de salida con `2>&1 \| Out-String` |
| **8** | Rechazo de commit por falta de identidad en Git | Repositorio recién clonado sin `user.name` ni `user.email` | Se configuraron localmente los datos de Maximiliano Cabello Mata para este repositorio |
| **9** | `git push` congelado por solicitud oculta de credenciales | Git Credential Manager abría diálogo fuera del alcance del proceso automatizado | Maximiliano realizó la autenticación interactiva directamente en la consola |
| **10** | `Start-Process -Verb RunAs` falló con `Solicitud no compatible` | Procesos en sesiones no interactivas no pueden invocar diálogos UAC interactivos | Se ejecutaron los comandos administrativos desde una ventana elevada abierta por el usuario |
| **11** | `PermissionDenied` en `Set-NetConnectionProfile` y Firewall | Falta de privilegios de Administrador en el prompt inicial del agente | Se ejecutó desde la ventana de PowerShell como Administrador (`system32`) |
| **12** | Chocolatey bloqueado por archivo `.lock` residual | Interrupción de proceso previo no elevado dejó un lock en `ProgramData\chocolatey\lib` | Se eliminó manualmente el archivo de bloqueo y se reintentó la instalación |
| **13** | `DirectoryNotFoundException` al descargar datos de Tesseract | Se intentó descargar `spa.traineddata` antes de instalar el motor base | Se instaló primero el paquete base con `choco install tesseract -y` |
| **14** | `cmd /c python` invoca el alias vacío de `WindowsApps` | El explorador de Windows no refrescó el PATH tras instalar Python y priorizaba el alias de la tienda | Se antepuso permanentemente `C:\Python315` y `C:\Python315\Scripts` al inicio del `PATH` del usuario |
| **15** | `Could not find a version that satisfies paddlepaddle>=3.0` | PyPI no cuenta con binarios precompilados de PaddlePaddle para Python 3.15 | El sistema conmutó automáticamente a Tesseract OCR (con español y detector de giro), cumpliendo el 100% de las pruebas |

---

## 3. Resumen Cronológico de Tareas Ejecutadas

### 3.1 Diagnóstico Inicial y Prueba de Inferencia Directa
- Se evaluó el hardware: 6 núcleos Ryzen 5, 23.3 GB RAM, sin GPU dedicada.
- Se probaron 7 fichas ficticias completas directamente con `llama3.1:latest`.
- **Conclusión:** El modelo alucinó inconsistencias inexistentes (falsos positivos en 3 de 3 fichas válidas). Se confirmó la necesidad del enfoque SIDP: reglas deterministas fijas y modelo acotado solo a la "zona gris".

### 3.2 Tarea 001: Reglas Base y Modelo en Zona Gris
- Se clonó `sidp-core` en la rama `claude/project-thread-vp6ab8`.
- Se creó el modelo `sidp-revisor` con [Modelfile](file:///C:/Users/DELFINO_PANDO_13/.gemini/antigravity/scratch/sidp-core/cerebro/laboratorio/Modelfile).
- Reglas fijas: **11 de 11 fichas correctas**.
- Opiniones en zona gris: 9 de 12 acertadas, **0 peligrosas**.
- Se subió informe [2026-10-14_1714.md](file:///C:/Users/DELFINO_PANDO_13/.gemini/antigravity/scratch/sidp-core/cerebro/laboratorio/resultados/2026-10-14_1714.md) (Commit `d0f2288`).

### 3.3 Tarea 002: Zona Gris Ampliada (18 Pares) y Modelo Contextual
- Se creó `sidp-revisor-2` con [Modelfile.2](file:///C:/Users/DELFINO_PANDO_13/.gemini/antigravity/scratch/sidp-core/cerebro/laboratorio/Modelfile.2) (ejemplos mexicanos).
- `sidp-revisor`: 27 aciertos de 54.
- `sidp-revisor-2`: **42 aciertos de 54**.
- Se subieron informes comparativos (Commit `33fa9ad`).

### 3.4 Tarea 005: PC 4 como Nodo Cerebro por Red
- Se instalaron `pypdf`, `opencv-python-headless` y `Tesseract OCR` con idioma español.
- Se configuró la red a Privada y se abrió el puerto 8771 en el Firewall.
- Se ejecutó la prueba de validación oficial sobre 10 expedientes:
  - Falsos detectados: **6 de 6 (100 %)**.
  - Falsos pasados como listos: **0 de 6 (0 %)**.
  - Verdaderos listos para autorizar: **3 de 4 (75 %)**.
- Se subió informe [2026-10-15_entorno_pc4.md](file:///C:/Users/DELFINO_PANDO_13/.gemini/antigravity/scratch/sidp-core/cerebro/laboratorio/resultados/2026-10-15_entorno_pc4.md) (Commit `41f5733`).

### 3.5 Tarea 006: Mejor Lectura de Fotos, Escaneos y Giro
- Se instalaron `pypdfium2`, `pillow` y `zxing-cpp`.
- Se generaron 49 fotos sintéticas de celular con perspectiva y sombra en `$env:USERPROFILE\SIDP-fotos`.
- Medición con Tesseract: 34.1 s (3.4 s/expediente), detectando **6 de 6 falsos (100%)** y **0 falsos colados (0%)**.
- Se reinició el cerebro y se verificó que `/salud` expone todas las herramientas nuevas.
- Se subió informe [2026-10-15_lectura_pc4.md](file:///C:/Users/DELFINO_PANDO_13/.gemini/antigravity/scratch/sidp-core/cerebro/laboratorio/resultados/2026-10-15_lectura_pc4.md) (Commit `844e9d8`).

---

## 4. Estado Final del Sistema

- **Servicio activo:** `http://192.168.100.15:8771` (arrancado desde [iniciar_cerebro.bat](file:///C:/Users/DELFINO_PANDO_13/.gemini/antigravity/scratch/sidp-core/validacion/iniciar_cerebro.bat)).
- **Herramientas activas:** `pypdf: true`, `pypdfium2: true`, `opencv: true`, `zxing: true`, `tesseract: true`, `tesseract_espanol: true`, `tesseract_giro: true`.
- **Clave local para `SIDP-Validador.exe`:** `9ef2cae7cb8ce61c` (almacenada en `~/.sidp/clave_cerebro.txt`).
