# Informe Integral de Sesión - PC 4 (Laboratorio Cerebro) para el Agente Claude

- **Fecha de actualización:** 2026-10-16
- **Equipo:** PC 4 (`DESKTOP-8RJIA6B`)
- **Procesador / APU:** AMD Ryzen 5 5600G with Radeon Graphics (6 núcleos / 12 hilos)
- **Memoria RAM:** 24 GB
- **Almacenamiento:** Disco mecánico WDC WD1600 (160 GB)
- **Sistema Operativo:** Windows 11 Enterprise (10.0.22000)
- **Python:** 3.15.0a8 (`C:\Python315\python.exe`)
- **Rama:** `claude/project-thread-vp6ab8`
- **Operador local:** Maximiliano Cabello Mata

---

## 1. Resumen Cronológico de Tareas Realizadas en PC 4 (Tareas 001 a 012)

Durante las sesiones de trabajo en el hardware real de la PC 4 se ejecutaron, diagnosticaron y validaron las siguientes tareas del buzón:

### Tareas 001 a 004: Modelos `sidp-revisor` / `sidp-revisor-2` y Validador de Ejemplo
- Creación y evaluación de `sidp-revisor` y `sidp-revisor-2` en Ollama sobre 11 fichas y 30 pares en zona gris.
- Ajuste de reglas deterministas para dejar en "duda" casos críticos (apellidos faltantes, orden invertido, variaciones de más de una letra) sin consultar al modelo.
- Prueba integral del validador sobre expedientes de ejemplo (`0 de 6` falsos negativos peligrosos).

### Tarea 005: Entorno de validación y servicio cerebro por red
- Instalación de Tesseract OCR 5.5 con soporte de idioma español (`spa.traineddata`) y herramientas de visión (`pypdf`, `pypdfium2`, `opencv-python-headless`, `zxing-cpp`).
- Configuración de la red local como **Privada** y habilitación de la regla de firewall `SIDP Cerebro 8771` (Inbound TCP 8771).
- Puesta en marcha del servidor HTTP del cerebro (`validacion.cerebro_red`) con `sidp-revisor-2`.

### Tarea 006: Nuevo lector de documentos y fotos
- Medición de rendimiento y precisión del lector con transformaciones geométricas (recorte de bordes, corrección de perspectiva, sombras, rotación y lectura de QR / franja MRZ `<<<` de INE) sobre 49 fotos sintéticas.
- Nota de compatibilidad documentada: `PaddleOCR` / `paddlepaddle` aún no publica ruedas precompiladas para Python 3.15 (`cp315`), por lo que el lector opera de forma estable sobre `Tesseract 5.5` + `OpenCV` + `zxing-cpp`.

### Tarea 007: Escaneo del día de pruebas (`/leer`)
- Verificación del endpoint `/leer` para recibir expedientes completos escaneados directamente desde `SIDP-Validador.exe` sin almacenar archivos temporales permanentes en disco.

### Tarea 008: Base de datos PostgreSQL 17.11 para el cerebro
- Descarga e instalación desatendida de **PostgreSQL 17.11** (`postgresql-x64-17`) en Windows.
- Restricción estricta de escucha en `127.0.0.1:5432` y `[::1]:5432` (`localhost`), garantizando que ningún equipo externo en la red pueda conectarse directamente al puerto de PostgreSQL.
- Desactivación de reglas públicas de firewall para PostgreSQL.
- Creación segura del rol `sidp` y la base de datos `sidp_cerebro`, con credenciales resguardadas exclusivamente en `%USERPROFILE%\.sidp\` (fuera del repositorio).

### Tarea 009: Esquema v2 y carga del padrón oficial de la SEP
- Migración al esquema relacional v2 de `sidp` con tablas para alumnos, grupos, tutores, inscripciones, documentos, revisiones, lecturas y bitácora de auditoría.
- Carga de los **191 alumnos** oficiales desde `C:\SIDP-datos\lista_oficial.pdf` en sus 6 grupos y comprobación de idempotencia ante recargas.

### Tarea 010: Reconstrucción limpia de la base con el parser mejorado
- Vaciado total de la base mediante `python -m validacion.base_cerebro borrar --si-borrar-todo` y recarga limpia desde `C:\SIDP-datos\lista_oficial.pdf` con separación mejorada de nombres y soporte de `Ñ`.
- Disminución de renglones dudosos a `0` en cinco de los seis grupos (solo `1` en 1° A).
- Verificación del endpoint `/alumnos` entregando los 6 grupos completos a `SIDP-Validador.exe`.

### Tarea 011: Respaldo previo, pandas, inventario de bienes, limpieza y `/respaldo`
- Instalación de `pandas 3.0.6`.
- Generación de respaldo completo previo a cambios mediante `pg_dump` en `C:\SIDP-datos\respaldos\sidp_cerebro_20261015_180723.dump` (`0.11 MB`).
- Actualización del esquema con las tablas de inventario escolar y mantenimiento de base (`VACUUM ANALYZE` + `REINDEX`, tamaño en disco `10.4 MB`).
- Ejecución de `python -m validacion.base_cerebro analisis` con cruce estadístico en pandas.
- Limpieza autorizada exclusivamente sobre caché de pip (`81.7 MB` liberados) y carpeta temporal `$env:TEMP` (`~452 MB` liberados), liberando más de **533 MB** sin tocar `C:\SIDP-datos`, PostgreSQL ni modelos de Ollama.
- Creación de `C:\SIDP-datos\respaldo` y verificación de los endpoints `/analisis`, `/inventario` y `/respaldo`.

### Tarea 012: Arranque autónomo sin ventanas (`SIDP-Ollama` y `SIDP-Cerebro`) y modelo de visión
- Ejecución de `cerebro\pc4\instalar_servicios.ps1` con privilegios de Administrador para registrar las tareas programadas de Windows (`SIDP-Ollama` y `SIDP-Cerebro`) mediante arranque `S4U` al encender la PC sin necesidad de iniciar sesión ni dejar ventanas abiertas.
- Configuración de `postgresql-x64-17` en arranque automático y desactivación de suspensión, hibernación e inicio rápido de energía.
- Descarga y evaluación de `qwen3-vl:8b` (`6.1 GB`) y `qwen2.5vl:3b` (`3.2 GB`).
- Diagnóstico profundo de tiempos de inferencia visual en el APU Ryzen 5 5600G + HDD mecánico:
  - **Causa de lentitud en `qwen3-vl:8b` (~531 s en frío):** lectura de 6.1 GB desde disco mecánico + warmup (`169.1 s`), resolución mínima forzada de 1 MP (~1,950 tokens visuales, `49.4 s` de prompt eval) y activación por defecto del modo *thinking* en Ollama (`1,171` tokens de pensamiento interno antes de responder). Desactivando `think: False`, el tiempo de `qwen3-vl:8b` en caliente baja a `~105 s`.
  - **Optimización con `qwen2.5vl:3b`:** modelo nativo sin sobrecarga de pensamiento interno (`eval time` de solo `3.9 s` a `5.4 s` a `11.9 - 14.0 tokens/s`). Con `LADO=1600` promedió **108.4 s** en las primeras 3 hojas de `C:\SIDP-datos\fotos_inventadas` (`acta_alumno.jpg`: `108.3 s`, `boleta.jpg`: `108.2 s`, `certificado_medico.jpg`: `108.8 s`), y al reducir `lado=960` bajó a **35.7 - 39.1 s** por hoja.
- Configuración de `SIDP_MODELO_VISION=qwen2.5vl:3b`, `OLLAMA_KEEP_ALIVE=24h`, `OLLAMA_FLASH_ATTENTION=1` y `OLLAMA_IGPU_ENABLE=1`.

---

## 2. Estado Actual de la Base de Datos (`sidp_cerebro`)

La base de datos se encuentra limpia, respaldada, optimizada e íntegra con el padrón del ciclo escolar **2026-2027**:

| Grupo | Alumnos Inscritos | Hombres | Mujeres | Extraedad | Renglones Dudosos al Cargar |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1° A** | 34 | 19 | 15 | 0 | 1 |
| **2° A** | 31 | 15 | 16 | 0 | 0 |
| **3° A** | 33 | 15 | 18 | 0 | 0 |
| **4° A** | 32 | 18 | 14 | 0 | 0 |
| **5° A** | 32 | 14 | 18 | 0 | 0 |
| **6° A** | 29 | 12 | 17 | 0 | 0 |
| **Total** | **191** | **93** | **98** | **0** | **1** |

- **Tamaño en disco de `sidp_cerebro`:** `10.4 MB` (tras `VACUUM ANALYZE` y `REINDEX`).
- **Respaldo disponible en:** `C:\SIDP-datos\respaldos\sidp_cerebro_20261015_180723.dump`.
- **Alertas activas:** `curp_digito: 1` (una CURP del PDF original con dígito verificador distinto al calculado por algoritmo RENAPO) y `renapo_pendiente: 191`.
- **Bitácora de auditoría:** 382 eventos registrados.
- **Inventario escolar:** Esquema inicializado (`0` bienes registrados actualmente).

---

## 3. Estado Actual de Servicios y Modelos en PC 4

1. **PostgreSQL (`postgresql-x64-17`):** `Running` (Automatic), escuchando únicamente en `127.0.0.1:5432` y `[::1]:5432`.
2. **Tarea programada `SIDP-Ollama`:** `Running`, escuchando en `127.0.0.1:11434`.
   - Modelos instalados en `C:\Users\DELFINO_PANDO_13\.ollama\models`:
     - `qwen2.5vl:3b` (configurado como predeterminado en `SIDP_MODELO_VISION`)
     - `qwen3-vl:8b`
     - `sidp-revisor-2:latest`
     - `sidp-revisor:latest`
     - `llama3.1:latest`
3. **Tarea programada `SIDP-Cerebro`:** `Running`, escuchando en el puerto `8771` y respondiendo en `/salud`, `/alumnos`, `/leer`, `/analisis`, `/inventario` y `/respaldo`.

---

## 4. Protocolo de Seguridad y Privacidad Cumplido

- **Cero filtración de información sensible:** Ningún nombre de alumno, CURP, teléfono, domicilio, contraseña de PostgreSQL, clave del cerebro ni dirección IP local fue incluido en este informe ni en ningún archivo del repositorio.
- **Archivos protegidos fuera del árbol Git:** `C:\SIDP-datos\lista_oficial.pdf`, `C:\SIDP-datos\respaldos\`, `C:\SIDP-datos\fotos_inventadas\` y `%USERPROFILE%\.sidp\` permanecen estrictamente en el almacenamiento local de la PC 4.
