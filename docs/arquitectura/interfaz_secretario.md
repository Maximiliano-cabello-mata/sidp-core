# Diseño de Interfaz de Usuario: Portal de Secretaría (Control Escolar) — SIDP

Fecha: 2026-10-14  
Estado: Aprobado para diseño y maquetación de frontend  
Rol del Sistema: `Secretaria` / `Control Escolar`  
Documento rector de interfaz para el puesto de control escolar en el Sistema Integral Delfino Pando (SIDP).  
Relacionado con: [sistema_administrativo.md](sistema_administrativo.md), [modulo_expediente.md](modulo_expediente.md), [ADR-019](decisiones.md) y [bocetos/secretario.txt](bocetos/secretario.txt).

---

## 1. Alcance y Reglas de Seguridad en Interfaz

El perfil de Secretaría constituye el motor operativo diario de la escuela para inscripciones, expedientes, constancias e inventario. Para proteger la privacidad de los menores y la seguridad institucional, la interfaz aplica estrictas reglas de control de acceso (vinculadas a `backend/seguridad.py`):

### Restricciones y protecciones activas para Secretaría:
1. **Directorio sin docentes:** En la sección de personas solo puede buscar y gestionar Alumnos y Tutores; los expedientes y datos de docentes están ocultos para este rol.
2. **Folder escolar seguro (Privacidad de salud):** Dentro de los expedientes, los documentos de identidad (Acta, CURP, fotos) están disponibles para ver y descargar, pero los documentos confidenciales (Certificados Médicos, Reportes Psicológicos) se muestran bloqueados con candado (`🔒 Acceso restringido (Exclusivo de Dirección)`).
3. **Sin acciones destructivas:** No existe el botón de *"Eliminar Expediente"* ni la facultad de borrar registros oficiales de alumnos.
4. **Sin auditoría forense expuesta:** No tiene acceso al panel *"El Ojo del Sistema"* (historial de quién ha visto o descargado archivos), reservado para Dirección y Administradores.
5. **Sin acceso a Ajustes del Sistema:** La barra lateral no incluye el menú de configuración institucional, políticas ni roles.

---

## 2. Estructura de Navegación

* **Barra Superior (Top Bar):**
  * `[ 🏫 Nombre de tu Escuela ]`
  * Buscador rápido contextual: `🔍 Buscar alumno, grupo o trámite...`
  * Notificaciones operativas: `🔔 (3)`
  * Perfil activo: `👤 Secretaria`
* **Barra Lateral (Sidebar):**
  * 🏠 **Inicio:** Resumen de jornada, trámites urgentes y constancias listas.
  * 👥 **Personas:** Directorio y registro de Alumnos y Tutores.
  * 📂 **Archivo Escolar:** Carpetas de alumnos, expedientes por grupo y calificaciones.
  * 📦 **Inventario:** Préstamos y devoluciones de equipo escolar.

---

## 3. Especificación Detallada de Pantallas y Wireframes

### 3.1. Inicio (Panel Operativo de Secretaría)

Ofrece una visión ejecutiva de los pendientes del día: nuevos alumnos inscritos, documentos faltantes por recabar y constancias que ya fueron firmadas por la Dirección listas para entrega.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar alumno, grupo o trámite... | 🔔 (3) | 👤 Secretaria
================================================================================
 👉 Inicio         |  ¡Buen día, Rosa! 👋 
                   |  Resumen de tu jornada para hoy (14 de Octubre).
 👥 Personas       |  
                   |  =========================================================
 📂 Archivo        |  📊 TU VISTAZO RÁPIDO
    Escolar        |  =========================================================
                   |  [ 👨‍🎓 12 ]             [ ⚠️ 5 ]             [ ⏳ 3 ]
                   |  Nuevos ingresos      Faltan Documentos    Esperando Firma
                   |  (Este mes)           (Resolver hoy)       (Del Director)
                   |
 📦 Inventario     |  =========================================================
                   |  🚀 ACCESOS RÁPIDOS (Tus herramientas de uso diario)
                   |  =========================================================
                   |  [ + Inscribir Nuevo Alumno ]   [ 🖨️ Generar Constancia ]
                   |  [ 📝 Capturar Calificaciones ] [ 💬 Enviar Aviso a Padres ]
                   |
                   |  =========================================================
                   |  ⚠️ ALERTAS Y TAREAS PENDIENTES
                   |  =========================================================
                   |  • Urgente: Juan Pérez (1ro A) aún no entrega Acta de Nacimiento. [Ver]
                   |  • Recordatorio: Cierre de calificaciones de 3ro B es el viernes. 
                   |  • Trámite Listo: El Director ya firmó la constancia de María López. [Imprimir]
================================================================================
```

---

### 3.2. Directorio de Personas (Alumnos y Tutores)

Vista de consulta y contacto. Note la ausencia deliberada de la pestaña de Docentes.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar Alumno o Tutor...    | 🔔 (3) | 👤 Secretaria
================================================================================
 🏠 Inicio         |  DIRECTORIO DE ALUMNOS Y TUTORES
                   |  
 👉 Personas       |  =========================================================
                   |  [ 👨‍🎓 ALUMNOS ]  [ 👨‍👩‍👧 TUTORES ]    (❌ Falta la pestaña DOCENTES)
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  [ + Inscribir Nuevo Alumno ]   [ + Registrar Tutor ]
                   |  
                   |  ---------------------------------------------------------
                   |  | Matrícula | Nombre Completo | CURP Validado | Rol     | Acciones |
 📦 Inventario     |  |-----------|-----------------|---------------|---------|----------|
                   |  | 2026-001  | Pérez, Juan     | [✅ RENAPO]   | Alumno  | [Abrir]  |
                   |  | 2026-002  | Gómez, Carlos   | [✅ RENAPO]   | Alumno  | [Abrir]  |
                   |  | TUT-089   | Sr. Pérez, J.   | [⚠️ Faltante] | Tutor   | [Abrir]  |
                   |  ---------------------------------------------------------
                   |  (❌ Nota: La secretaria no puede ver ni buscar a los maestros aquí).
================================================================================
```

---

### 3.3. Proceso de Inscripción de Nuevo Alumno con Validación RENAPO

Asistente que conecta con el servicio oficial para autocompletar la información legal y evitar errores ortográficos o de fecha.

#### Wireframe:
```text
================================================================================
  👨‍🎓 INSCRIBIR NUEVO ALUMNO
--------------------------------------------------------------------------------
  Para evitar errores de captura, ingresa la CURP del alumno. 

  [ CURP: PEJU051012HDFRRM01 ]  [ 🔍 Validar en RENAPO ]

  ----------------------------------------------------------------------
  (Después de validar:)
  ✅ Identidad Confirmada
  Nombre Completo: JUAN PÉREZ LÓPEZ
  Fecha de Nacimiento: 12/Oct/2005 

  ----------------------------------------------------------------------
  COMPLETAR INSCRIPCIÓN:
  
  Asignar a Grupo:    [ Seleccionar... 🔽 ]  (Ej: 1ro "A")
  Nombre del Tutor:   [ Buscar en sistema... 🔍 ]

                             [ ❌ Cancelar ]    [ 💾 Inscribir Alumno ]
================================================================================
```

---

### 3.4. Archivo Escolar (Listado por Grupo)

Navegación del archivo de expedientes organizado por grupos con filtro directo.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar alumno por nombre o matrícula... | 👤 Secretaria
================================================================================
 🏠 Inicio         |  ARCHIVO ESCOLAR
                   |  
 👥 Personas       |  =========================================================
                   |  [ 📂 EXPEDIENTES ]  [ 📝 CALIFICACIONES ]  [ 🖨️ LISTAS DE GRUPO ]
 👉 Archivo        |  =========================================================
    Escolar        |
                   |  ACCIONES DE RUTINA
                   |  [ 🗂️ Filtrar por Grupo: 1ro "A" 🔽 ] 
                   |  
                   |  ---------------------------------------------------------
 📦 Inventario     |  | Matrícula | Nombre del Alumno | Grado y Grupo | Acciones      |
                   |  |-----------|-------------------|---------------|---------------|
                   |  | 2026-001  | Pérez, Juan       | 1ro "A"       | [Abrir Folder]|
                   |  | 2026-002  | Gómez, Carlos     | 1ro "A"       | [Abrir Folder]|
                   |  | 2026-003  | López, María      | 1ro "A"       | [Abrir Folder]|
                   |  ---------------------------------------------------------
================================================================================
```

---

### 3.5. Folder Escolar Seguro (Expediente con Restricción de Privacidad)

Al abrir el expediente de un estudiante, la secretaria puede consultar y subir documentos escolares estándar, mientras que los datos sensibles de salud permanecen restringidos.

#### Wireframe:
```text
================================================================================
  📂 FOLDER ESCOLAR: Juan Pérez López (Matrícula: 2026-001)
--------------------------------------------------------------------------------
  [ 📑 Documentos ]  [ 📊 Calificaciones ]  [ 📄 Preparar Constancia ]

  DOCUMENTOS BÁSICOS (Permitidos para tu puesto)
  ---------------------------------------------------------
  📄 Acta de Nacimiento     | Subido: 10/Ago | [👁️ Ver] [⬇️ Descargar]
  📄 CURP                   | Subido: 10/Ago | [👁️ Ver] [⬇️ Descargar]
  📸 Fotografía Infantil    | Subido: 10/Ago | [👁️ Ver] [⬇️ Descargar]
  ---------------------------------------------------------

  DOCUMENTOS CONFIDENCIALES
  ---------------------------------------------------------
  🏥 Certificado Médico     | 🔒 Acceso restringido (Exclusivo de Dirección)
  🧠 Reporte Psicológico    | 🔒 Acceso restringido (Exclusivo de Dirección)
  ---------------------------------------------------------

  [ ⬆️ Subir Nuevo Documento Común ]    

  ( ❌ Nota visual: Como puedes notar, no existe el botón rojo de "Eliminar Expediente" 
  ni el registro de "Quién ha visto esto" que sí tenía el Director ).
================================================================================
```

---

### 3.6. Inventario y Almacén (Operación de Préstamos y Devoluciones)

Módulo diario de secretaría para el control de entrega y recepción de proyectores, bocinas, micrófonos y laptops a docentes.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar equipo o mobiliario... | 👤 Secretaria
================================================================================
 🏠 Inicio         |  INVENTARIO Y ALMACÉN
                   |  
 👥 Personas       |  =========================================================
                   |  [ 💻 TECNOLOGÍA ]  [ 🪑 MOBILIARIO ]  [ 🔄 PRÉSTAMOS ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  TUS ACCIONES DIARIAS
                   |  [ 📤 Registrar Préstamo ]   [ 📥 Recibir Devolución ]
                   |  
                   |  ---------------------------------------------------------
 👉 Inventario     |  | Código  | Artículo            | Estado        | Responsable / Ubicación |
                   |  |---------|---------------------|---------------|-------------------------|
                   |  | PRO-005 | Proyector Epson     | 🔴 Prestado   | Mtra. Laura (Aula 3)    |
                   |  | LAP-002 | Laptop HP Plata     | 🟢 Disponible | Almacén (Tu oficina)    |
                   |  | BOC-001 | Bocina Bluetooth    | 🔴 Prestado   | Mtro. Carlos (Cancha)   |
                   |  | MIC-003 | Micrófono           | ⚠️ Dañado     | Soporte Técnico         |
                   |  ---------------------------------------------------------
================================================================================
```
