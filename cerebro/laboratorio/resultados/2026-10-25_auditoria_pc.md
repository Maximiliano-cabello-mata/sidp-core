# Auditoría de la PC de la escuela (2026-10-25)

Alcance: `Escritorio`, `Documentos` y `Descargas` del usuario, más `C:\SIDP` y `C:\SIDP-datos` (ya cubiertos en informes anteriores).

## 1. Panorama

- **4072** archivos de oficina, **5109.4 MB**.
- Por tipo: `.pdf` 1793, `.docx` 996, `.xlsx` 773, `.png` 228, `.jpg` 102, `.doc` 67, `.xls` 40, `.pptx` 37, `.jpeg` 36.
- Por año de última modificación: 2011: 1, 2019: 6, 2021: 1, 2022: 68, 2023: 169, 2024: 1217, 2025: 1442, 2026: 1168.
- **Duplicados** (mismo nombre base y mismo tamaño, `(1)`, `- copia`): **530** archivos sobrantes = **508.3 MB** recuperables.
- **Temporales/basura** (`~$…`, `_removed`, `merged`, `organized`): **153** archivos.
- **Sin clasificar por nombre**: 1250 (31 %) → el nombre del archivo no alcanza para saber qué es; hay que leer el contenido.

## 2. Qué hay, por categoría

| Categoría | Archivos | MB | Extensiones |
|---|---:|---:|---|
| `otros_sin_clasificar` | 1250 | 1704.4 | .pdf 605, .docx 322, .xlsx 160, .jpg 101, .doc 19, .png 17, .pptx 15, .xls 9, .jpeg 2 |
| `rh_plantilla_layout_cfdi` | 444 | 402.7 | .pdf 358, .xlsx 56, .docx 22, .doc 6, .pptx 2 |
| `oficios_actas_constancias` | 411 | 356.2 | .pdf 135, .docx 133, .xlsx 119, .doc 14, .xls 9, .pptx 1 |
| `formatos_en_blanco` | 259 | 138.0 | .docx 90, .xlsx 90, .pdf 55, .doc 14, .xls 10 |
| `diplomas_eventos` | 248 | 416.7 | .png 204, .pdf 20, .docx 17, .pptx 6, .xlsx 1 |
| `informes_solicitudes_minutas` | 239 | 221.1 | .docx 135, .pdf 66, .xlsx 25, .doc 10, .jpg 1, .xls 1, .pptx 1 |
| `archivos_temporales_basura` | 153 | 95.1 | .xlsx 61, .docx 54, .pdf 33, .doc 4, .pptx 1 |
| `escaneos` | 140 | 1053.6 | .pdf 107, .jpeg 32, .docx 1 |
| `seguimiento_sinavid_siceps` | 132 | 31.2 | .pdf 59, .docx 50, .xlsx 22, .pptx 1 |
| `listas_asistencia` | 110 | 97.0 | .docx 46, .pdf 42, .xlsx 22 |
| `estadistica_911` | 108 | 37.0 | .xlsx 85, .pdf 16, .docx 7 |
| `comites_cooperacion` | 107 | 53.5 | .pdf 44, .xlsx 40, .docx 19, .xls 2, .png 1, .pptx 1 |
| `calificaciones_boletas` | 103 | 78.6 | .xlsx 58, .pdf 23, .docx 21, .xls 1 |
| `planeacion_didactica` | 101 | 151.6 | .docx 53, .pdf 38, .xlsx 5, .pptx 4, .jpeg 1 |
| `expedientes_maestros_rh` | 96 | 176.6 | .pdf 86, .docx 6, .xlsx 4 |
| `nomina_quincena` | 95 | 17.4 | .pdf 75, .docx 10, .png 6, .xlsx 4 |
| `diagnostico_sisat_eia` | 65 | 65.8 | .pdf 26, .xlsx 19, .xls 8, .docx 7, .pptx 5 |
| `salud_dif_proteccion` | 11 | 13.0 | .pdf 5, .docx 3, .xlsx 2, .jpeg 1 |

## 3. Calidad medida en una muestra de 203 archivos

- **PDF** (72 muestreados): 21 (29 %) no traen capa de texto (son escaneos) → solo el lector con visión los puede leer.
- **Excel** (63 muestreados): 24 (38 %) llevan fórmulas; promedio de 52 fórmulas por libro; 7 con gráficos.
- **Word** (64 muestreados): 31 (48 %) son formatos con espacios en blanco para llenar (`____`, `.....`, controles de contenido).

## 4. Ejemplos

Los ejemplos con nombres, rutas y contenido reales **no se publican** (regla 2 de `LEEME.md`). Están en la PC en `C:\SIDP-datos\auditoria\AUDITORIA_PC_REAL_LOCAL.md`. En el repo solo van estadísticas agregadas; los ejemplos sintéticos están en `ejemplos_formatos_escuela/`.

## 5. Qué debe hacer el sistema con esto (hallazgos → mejoras)

| # | Hallazgo | Mejora para SIDP | Valor |
|---|---|---|---|
| 1 | La información vive en cientos de Excel/Word sueltos y copias `(1)`, `- copia` | **Importador de carpeta**: el directivo apunta a una carpeta y SIDP clasifica por contenido (no solo por nombre), detecta duplicados y propone conservar el más reciente | Alto |
| 2 | La mitad de los archivos no se pueden clasificar por nombre | **Clasificador por contenido** (primeras líneas del Word/Excel/PDF + cabeceras) con las categorías de la sección 2 | Alto |
| 3 | Muchos PDF son escaneos sin texto | Cola de lectura con visión (ya existe, 2 lecturas por hoja) y **prioridad** para documentos de alumno | Alto |
| 4 | Los Excel de nómina/quincena, calificaciones y estadística 911 repiten las mismas columnas cada periodo | **Plantillas vivas**: SIDP genera el periodo siguiente desde la base y llena fórmulas; el usuario ya no copia y pega libros | Alto |
| 5 | Formatos Word en blanco (oficios, actas, constancias, fichas) | **Biblioteca de formatos con campos** que se llenan solos desde alumno/docente/escuela (ya hay 11 plantillas Word de ejemplo) | Alto |
| 6 | Expedientes de maestros y RH (RFC, CURP, CFDI, comprobantes) en carpetas por nombre | **Expediente de personal** igual que el de alumno: lectura automática, vencimientos (cédula, constancias) y faltantes | Medio |
| 7 | Seguimiento SINAVID/SICEPS, padrones y bases de datos en Excel | **Exportadores** con el layout oficial exacto; validación antes de subir a la plataforma oficial | Alto |
| 8 | Archivos temporales `~$` y `_removed/merged/organized` | **Limpieza segura** (papelera, nunca borrado directo) con vista previa | Bajo |
| 9 | Respaldo: Descargas es de facto el archivo general | **Respaldo con versión** y una sola copia canónica por documento | Medio |
| 10 | Los datos del alumno se repiten en cada formato | **Un solo dato, muchos formatos**: capturar una vez y que todo se llene | Alto |

## 6. Orden sugerido

1. Clasificador por contenido + detección de duplicados (la base de todo lo demás).
2. Expediente de personal.
3. Plantillas vivas de periodo (quincena, calificaciones, 911).
4. Exportadores con layout oficial (SINAVID/SICEPS/PROEEB).
5. Limpieza y respaldo con versión.
