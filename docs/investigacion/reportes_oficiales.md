# Qué piden el 911, el SAID y la SEP, y qué puede dar SIDP (2026-10-15)

Pedido de Maximiliano: saber qué formatos y datos piden la Secretaría de Educación y sus sistemas, para que
el panel de **Análisis** los entregue listos (Excel y otros archivos).

> **Fuentes sin verificar.** El entorno donde se hizo esta investigación bloquea gob.mx; lo de abajo sale de
> resúmenes de buscadores y de documentos públicos citados por terceros. Antes de usarlo en un reporte real,
> la dirección debe compararlo con el cuestionario del ciclo vigente.

## Lo que piden

### Estadística 911 (inicio de cursos, primaria: cuestionario 911.3)

Se captura en línea (f911.sep.gob.mx) en octubre, la hace el director y no acepta archivos: SIDP prepara
los números para capturarlos.

| Bloque | Qué pide |
|---|---|
| Alumnos | Inscripción total al 30 de septiembre, por grado y sexo; por edad cumplida al 1 de septiembre; nuevo ingreso y repetidores |
| Grupos | Número de grupos por grado; grupos multigrado |
| Ciclo anterior | Existencia (los que terminaron) y promovidos, por grado y sexo |
| Inclusión | Alumnos con discapacidad, barreras para el aprendizaje (BAP) y aptitudes sobresalientes, por tipo |
| Población | Hablantes de lengua indígena, nacidos en otro país o en otra entidad, afrodescendientes |
| Personal | Por función (director, docente frente a grupo, educación física, apoyo, administrativo), sexo y nivel de estudios |
| Escuela | Aulas en uso, libros de texto recibidos, becas |

### SAID (Edomex: preinscripción y asignación)

- Pide la CURP del alumno y su acta; el tutor elige hasta 5 escuelas.
- Una segunda fase cubre los traslados (cambios de escuela) con la clave de la escuela de origen y de destino.
- La escuela recibe la lista de asignados con su folio: SIDP debe poder guardar ese folio por alumno.

### Evaluación (Acuerdo 10/09/23)

- Tres periodos al año; calificación por campo formativo (Lenguajes; Saberes y pensamiento científico; Ética,
  naturaleza y sociedades; De lo humano y lo comunitario) con observaciones por campo.
- En 1.º de primaria se acredita con haber cursado el grado.

### Control escolar (normas vigentes)

- La falta de un documento no impide inscribir: se firma una carta compromiso y se da un plazo. Con las
  plantillas nuevas, la escuela puede agregar esa carta como documento.

### Programas que piden datos de la escuela

- Beca Rita Cetina: CURP del alumno, clave de centro de trabajo (CCT), CURP e identificación del tutor.
- La Escuela es Nuestra (LEEN): matrícula de la escuela.

No se encontraron plantillas oficiales de Excel para importar datos: todo se captura en los portales.

## Qué ya tiene SIDP y qué le falta

| Dato | ¿Está? | Dónde o qué falta |
|---|---|---|
| Alumno: CURP, nombre, fecha de nacimiento, sexo | Sí | `alumno` |
| Grado, grupo, ciclo | Sí | `grupo`, `inscripcion` |
| Tutor y su CURP | Sí | `tutor.curp` |
| Calificaciones por campo formativo y periodo | Sí | `calificacion` (5 a 10) |
| Asistencia | Sí | `asistencia_alumno` |
| CCT de la escuela | **No** | Una fila de datos de la escuela |
| Nuevo ingreso o repetidor | Parcial | `inscripcion.tipo` tiene nuevo ingreso; falta "repite el grado" |
| Promovido al cerrar el ciclo | **No** | Resultado de fin de ciclo por inscripción |
| Discapacidad, BAP, aptitudes | Parcial | Hoy es texto libre; el 911 pide tipos fijos |
| Lengua indígena, nacido fuera, afrodescendiente | **No** | Tres campos del alumno |
| Personal: sexo, nivel de estudios, función | Parcial | `personal.puesto` existe; faltan sexo y nivel de estudios |
| Aulas, libros, becas | **No** | Datos de la escuela por ciclo |
| Observaciones por campo formativo | Parcial | Hay observaciones por calificación; revisar que sea por campo |
| Carta compromiso | Sí, ya | Se agrega como plantilla |
| Folio SAID, escuela de origen y destino | **No** | Campos de la inscripción y del traslado |

## Qué entregaría el panel de Análisis

1. **Hoja 911 (Excel):** las tablas del cuestionario con los números ya contados (por grado, sexo y edad al
   1 de septiembre), para copiarlos al portal. Con un aviso por cada dato que falte en la base.
2. **Lista de alumnos (Excel y CSV):** CURP, nombre, grado, grupo, sexo, fecha de nacimiento, tutor y
   contacto. Sirve para el SAID, las becas y el padrón.
3. **Calificaciones por grupo y periodo (Excel):** una hoja por grupo, un renglón por alumno y una columna por
   campo formativo.
4. **Asistencia por grupo y mes (Excel).**
5. **Expedientes incompletos (Excel):** quién debe qué documento y desde cuándo.

Antes de construirlo hacen falta los campos de la tabla de arriba y las 6 preguntas pendientes para la
escuela (`docs/investigacion/sistemas-escolares-mexico.md`).
