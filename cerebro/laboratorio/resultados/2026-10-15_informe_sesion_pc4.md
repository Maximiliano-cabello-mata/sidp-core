# Informe Integral de Sesión - PC 4 (Laboratorio Cerebro) para el Agente Claude

- **Fecha:** 2026-10-15
- **Equipo:** PC 4 (`DESKTOP-8RJIA6B`)
- **Sistema Operativo:** Windows 11 Enterprise (10.0.22000)
- **Rama:** `claude/project-thread-vp6ab8`
- **Operador local:** Maximiliano Cabello Mata

---

## 1. Resumen de Actividades Realizadas en PC 4

Durante la sesión del día de hoy en el hardware real (PC 4), se ejecutaron y validaron las siguientes tareas del buzón:

### Tarea 005: Entorno de validación y servicio cerebro
- Instalación de Tesseract OCR 5.5 con soporte de idioma español (`spa.traineddata`) y herramientas de visión (`pypdf`, `pypdfium2`, `opencv-python-headless`, `zxing-cpp`).
- Configuración de la red local como **Privada** y habilitación de la regla de firewall `SIDP Cerebro 8771` (Inbound TCP 8771).
- Puesta en marcha de Ollama con el modelo `sidp-revisor-2`.
- Verificación con expedientes de prueba: 0 % de falsos negativos peligrosos (6 de 6 trampas detectadas).

### Tarea 006: Lector de documentos y fotos
- Medición de rendimiento y precisión del lector con transformaciones geométricas (recorte de bordes, corrección de perspectiva, sombras y rotación de INE/documentos).
- Evaluación comparativa de OCR sobre fotos del padrón de prueba.

### Tarea 007: Escaneo del día de pruebas
- Verificación del endpoint `/leer` para recibir expedientes completos escaneados directamente desde `SIDP-Validador.exe` sin almacenar archivos temporales permanentes en disco.

### Tarea 008: Base de datos PostgreSQL para el cerebro
- Descarga e instalación desatendida de **PostgreSQL 17.11** en Windows.
- Restricción estricta de escucha en `127.0.0.1:5432` y `[::1]:5432` (`localhost`), garantizando que nadie en la red pueda atacar el puerto de la base.
- Desactivación de reglas públicas de firewall para PostgreSQL.
- Creación segura del rol `sidp` y la base de datos `sidp_cerebro`.
- Contraseñas almacenadas exclusivamente en `%USERPROFILE%\.sidp\` (fuera del repositorio).
- Instalación del conector `pg8000` e inicialización del primer esquema.

### Tarea 009: Esquema v2 y carga del padrón oficial de la SEP
- Migración al esquema relacional v2 de `sidp` con tablas para alumnos, grupos, tutores, inscripciones, documentos, revisiones, lecturas y bitácora de auditoría.
- Recepción de la lista oficial de la escuela en `C:\SIDP-datos\lista_oficial.pdf` y carga de los 191 alumnos oficiales en sus 6 grupos.
- Comprobación de idempotencia: el sistema rechaza duplicados si el mismo archivo se vuelve a cargar.

### Tarea 010: Base de la PC 4 desde cero con la lista revisada
- Vaciado total de la base mediante `python -m validacion.base_cerebro borrar --si-borrar-todo`.
- Recarga desde `C:\SIDP-datos\lista_oficial.pdf` utilizando el parser mejorado de extracción (separación inteligente de nombres y tratamiento correcto de la letra `Ñ` y acentos).
- Disminución de renglones dudosos a 0 en casi todos los grupos (solo 1 en 1° A).
- Verificación del nuevo endpoint `/alumnos`, que entrega directamente la estructura de grupos y alumnos hacia `SIDP-Validador.exe`.

---

## 2. Estado Actual de la Base de Datos (`sidp_cerebro`)

La base de datos se encuentra limpia, íntegra y completamente poblada con los datos del ciclo escolar 2026-2027:

### Resumen por Grado y Grupo

| Grupo | Alumnos Inscritos | Hombres | Mujeres | Extraedad | Renglones Dudosos al Cargar |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1° A** | 34 | 19 | 15 | 0 | 1 |
| **2° A** | 31 | 15 | 16 | 0 | 0 |
| **3° A** | 33 | 15 | 18 | 0 | 0 |
| **4° A** | 32 | 18 | 14 | 0 | 0 |
| **5° A** | 32 | 14 | 18 | 0 | 0 |
| **6° A** | 29 | 12 | 17 | 0 | 0 |
| **Total** | **191** | **93** | **98** | **0** | **1** |

### Métricas de Matrícula (Estadística 911 por Edad al 31 de Diciembre)
- **1° Grado:** 6 años: 18 H, 15 M | 7 años: 1 H
- **2° Grado:** 7 años: 14 H, 16 M | 8 años: 1 H
- **3° Grado:** 8 años: 15 H, 18 M
- **4° Grado:** 9 años: 17 H, 14 M | 10 años: 1 H, 14 M
- **5° Grado:** 10 años: 13 H, 18 M | 11 años: 1 H
- **6° Grado:** 11 años: 12 H, 17 M

### Estado de Alertas y Auditoría
- **Alertas activas:**
  - `curp_digito: 1`: Se detectó una CURP en el PDF de origen cuyo dígito verificador no coincide con el algoritmo RENAPO (requiere revisión física con el acta de nacimiento).
  - `renapo_pendiente: 191`: Padrón inicial cargado pendiente de cotejo oficial.
- **Bitácora de auditoría:** 382 eventos inmutables registrados (altas e inscripciones iniciales).
- **Expedientes por completar:** 191 alumnos pendientes de validación documental en el Validador.

---

## 3. Estado de Servicios y Conectividad en PC 4

1. **PostgreSQL 17.11:** Servicio `postgresql-x64-17` activo en segundo plano, escuchando exclusivamente en `127.0.0.1:5432`.
2. **Cerebro Red (`validacion.cerebro_red`):** Servicio HTTP activo en el puerto 8771. En su arranque registra:
   ```text
   Cerebro escuchando en http://<IP-LOCAL>:8771  (modelo sidp-revisor-2)
   Base de datos: PostgreSQL 17.11 con 191 alumnos inscritos.
   Clave para SIDP-Validador.exe: <OCULTO>
   Cierra esta ventana para apagarlo.
   ```
3. **Ollama:** En ejecución local con el modelo `sidp-revisor-2` en el puerto 11434.
4. **Verificación `/salud`:** Responde HTTP 200 con herramientas de lectura en `true`, modelo listo y base en versión 2 con 191 alumnos.
5. **Verificación `/alumnos`:** Responde HTTP 200 entregando la lista de los 6 grupos y sus filas completas al Validador.

---

## 4. Herramienta de Visualización Local para el Operador

Para facilitar la supervisión directa sin exponer datos personales al exterior, se preparó un script de consola interactivo para Maximiliano en:
- `C:\SIDP-datos\ver_alumnos_postgres.bat`
- Acceso directo en el Escritorio: `Ver_Alumnos_PostgreSQL.bat`

Esta herramienta permite al operador consultar en pantalla la lista completa de los 191 alumnos, filtrar por grupo, buscar por nombre o CURP y acceder a la consola interactiva `psql` conectada a `sidp_cerebro`.

---

## 5. Protocolo de Seguridad y Privacidad

- **Cero filtración de credenciales:** Ninguna contraseña de superusuario ni de rol, ni la clave del cerebro, fueron registradas en el repositorio, en los informes ni en mensajes públicos.
- **Protección de datos de menores:** El archivo original `lista_oficial.pdf` permanece en `C:\SIDP-datos\` fuera del árbol git. Todos los informes subidos a GitHub contienen exclusivamente datos estadísticos, conteos y estados de validación.
