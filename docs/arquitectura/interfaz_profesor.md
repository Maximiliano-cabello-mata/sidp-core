# Diseño de Interfaz de Usuario: Portal del Docente / Profesor — SIDP

Fecha: 2026-10-14  
Estado: Aprobado para diseño y maquetación de frontend  
Rol del Sistema: `Docente` / `Profesor`  
Documento rector de interfaz para el módulo docente del Sistema Integral Delfino Pando (SIDP).  
Relacionado con: [sistema_administrativo.md](sistema_administrativo.md), [ADR-019](decisiones.md) y [bocetos/profesor.txt](bocetos/profesor.txt).

---

## 1. Alcance y Filosofía de Diseño

El portal del docente está optimizado para la velocidad y la concentración en las tareas pedagógicas cotidianas. A diferencia del panel directivo o administrativo, el docente cuenta con una interfaz **ultra-simplificada y libre de distracciones**:

### Principios de diseño para el docente:
1. **Menú minimalista:** Se eliminan todas las secciones irrelevantes para su función (Inventario, Firmas, Ajustes del sistema y Archivo general no aparecen). Únicamente dispone de **Inicio** y **Mi Grupo**.
2. **Acceso exclusivo a grupos asignados:** El docente solo puede consultar y registrar datos de los alumnos inscritos en sus clases y materias asignadas.
3. **Flujo de pase de lista en segundos:** El registro diario de asistencia está pensado para realizarse al inicio de la jornada escolar con selección rápida de presencia o falta.
4. **Bitácora cualitativa (Observaciones):** Registro ágil de conducta o desempeño académico con clasificación por tipo de nota.

---

## 2. Estructura de Navegación

* **Barra Superior (Top Bar):**
  * `[ 🏫 Nombre de tu Escuela ]`
  * Buscador enfocado: `🔍 Buscar alumno (solo de mis grupos)...`
  * Identificador de perfil: `👤 Profesor`
* **Barra Lateral (Sidebar):**
  * 👉 **Inicio:** Clases del día y recordatorios urgentes de entrega.
  * 👥 **Mi Grupo:** Pase de lista, calificaciones y observaciones del grupo seleccionado.

---

## 3. Especificación de Pantallas y Wireframes

### 3.1. Pantalla de Inicio (Portal del Profesor)

Presenta los recordatorios operativos del día (fechas límite de evaluación, pases de lista pendientes) y acceso directo a cada clase asignada.

#### Componentes:
* **Recordatorios de Hoy:** Alertas automáticas sobre listas sin pasar y cierres de captura de calificaciones.
* **Tus Clases Asignadas:** Tarjetas de acceso directo con materia, grado y grupo (ej. *1ro "A" - Matemáticas*, *3ro "B" - Física*).

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar alumno (solo de mis grupos)... | 👤 Profesor
================================================================================
 👉 Inicio         |  ¡Buen día, Mtra. Laura! 🍎
                   |  
 👥 Mi   Grupo     |  =========================================================
                   |  📌 TUS RECORDATORIOS DE HOY
                   |  =========================================================
                   |  • ⚠️ No has pasado lista en: 1ro "A" (Matemáticas).
                   |  • ⏳ El periodo para subir calificaciones cierra este viernes.
                   |
                   |  =========================================================
                   |  📚 TUS CLASES ASIGNADAS
                   |  =========================================================
                   |  [ 📘 1ro "A" - Matemáticas ] ➡️ [ Entrar a la clase ]
                   |  [ 📙 3ro "B" - Física      ] ➡️ [ Entrar a la clase ]
                   |
                   |  ( ❌ Nota: No hay menú de Inventario, Firmas, ni Ajustes. 
                   |    El menú izquierdo es lo más pequeño posible ).
================================================================================
```

---

### 3.2. Vista de Clase: Pase de Lista y Calificaciones

Espacio de trabajo dentro de una materia y grupo específicos para capturar asistencia diaria y gestionar el avance de evaluaciones.

#### Componentes:
* **Pestañas de la clase:**
  * `[ 📅 PASE DE LISTA ]`: Tabla con número de lista, nombre completo del alumno y selector de estado (`🟢 Presente` o `🔴 Falta`).
  * `[ 📝 CALIFICACIONES ]`: Captura de evaluaciones parciales o finales del periodo.
  * `[ 👁️ OBSERVACIONES ]`: Registro de incidencias y notas cualitativas.
* **Botón de guardado:** Confirmación de registro (`[ 💾 Guardar Asistencia de Hoy ]`).

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 🔍 Buscar alumno en esta clase...      | 👤 Profesor
================================================================================
 🏠 Inicio         |  MATEMÁTICAS - 1ro "A"
                   |  
 👉 Mi   Grupo     |  =========================================================
                   |  [ 📅 PASE DE LISTA ]  [ 📝 CALIFICACIONES ]  [ 👁️ OBSERVACIONES ]
                   |  =========================================================
                   |
                   |  📅 ASISTENCIA DEL DÍA: Hoy, 14 de Octubre
                   |
                   |  ---------------------------------------------------------
                   |  | No. | Alumno              | Asistencia                 |
                   |  |-----|---------------------|----------------------------|
                   |  | 1   | Gómez, Carlos       | (🟢 Presente) (🔴 Falta)   |
                   |  | 2   | López, María        | (🟢 Presente) (🔴 Falta)   |
                   |  | 3   | Pérez, Juan         | (🟢 Presente) (🔴 Falta)   |
                   |  ---------------------------------------------------------
                   |  [ 💾 Guardar Asistencia de Hoy ]
================================================================================
```

---

### 3.3. Observaciones del Grupo (Reportes y Desempeño)

Permite asentar reportes formativos sobre alumnos específicos para comunicación interna o posterior reporte a padres de familia.

#### Componentes:
* **Buscador/Selector de alumno:** Localiza rápidamente al estudiante en la lista del grupo.
* **Área de texto:** Campo para redactar el comportamiento, avance o dificultad observada.
* **Clasificación semántica de nota:**
  * `( ) Positiva 🌟`: Logros, felicitaciones y mejoras notables.
  * `( ) Neutra 📝`: Notas informativas de seguimiento escolar.
  * `( ) Alerta de Conducta ⚠️`: Incidencias, faltas disciplinarias o rezago alarmante.

#### Wireframe:
```text
================================================================================
  👁️ OBSERVACIONES DEL GRUPO: 1ro "A"
--------------------------------------------------------------------------------
  Selecciona un alumno para agregar un reporte de conducta o desempeño.
  
  [ Buscar Alumno... 🔍 ] (Ej. Selecciona a "Carlos Gómez")

  Escribe tu observación sobre Carlos:
  [ Carlos ha mostrado mucha mejora en las multiplicaciones, pero platica 
    mucho durante las explicaciones. _________________________________ ]

  Tipo de nota: 
  ( ) Positiva 🌟    ( ) Neutra 📝    ( ) Alerta de Conducta ⚠️

                             [ ❌ Cancelar ]    [ 💾 Guardar Observación ]
================================================================================
```

---

## 4. Reglas de Privacidad y Seguridad del Docente

1. **Aislamiento de expediente médico:** El docente no tiene acceso a diagnósticos confidenciales ni reportes psicológicos completos; únicamente a indicaciones de salud operativas que la dirección apruebe compartir (ej. alergias severas).
2. **Imposibilidad de alteración de matrícula:** El docente no puede dar de alta ni de baja alumnos; la lista del grupo es gestionada por Secretaría y Dirección.
3. **Control de versiones en calificaciones:** Cada captura de calificaciones queda sellada con marca de tiempo y usuario para evitar discrepancias.
