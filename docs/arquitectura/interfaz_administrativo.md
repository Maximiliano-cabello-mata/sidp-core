# Diseño de Interfaz de Usuario (UI) y Experiencia de Usuario (UX) — SIDP

Fecha: 2026-10-14  
Estado: Aprobado para diseño y maquetación de frontend  
Documento rector de interfaz para el Sistema Integral Delfino Pando (SIDP).  
Relacionado con: [ADR-019](decisiones.md) (arquitectura de datos), [ADR-022](decisiones.md) (validación documental), [sistema_administrativo.md](sistema_administrativo.md) y [modulo_expediente.md](modulo_expediente.md).

---

## 1. Visión y Principios de Diseño

La interfaz administrativa de SIDP está diseñada para operar de manera ágil, intuitiva y confiable en computadoras de escritorio y estaciones de trabajo dentro de una escuela primaria en red local (LAN).

### Principios rectores:
1. **Claridad operativa:** Menos clics, tipografía legible y estados visuales con códigos de color directos (🟢 Disponible / Óptimo, 🔴 En Préstamo / Crítico, ⚠️ Advertencia / Faltante, ⏳ Pendiente).
2. **Validación asistida en origen:** El sistema ayuda al personal a evitar errores de captura autocompletando datos oficiales (RENAPO) a partir de la CURP.
3. **Supervisión académica continua:** Monitoreo diario en tiempo real sobre la captura de asistencias por grupo y el avance en evaluaciones/calificaciones docentes.
4. **Seguridad y auditoría visible ("El Ojo del Sistema"):** Cada consulta, descarga o modificación documental deja un rastro inmutable y visible para la dirección.
5. **Permisos por función mínima:** Cada integrante del personal accede estrictamente a las funciones y documentos correspondientes a su perfil.

---

## 2. Estructura y Navegación Global (Layout Maestro)

La interfaz se divide en dos áreas principales fijas en pantalla:

```mermaid
flowchart TD
    subgraph APP[Ventana Principal del Sistema]
        TOP[Barra Superior: Escuela | Buscador Contextual | Notificaciones | Perfil Activo]
        subgraph BODY[Cuerpo Principal]
            SIDE[Barra Lateral: Menú de Navegación]
            CONT[Área de Contenido / Vistas / Formularios / Tablas]
        end
    end
    TOP --- BODY
    SIDE --- CONT
```

* **Barra Superior (Top Bar):**
  * Identificación de la institución: `[ 🏫 Nombre de tu Escuela ]`
  * Buscador global rápido (contextual según la sección activa).
  * Centro de notificaciones con contador visual (`🔔 (N)`).
  * Perfil activo y selector de rol (`👤 Director`, `👤 Super Admin`, `👤 Menú`).
* **Barra Lateral (Sidebar):**
  * 🏠 **Inicio:** Resumen ejecutivo, accesos rápidos y actividad reciente.
  * 👥 **Personas:** Directorio y registro de alumnos, docentes y tutores.
  * 📂 **Archivo Escolar:** Expediente digital, documentos y trazabilidad.
  * 📝 **Asistencias y Calific.:** Supervisión del avance diario y evaluaciones por grupo.
  * 📦 **Inventario:** Control de tecnología, mobiliario y préstamos.
  * ⚙️ **Ajustes:** Configuración del plantel, personal, permisos y respaldos.

---

## 3. Especificación Detallada de Módulos

### 3.1. Inicio (Dashboard Principal)

Panel de control que recibe a la dirección y personal al iniciar el día, ofreciendo métricas operativas al instante, atajos directos a tareas frecuentes y bitácora de eventos recientes.

#### Componentes:
* **Vistazo Rápido (KPIs):** Alumnos activos (`[ 👨‍🎓 450 ]`), avance de evaluaciones (`[ 📝 12 ] Grupos Evaluados`) y salud del sistema (`[ 🟢 Óptimo ]`).
* **Accesos Rápidos:** Acciones de un solo clic para las operaciones más cotidianas (`+ Inscribir Alumno`, `Ver Reporte de Asistencia`, `Buscar Expediente`, estado de conexión con RENAPO).
* **Actividad Reciente:** Eventos registrados en tiempo real por el personal y procesos automáticos del sistema.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Búsqueda rápida de alumnos... | 🔔 (2) | 👤 Director
================================================================================
 👉 Inicio         |  ¡Buenos días, Ana! 👋 
                   |  Aquí tienes el resumen de tu escuela hoy (14 de Octubre).
 👥 Personas       |  
                   |  =========================================================
 📂 Archivo        |  📊 VISTAZO RÁPIDO
    Escolar        |  =========================================================
                   |  [ 👨‍🎓 450 ]          [ 📝 12 ]            [ 🟢 Óptimo ]
 📝 Asistencias    |  Alumnos Activos    Grupos Evaluados     Estado del Sistema
    y Calific.     |  
                   |
 📦 Inventario     |  =========================================================
                   |  🚀 ACCESOS RÁPIDOS (Lo que haces más seguido)
 ⚙️ Ajustes        |  =========================================================
                   |  [ + Inscribir Alumno ]   [ 📊 Ver Reporte de Asistencia ]
                   |  [ 🔍 Buscar Expediente ] [ 🔄 Conexión con RENAPO: Activa ]
                   |
                   |  =========================================================
                   |  📋 ACTIVIDAD RECIENTE EN LA ESCUELA
                   |  =========================================================
                   |  • Hace 10 min: Secretaría inscribió a "Carlos Gómez" (1ro A).
                   |  • Hace 45 min: Sistema respaldó la base de datos automáticamente.
                   |  • Ayer 18:00: Mtra. Laura subió calificaciones de 3ro B.
================================================================================
```

---

### 3.2. Directorio de Personas

Gestión centralizada de todas las personas que forman parte de la comunidad escolar: estudiantes, docentes y padres de familia o tutores.

#### Características clave:
* **Filtros por rol:** Pestañas segmentadas para Alumnos, Docentes y Tutores.
* **Estado de validación de CURP:** Distintivo visual claro (`[✅ RENAPO]` o `[⚠️ Faltante]`).
* **Acciones:** Inscripción/alta de nuevas personas e importación de listas.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar (Nombre, Matrícula o CURP)... | 👤 Menú
================================================================================
 🏠 Inicio         |  DIRECTORIO DE PERSONAS
                   |  
 👉 Personas       |  =========================================================
                   |  [ 👨‍🎓 ALUMNOS ]  [ 👩‍🏫 DOCENTES ]  [ 👨‍👩‍👧 TUTORES ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  [ + Inscribir / Registrar Nuevo ]   [ 📥 Importar Lista ]
 📝 Asistencias    |  
    y Calific.     |  ---------------------------------------------------------
                   |  | Matrícula | Nombre Completo | CURP Validado | Rol     | Acciones |
 📦 Inventario     |  |-----------|-----------------|---------------|---------|----------|
                   |  | 2026-001  | Pérez, Juan     | [✅ RENAPO]   | Alumno  | [Ver]    |
 ⚙️ Ajustes        |  | 2026-002  | Gómez, Carlos   | [✅ RENAPO]   | Alumno  | [Ver]    |
                   |  | DOC-014   | Mtra. Laura R.  | [✅ RENAPO]   | Docente | [Ver]    |
                   |  | TUT-089   | Sr. Pérez, J.   | [⚠️ Faltante] | Tutor   | [Ver]    |
                   |  ---------------------------------------------------------
================================================================================
```

---

### 3.3. Archivo Escolar (Expediente del Alumno y Auditoría)

Administración del archivo digital oficial de cada alumno con control de acceso por documento y trazabilidad de lecturas y descargas.

#### Puntos destacados:
* **Ficha del alumno:** Identificación rápida por Nombre, Matrícula y Grado/Grupo.
* **Pestañas:** Datos Generales, Documentos y Quién ha visto esto.
* **Repositorio documental:** Visualización y descarga de Acta de Nacimiento, CURP validada, Certificado Médico y Cartas Responsivas.
* **El Ojo del Sistema (Historial de Visitas y Auditoría):** Registro inmutable en pantalla de quién descargó o visualizó cada documento, con fecha, hora y usuario exacto.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar...                           | 👤 Super Admin
================================================================================
 🏠 Inicio         |  ARCHIVO ESCOLAR > EXPEDIENTE DEL ALUMNO
                   |  
 👥 Personas       |  👤 Carlos Gómez López | Matrícula: 2026-045 | Grupo: 3ro "B"
                   |  =========================================================
 👉 Archivo        |  [ 📋 Datos Generales ]  [ 📂 DOCUMENTOS ]  [ 👁️ QUIÉN HA VISTO ESTO ]
    Escolar        |  =========================================================
                   |
 📝 Asistencias    |  DOCUMENTOS DEL ALUMNO (Acceso Ilimitado Activado 🟢)
    y Calific.     |  Aquí puedes ver y descargar todo el archivo digital.
                   |  
 📦 Inventario     |  ---------------------------------------------------------
                   |  📄 Acta de Nacimiento     | Subido: 10/Ago | [👁️ Ver] [⬇️ Descargar]
 ⚙️ Ajustes        |  📄 CURP (Valido x RENAPO) | Subido: 10/Ago | [👁️ Ver] [⬇️ Descargar]
                   |  🏥 Certificado Médico     | Subido: 12/Ago | [👁️ Ver] [⬇️ Descargar]
                   |  📝 Carta Responsiva       | Subido: 12/Ago | [👁️ Ver] [⬇️ Descargar]
                   |  ---------------------------------------------------------
                   |
                   |  ⬇️ EL OJO DEL SISTEMA: HISTORIAL DE VISITAS (Auditoría) ⬇️
                   |  ---------------------------------------------------------
                   |  • Hoy 10:15 AM - Ana G. (Directora) descargó "Certificado Médico".
                   |  • Ayer 08:30 AM - Rosa M. (Secretaria) vio "Acta de Nacimiento".
                   |  • 12/Ago 14:00 PM - Sistema validó CURP automáticamente.
================================================================================
```

---

### 3.4. Asistencias y Calificaciones (Supervisión)

Módulo central para el seguimiento directivo y administrativo del trabajo escolar cotidiano de los docentes.

#### Características:
* **Vistas segmentadas:** Pestañas para `[ 📅 REPORTE DE ASISTENCIAS ]` y `[ 📝 BOLETAS Y CALIFICACIONES ]`.
* **Monitoreo por grupos:** Supervisión en tiempo real del pase de lista del día y estado de captura de evaluaciones periódicas.
* **Semáforo de cumplimiento:**
  * ✅ **Capturada / Completadas:** Cumplido en tiempo y forma.
  * ⏳ **Pendiente:** En proceso de captura dentro del plazo.
  * ⚠️ **Faltante:** Sin captura registrada para el día en curso.
* **Operaciones directas:** Consulta detallada por grupo y exportación/impresión de reportes oficiales.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar grupo o profesor... | 🔔 (1) | 👤 Director
================================================================================
 🏠 Inicio         |  ASISTENCIAS Y CALIFICACIONES (SUPERVISIÓN)
                   |  
 👥 Personas       |  =========================================================
                   |  [ 📅 REPORTE DE ASISTENCIAS ]  [ 📝 BOLETAS Y CALIFICACIONES ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  SEGUIMIENTO POR GRUPOS
 👉 Asistencias    |  Revisa el avance de los profesores en sus evaluaciones diarias.
    y Calific.     |  
                   |  ---------------------------------------------------------
 📦 Inventario     |  | Grupo     | Profesor Titular | Asistencia Hoy | Calificaciones |
                   |  |-----------|------------------|----------------|----------------|
 ⚙️ Ajustes        |  | 1ro "A"   | Mtra. Laura R.   | ✅ Capturada   | ⏳ Pendiente   |
                   |  | 2do "B"   | Mtro. Carlos G.  | ⚠️ Faltante    | ✅ Completadas |
                   |  | 3ro "A"   | Mtra. Rosa M.    | ✅ Capturada   | ✅ Completadas |
                   |  ---------------------------------------------------------
                   |
                   |  [ 👁️ Ver Detalles del Grupo ]     [ 🖨️ Exportar Reportes ]
================================================================================
```

---

### 3.5. Inventario y Almacén

Control de recursos materiales del plantel educativo categorizados por tipo de bien, estado operativo y persona o aula responsable.

#### Características:
* **Categorías:** Pestañas para Tecnología, Mobiliario y Registro de Préstamos.
* **Identificación rápida:** Código interno de inventario y soporte para escaneo mediante código QR.
* **Semáforo de estado:**
  * 🟢 **Disponible:** Listo para asignación o uso en almacén o aula.
  * 🔴 **En Préstamo:** Asignado temporalmente a un docente o área.
  * ⚠️ **Dañado:** En mantenimiento o pendiente de reparación.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar equipo, silla, libro... | 🔔 (1) | 👤 Menú
================================================================================
 🏠 Inicio         |  INVENTARIO Y ALMACÉN
                   |  
 👥 Personas       |  =========================================================
                   |  [ 💻 TECNOLOGÍA ]  [ 🪑 MOBILIARIO ]  [ 🔄 PRÉSTAMOS ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  [ + Agregar Nuevo Artículo ]   [ 📷 Escanear Código QR ]
 📝 Asistencias    |  
    y Calific.     |  ---------------------------------------------------------
                   |  | Código  | Artículo            | Estado        | Responsable / Ubicación |
 👉 Inventario     |  |---------|---------------------|---------------|-------------------------|
                   |  | LAP-001 | Laptop HP Plata     | 🔴 En Préstamo| Mtra. Laura (Aula 3)    |
 ⚙️ Ajustes        |  | PRO-005 | Proyector Epson     | 🟢 Disponible | Almacén Principal       |
                   |  | PRO-006 | Proyector Epson     | ⚠️ Dañado     | Mantenimiento           |
                   |  | SIL-102 | Silla de Escritorio | 🟢 Disponible | Aula de Cómputo         |
                   |  ---------------------------------------------------------
================================================================================
```

---

### 3.6. Ajustes y Matriz Granular de Permisos

Centro de administración general del sistema escolar, control de políticas, auditoría forense, respaldos y administración de permisos por empleado.

#### Pantalla Principal de Ajustes:
* **Datos Generales de la Escuela:** Ciclo escolar en curso, logotipo, periodos de evaluación.
* **Personal y Permisos:** Gestión de empleados y control de acceso por privilegios granulares.
* **Historial de Movimientos:** Auditoría completa de eliminaciones y descargas de archivos.
* **Copias de Seguridad (Respaldos):** Descarga inmediata de copias de la base de datos SQLite WAL.

#### Wireframe del Panel de Ajustes:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar en configuración... | 🔔 (1) | 👤 Super Admin
================================================================================
 🏠 Inicio         |  AJUSTES DEL SISTEMA
                   |  
 👥 Personas       |  =========================================================
                   |  [ 🏫 Datos de Escuela ] [ 👥 Personal ] [ 📋 Auditoría ] [ 💾 Respaldos ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  SELECCIONA QUÉ DESEAS CONFIGURAR:
 📝 Asistencias    |  
    y Calific.     |  ---------------------------------------------------------
                   |  🏫 DATOS GENERALES DE LA ESCUELA (Políticas)
 📦 Inventario     |  • Ciclo escolar actual: 2026-2027
                   |  • Cambiar logo o nombre de la institución.
 👉 Ajustes        |  • Activar/Desactivar periodos de evaluación.
                   |  [ ✏️ Modificar Datos ]
                   |  ---------------------------------------------------------
                   |  👥 PERSONAL Y PERMISOS 
                   |  • Administrar a los empleados, maestos y secretarias.
                   |  • Decidir quién puede ver qué cosa.
                   |  [ ⚙️ Administrar Personal ] 
                   |  ---------------------------------------------------------
                   |  📋 HISTORIAL DE MOVIMIENTOS (Auditoría)
                   |  • Ver el registro detallado de quién borró o descargó archivos.
                   |  [ 👁️ Revisar Historial ]
                   |  ---------------------------------------------------------
                   |  💾 COPIAS DE SEGURIDAD (Respaldos)
                   |  • Guardar toda la información de la escuela para no perder nada.
                   |  [ ⬇️ Descargar Respaldo Ahora ]
                   |  ---------------------------------------------------------
================================================================================
```

#### Sub-pantalla: Ajustes > Personal > Editar Permisos

Permite al Super Administrador definir con precisión quirúrgica las facultades de cada usuario, distinguiendo operaciones cotidianas de permisos restringidos o críticos (🔒):

```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar...                           | 👤 Super Admin
================================================================================
 🏠 Inicio         |  AJUSTES > PERSONAL > EDITAR PERMISOS
                   |  
 👥 Personas       |  =========================================================
                   |  [ 👤 Datos del Empleado ]  [ 🔐 PERMISOS Y ACCESOS ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  EMPLEADO: Rosa Martínez
 📝 Asistencias    |  PUESTO: Secretaria de Control Escolar
    y Calific.     |  
                   |  ¿QUÉ PUEDE HACER ESTA PERSONA EN EL SISTEMA?
 📦 Inventario     |  (Marca con una ✔️ lo que le autorizas hacer)
                   |
 👉 Ajustes        |  ---------------------------------------------------------
                   |  [ ✔️ ] Inscribir alumnos nuevos.
                   |  [ ✔️ ] Ver y descargar documentos de identidad (Actas, CURP).
                   |  [    ] Ver documentos confidenciales (Médicos, Psicológicos). 🔒
                   |  [ ✔️ ] Subir calificaciones.
                   |  [    ] Eliminar alumnos o borrar expedientes completos. 🔒
                   |  ---------------------------------------------------------
                   |
                   |          [ ❌ Cancelar ]        [ 💾 Guardar Permisos ]
================================================================================
```

---

## 4. Matriz de Roles y Accesos Recomendada

| Función / Permiso | Director | Secretaria | Docente | Administrador Técnico |
|---|:---:|:---:|:---:|:---:|
| Inscribir alumnos nuevos | ✅ | ✅ | ❌ | ❌ |
| Ver documentos de identidad (Acta, CURP) | ✅ | ✅ | ❌ | ❌ |
| Ver documentos confidenciales (Médicos/Psicológicos) | ✅ | 🔒 (Req. permiso) | ❌ | ❌ |
| Supervisar asistencias y avance escolar | ✅ | ✅ (Lectura) | ❌ | ❌ |
| Capturar asistencias y calificaciones | ✅ | ✅ (Apoyo) | ✅ (Sus grupos) | ❌ |
| Eliminar alumnos o expedientes completos | ✅ | ❌ | ❌ | ❌ |
| Gestión de inventario y préstamos | ✅ | ✅ | 👁️ (Consulta) | ❌ |
| Descargar copias de seguridad / auditoría | ✅ | ❌ | ❌ | ✅ |
