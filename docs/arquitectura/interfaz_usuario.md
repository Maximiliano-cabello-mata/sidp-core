# Diseño de Interfaz de Usuario (UI) y Experiencia de Usuario (UX) — SIDP

Fecha: 2026-10-13  
Estado: Aprobado para diseño y maquetación de frontend  
Documento rector de interfaz para el Sistema Integral Delfino Pando (SIDP).  
Relacionado con: [ADR-019](decisiones.md) (arquitectura de datos), [ADR-022](decisiones.md) (validación documental), [sistema_administrativo.md](sistema_administrativo.md) y [modulo_expediente.md](modulo_expediente.md).

---

## 1. Visión y Principios de Diseño

La interfaz de SIDP está diseñada para operar de manera ágil, intuitiva y confiable en computadoras de escritorio y estaciones de trabajo dentro de una escuela primaria en red local (LAN).

### Principios rectores:
1. **Claridad inmediata:** Menos clics, tipografía legible y estados visuales con códigos de color directos (🟢 Disponible / Óptimo, 🔴 En Préstamo / Crítico, ⚠️ Advertencia / Faltante).
2. **Validación asistida en origen:** El sistema ayuda al usuario a evitar errores humanos autocompletando datos oficiales (RENAPO) a partir de la CURP.
3. **Seguridad y auditoría visible ("El Ojo del Sistema"):** Cada consulta, descarga, firma o modificación deja un rastro claro e inmutable accesible para los administradores.
4. **Permisos por función mínima:** Cada miembro del personal accede exclusivamente a las funciones y documentos autorizados para su rol.

---

## 2. Estructura y Navegación Global (Layout Maestro)

La interfaz se divide en dos componentes principales fijos en pantalla:

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
  * Perfil activo y selector de rol (`👤 Director`, `👤 Super Admin`, `👤 Secretaria`).
* **Barra Lateral (Sidebar):**
  * 🏠 **Inicio:** Resumen ejecutivo, accesos rápidos y actividad reciente.
  * 👥 **Personas:** Directorio y registro de alumnos, docentes y tutores.
  * 📂 **Archivo Escolar:** Expediente digital, documentos y trazabilidad.
  * ✍️ **Firmar Documentos:** Bandeja de firma electrónica y validación.
  * 📦 **Inventario:** Control de tecnología, mobiliario y préstamos.
  * ⚙️ **Ajustes:** Configuración del plantel, personal, permisos y respaldos.

---

## 3. Especificación Detallada de Módulos

### 3.1. Inicio (Dashboard Principal)

Panel de control que recibe al personal al iniciar el día, ofreciendo métricas operativas al instante, atajos directos a tareas frecuentes y bitácora de eventos recientes.

#### Componentes:
* **Métricas clave (KPIs):** Alumnos activos, documentos pendientes de firma y salud de la plataforma/LAN.
* **Accesos rápidos:** Acciones de un solo clic para las operaciones más comunes.
* **Actividad reciente:** Eventos registrados en tiempo real por el personal y el sistema.

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
                   |  [ 👨🎓 450 ]          [ ✍️ 5 ]             [ 🟢 Óptimo ]
 ✍️ Firmar         |  Alumnos Activos    Docs. por Firmar     Estado del Sistema
    Documentos     |  
                   |
 📦 Inventario     |  =========================================================
                   |  🚀 ACCESOS RÁPIDOS (Lo que haces más seguido)
 ⚙️ Ajustes        |  =========================================================
                   |  [ + Inscribir Alumno ]   [ 📄 Revisar Bandeja de Firmas ]
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

### 3.2. Directorio de Personas y Alta con RENAPO

Gestión centralizada de todas las personas que forman parte de la comunidad escolar: estudiantes, docentes y padres de familia o tutores.

#### Características clave:
* **Filtros por rol:** Pestañas segmentadas para Alumnos, Docentes y Tutores.
* **Estado de validación de CURP:** Distintivo visual claro (`[✅ RENAPO]` o `[⚠️ Faltante]`).
* **Asistente de registro inteligente:** Evita errores de captura solicitando la CURP primero y autocompletando nombre, fecha de nacimiento, edad y entidad federativa tras la verificación oficial.

#### Wireframe del Directorio:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar (Nombre, Matrícula o CURP)... | 👤 Menú
================================================================================
 🏠 Inicio         |  DIRECTORIO DE PERSONAS
                   |  
 👉 Personas       |  =========================================================
                   |  [ 👨🎓 ALUMNOS ]  [ 👩🏫 DOCENTES ]  [ 👨👩👧 TUTORES ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  [ + Inscribir / Registrar Nuevo ]   [ 📥 Importar Lista ]
 ✍️ Firmar         |  
    Documentos     |  ---------------------------------------------------------
                   |  | Matrícula | Nombre Completo | CURP Validado | Rol     | Acciones |
 📦 Inventario     |  |-----------|-----------------|---------------|---------|----------|
                   |  | 2026-001  | Pérez, Juan     | [✅ RENAPO]   | Alumno  | [Ver]    |
 ⚙️ Ajustes        |  | 2026-002  | Gómez, Carlos   | [✅ RENAPO]   | Alumno  | [Ver]    |
                   |  | DOC-014   | Mtra. Laura R.  | [✅ RENAPO]   | Docente | [Ver]    |
                   |  | TUT-089   | Sr. Pérez, J.   | [⚠️ Faltante] | Tutor   | [Ver]    |
                   |  ---------------------------------------------------------
================================================================================
```

#### Wireframe del Formulario / Modal de Registro:
```text
================================================================================
  👤 REGISTRAR NUEVA PERSONA
--------------------------------------------------------------------------------
  Para evitar errores, ingresa la CURP de la persona. 
  El sistema autocompletará el resto de los datos.

  [ CURP: PEJU051012HDFRRM01 ]  [ 🔍 Validar y Buscar ]

  ----------------------------------------------------------------------
  (Después de hacer clic en Validar, el sistema muestra automáticamente:)

  ✅ Identidad Confirmada por RENAPO
  Nombre: JUAN PÉREZ LÓPEZ
  Nacimiento: 12/Oct/2005 (21 años)
  Entidad: Ciudad de México

  Selecciona el rol que tendrá en la escuela:
  ( ) Alumno Nuevo
  ( ) Docente
  ( ) Tutor / Padre de familia

                             [ ❌ Cancelar ]    [ 💾 Guardar Persona ]
================================================================================
```

---

### 3.3. Archivo Escolar (Expediente del Alumno y Auditoría)

Administración del archivo digital oficial de cada alumno con control de acceso por documento y trazabilidad de lecturas y descargas.

#### Puntos destacados:
* **Ficha del alumno:** Identificación rápida por Nombre, Matrícula y Grado/Grupo.
* **Repositorio documental:** Visualización y descarga de Acta de Nacimiento, CURP validada, Certificado Médico y Cartas Responsivas.
* **El Ojo del Sistema (Historial de Visitas y Auditoría):** Registro inmutable en pantalla de quién descargó o visualizó cada documento, con hora y usuario exacto.

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
 ✍️ Firmar         |  DOCUMENTOS DEL ALUMNO (Acceso Ilimitado Activado 🟢)
    Documentos     |  Aquí puedes ver y descargar todo el archivo digital.
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

### 3.4. Firmar Documentos (Firma Electrónica Avanzada)

Flujo para directivos y autoridades escolares que permite avalar electrónicamente constancias, boletas y nombramientos mediante certificados digitales seguros.

#### Características:
* **Bandeja de entrada organizada:** Pestañas para documentos "Por Firmar", "Ya Firmados" y herramienta para "Verificar Firma".
* **Firma en lote:** Selección múltiple mediante casillas de verificación para autorizar varios documentos de una sola vez.
* **Modal de seguridad criptográfica:** Confirmación de identidad mediante archivo de certificado digital (`.cer`) y contraseña de firma.

#### Wireframe de la Bandeja:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar documento o alumno... | 🔔 (5) | 👤 Director
================================================================================
 🏠 Inicio         |  FIRMAR DOCUMENTOS
                   |  
 👥 Personas       |  =========================================================
                   |  [ 📥 POR FIRMAR (5) ]  [ 🗂️ YA FIRMADOS ]  [ 🔍 VERIFICAR FIRMA ]
 📂 Archivo        |  =========================================================
    Escolar        |
                   |  DOCUMENTOS PENDIENTES DE TU AUTORIZACIÓN
 👉 Firmar         |  Selecciona los documentos que deseas firmar electrónicamente.
    Documentos     |  
                   |  ---------------------------------------------------------
 📦 Inventario     |  | ✔️ | Tipo de Documento  | Alumno / Docente | Fecha Generado |
                   |  |----|--------------------|------------------|----------------|
 ⚙️ Ajustes        |  | [ ]| Constancia Estudio | Juan Pérez (1ro) | Hoy 09:00 AM   |
                   |  | [ ]| Boleta de Calific. | Carlos Gómez     | Ayer 14:30 PM  |
                   |  | [ ]| Nombramiento       | Mtra. Laura Ruiz | Ayer 10:00 AM  |
                   |  ---------------------------------------------------------
                   |
                   |  [ 👁️ Revisar Seleccionados ]     [ ✍️ FIRMAR SELECCIONADOS ]
================================================================================
```

#### Wireframe del Modal de Autorización:
```text
================================================================================
  🔐 AUTORIZACIÓN DE FIRMA DIGITAL
--------------------------------------------------------------------------------
  Estás a punto de firmar 3 documentos con valor oficial.

  Por seguridad, confirma tu identidad:

  Tu Certificado Digital:  [ Archivo_Firma_Director.cer 📁 ] (Cargado)
  
  Contraseña de tu firma:  [ ******************** ]

                           [ ❌ Cancelar ]    [ ✍️ AUTORIZAR Y FIRMAR ]
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
 ✍️ Firmar         |  
    Documentos     |  ---------------------------------------------------------
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
* **Historial de Movimientos:** Auditoría completa de eliminaciones, firmas y descargas.
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
 ✍️ Firmar         |  
    Documentos     |  ---------------------------------------------------------
                   |  🏫 DATOS GENERALES DE LA ESCUELA (Políticas)
 📦 Inventario     |  • Ciclo escolar actual: 2026-2027
                   |  • Cambiar logo o nombre de la institución.
 👉 Ajustes        |  • Activar/Desactivar periodos de evaluación.
                   |  [ ✏️ Modificar Datos ]
                   |  ---------------------------------------------------------
                   |  👥 PERSONAL Y PERMISOS (Aquí entra el boceto que me mandaste)
                   |  • Administrar a los empleados, maestos y secretarias.
                   |  • Decidir quién puede ver qué cosa.
                   |  [ ⚙️ Administrar Personal ] 
                   |  ---------------------------------------------------------
                   |  📋 HISTORIAL DE MOVIMIENTOS (Auditoría)
                   |  • Ver el registro detallado de quién borró, firmó o descargó archivos.
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
 ✍️ Firmar         |  PUESTO: Secretaria de Control Escolar
    Documentos     |  
                   |  ¿QUÉ PUEDE HACER ESTA PERSONA EN EL SISTEMA?
 📦 Inventario     |  (Marca con una ✔️ lo que le autorizas hacer)
                   |
 👉 Ajustes        |  ---------------------------------------------------------
                   |  [ ✔️ ] Inscribir alumnos nuevos.
                   |  [ ✔️ ] Ver y descargar documentos de identidad (Actas, CURP).
                   |  [   ] Ver documentos confidenciales (Médicos, Psicológicos). 🔒
                   |  [ ✔️ ] Subir calificaciones.
                   |  [   ] Firmar documentos oficiales (Uso de Certificados). 🔒
                   |  [   ] Eliminar alumnos o borrar expedientes completos. 🔒
                   |  ---------------------------------------------------------
                   |
                   |           [ ❌ Cancelar ]        [ 💾 Guardar Permisos ]
================================================================================
```

---

## 4. Matriz de Roles y Accesos Recomendada

| Función / Permiso | Director | Secretaria | Docente | Administrador Técnico |
|---|:---:|:---:|:---:|:---:|
| Inscribir alumnos nuevos | ✅ | ✅ | ❌ | ❌ |
| Ver documentos de identidad (Acta, CURP) | ✅ | ✅ | ❌ | ❌ |
| Ver documentos confidenciales (Médicos/Psicológicos) | ✅ | 🔒 (Req. permiso) | ❌ | ❌ |
| Capturar calificaciones de grupo asignado | ✅ | ✅ | ✅ (Sólo sus grupos) | ❌ |
| Firmar documentos oficiales con e.firma/.cer | ✅ | ❌ | ❌ | ❌ |
| Eliminar alumnos o expedientes completos | ✅ | ❌ | ❌ | ❌ |
| Gestión de inventario y préstamos | ✅ | ✅ | 👁️ (Consulta) | ❌ |
| Descargar copias de seguridad / auditoría | ✅ | ❌ | ❌ | ✅ |
