# Base de datos de la PC 4 (PostgreSQL)

Decisión de Maximiliano (2026-10-15): la PC 4 tiene su propia base de datos, PostgreSQL, para hacer
mejores procesos. El código está en `validacion/base_cerebro.sql` (esquema `sidp`, versión 2) y
`validacion/base_cerebro.py`. La instalación fue la Tarea 008 del buzón; la carga de los alumnos, la 009.

## Dónde vive cada cosa

- **PC 4:** PostgreSQL escucha solo en 127.0.0.1. Nadie de la red entra a la base: todo pasa por el
  cerebro (puerto 8771, con su clave). La contraseña de la base vive en `%USERPROFILE%\.sidp\`.
- **PC del administrador:** SIDP-Validador.exe sigue guardando los archivos (PDF y fotos) y su SQLite.
  A la PC 4 llega solo la huella (sha256) de cada archivo, no el archivo.
- **Repositorio:** solo el código y números. La lista oficial y los datos de los alumnos nunca se suben.

## Tablas

| Tabla | Qué guarda |
|---|---|
| `ciclo`, `grupo` | Ciclos (agosto a julio) y grupos por grado y letra |
| `alumno` | CURP, nombre, fecha, sexo y entidad (salen de la CURP), si la CURP cuadra su dígito, qué dijo RENAPO |
| `tutor`, `alumno_tutor` | Padres o tutores; un solo tutor principal vigente por alumno |
| `inscripcion` | Un alumno en un grupo por ciclo: incompleta, completa, baja (con motivo) o cancelada |
| `tipo_documento` | Los 10 documentos del expediente, cuáles son obligatorios, desde qué grado y cuánto duran |
| `documento`, `revision_documento` | Cada documento recibido (versiones sin borrar) y quién lo validó o rechazó |
| `importacion` | Cada archivo cargado, por su huella: el mismo archivo no se carga dos veces |
| `lectura` | Lo que leyó el cerebro en cada página y qué tan cerca quedó de un alumno |
| `sugerencia_ia` | Lo que propone la IA; solo una persona lo acepta o lo corrige |
| `bitacora` | Cada alta y cambio, con el antes, el después y quién lo hizo |
| `dato` | Lo que sale del escaneo, campo por campo, solo los del estándar (`validacion/estandar.py`) |
| `alumnos_distintos` | Dos alumnos que se parecen, pero una persona dijo que son niños distintos (gemelos, primos) |
| `biblio_titulo`, `biblio_isbn` | Cada libro distinto (título, autor, editorial, año, serie de Libros del Rincón) y sus ISBN |
| `biblio_ejemplar` | Cada libro físico con su etiqueta `LIB-000001`, dónde se guarda y cómo está |
| `biblio_regla` | Cuántos días y cuántos libros: alumno 7 días y 2 libros; personal 14 días y 5 libros |
| `biblio_prestamo` | Quién se llevó cada ejemplar, cuándo lo regresa y cómo regresó |
| `biblio_consulta` | Lo que contestó el catálogo de Open Library por ISBN, para no volver a preguntar |

## Defensas en el motor

- No se borra nada: `DELETE` y `TRUNCATE` fallan; se usan estados.
- La bitácora no se puede cambiar ni borrar.
- Cada cambio sube la versión de 1 en 1; un cambio que no cambia nada no se guarda.
- Revisar un documento pide una persona (no "IA" ni "cerebro"); rechazar pide motivo; dar de baja también.
- Ningún proceso da de baja a un alumno solo: si falta en una lista, se cuenta en `no_vinieron` y decide una persona.
- Un mismo dato no se guarda dos veces (2026-10-26): el índice único `dato_sin_repetir` no deja dos filas vigentes o
  por confirmar con el mismo alumno, campo y valor (sin importar acentos ni espacios). Al aplicarlo a una base de antes,
  lo repetido queda `reemplazado` con `duplicado_de` y se queda el más seguro. Si dos lecturas lo guardan en el mismo
  instante, `guardar_dato` regresa el que ya estaba en lugar de fallar.
- La base no une alumnos sola: `alumnos_repetidos` solo avisa.

## Procesos (funciones del esquema `sidp`)

- **CURP:** `curp_digito`, `curp_valida`, `curp_fecha`. Revisan igual que el código de Python.
- **Edades:** `edad_al`, `grado_esperado` (6 años cumplidos al 31 de diciembre para 1°) y `ciclo_de`.
- **Cargas:** `cargar_alumnos` (reconoce al alumno por su CURP o por su nombre idéntico, cambia de grupo y
  rechaza renglones malos con su motivo) e `importar` (lo mismo, una sola vez por lista leída; si el lector
  mejora, el mismo PDF se vuelve a cargar y corrige los nombres de cada CURP).
- **Búsqueda:** `curp_cercana` (hasta 2 letras distintas), `nombre_cercano` (faltas de ortografía y otro
  orden) y `buscar` (para el panel).
- **Expediente:** `registrar_documento` (la versión anterior queda reemplazada), `revisar_documento`,
  `vencer_documentos` (el comprobante dura 3 meses), `marcar_renapo`, `cambiar_grupo` y `dar_baja`.
- **Vistas:**
  - `v_alumnos` y `v_inscritos`;
  - `v_faltantes` (qué documento obligatorio falta validar);
  - `v_matricula_911` (por grado, sexo y edad);
  - `v_resumen_grupo`;
  - `v_alertas`:
    - CURP que no cuadra;
    - fecha distinta a la de la CURP;
    - RENAPO no la encontró;
    - sin CURP;
    - extraedad o menor edad;
    - posible duplicado;
    - RENAPO pendiente.
- **Datos del escaneo (2026-10-26):**
  - `guardar_dato` guarda sin perder lo anterior; `confirmar_dato` es la persona que confirma, corrige o descarta.
  - `relectura` (la auditoría «Volver a leer todo»): lo que la máquina leyó antes de ese expediente queda reemplazado;
    lo de las personas no se toca.
  - `marcar_duplicado`: una lectura casi igual a otra más segura queda reemplazada (`validacion/purificar.py` decide
    cuáles con `duplicados`).
- **Alumnos repetidos (2026-10-26):** `alumnos_repetidos` regresa parejas de alumnos activos con el mismo nombre, con
  una CURP a una letra de la otra, o con el nombre casi igual (0.85) y la misma fecha o sin CURP. Salen en **Por
  revisar**; si es el mismo niño, una persona borra el que sobra, y si no, `marcar_distintos` lo anota para no volver
  a preguntar.
- **Resumen:** `resumen()`, solo números, para copiar a un informe.
- **Biblioteca (2026-10-23):**
  - `isbn13` revisa el dígito y pasa un ISBN-10 a 13; `biblio_codigo` corrige lo que escribe el lector de código
    de barras (`LIB'000001` → `LIB-000001`).
  - `biblio_parecidos` busca títulos parecidos (pg_trgm); de 0.8 para arriba se toma como el mismo libro.
  - `biblio_ejemplares_alta` da de alta los ejemplares y regresa sus etiquetas; `biblio_prestar` revisa la regla
    (los diccionarios y enciclopedias no se prestan) y `biblio_devolver` cuenta los días de atraso.
  - Vistas `v_biblio_titulos` y `v_biblio_prestamos`. Si se borra a un alumno, sus préstamos se quedan con
    "Alumno borrado".

## Comandos (en la PC 4, desde la raíz del repositorio)

```
python -m validacion.base_cerebro                                  # crea o actualiza la base y dice cómo está
python -m validacion.base_cerebro cargar C:\SIDP-datos\lista.pdf   # la lista oficial de la SEP
python -m validacion.base_cerebro informe                          # 911, grupos, alertas y faltantes, sin nombres
python -m validacion.base_cerebro respaldar                        # copia con pg_dump, tal como está (sin aplicar el esquema nuevo)
python -m validacion.base_cerebro borrar --si-borrar-todo          # deja la base vacía (solo a mano, para empezar de nuevo)
```

La versión 1 (tabla `padron_alumno`) se pasa sola a la 2 la primera vez. La tabla vieja se queda
renombrada como `padron_alumno_v1`. El cerebro y el .exe se comunican igual que antes:
- el .exe manda el padrón en `/padron` al conectarse y al guardar listas;
- en `/leer`, cada página regresa con las sugerencias de la base;
- en `/alumnos` (con la clave) el .exe trae los alumnos inscritos por grupo. Lo hace al conectarse al cerebro,
  antes de mandar su padrón, y con el botón **Traer la lista de la PC 4** de Listas de grupo. Un alumno que
  ya estaba en el .exe (misma CURP) toma el nombre de la PC 4, con su bitácora; los demás se agregan a su grupo.
