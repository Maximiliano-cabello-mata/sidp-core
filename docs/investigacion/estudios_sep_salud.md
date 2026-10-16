# Qué estudia SIDP de los alumnos y qué pide el gobierno (2026-10-16)

Pedido de Maximiliano: que la extracción saque toda la información útil de cada alumno (es por comodidad,
facilidad y rapidez; la validación ya se hizo en papel) y que el análisis estudie a los alumnos, no los
documentos. El estudio de la IA va dirigido al director y al subdirector.

> **Fuentes.** El entorno de esta investigación bloquea gob.mx y who.int. Lo de la SEP sale de fragmentos de PDF
> oficiales que devuelve el buscador y de prensa (fuentes secundarias). Las tablas de la OMS sí se bajaron
> completas, del repositorio oficial de la OMS en GitHub. Antes de un reporte real, comparen con el cuestionario
> del ciclo vigente.

## Qué sí vale la pena estudiar

| Tema | Qué se cuenta | De dónde sale |
|---|---|---|
| Salud | Estado nutricional con la OMS (delgadez, normal, sobrepeso, obesidad), vista, salud bucal, tipo de sangre, alergias, padecimientos, medicamentos, vacunas, discapacidad | Certificado médico |
| Dónde viven | Municipio, colonia y código postal; cuántos viven en cada lugar | Comprobante de domicilio e INE del tutor |
| Aprovechamiento | Promedio de cada boleta de años anteriores, por grado cursado y por campo formativo; alumnos con menos de 7 | Boletas (una por año: un alumno de 6.° trae cinco) |
| 911 | Alumnos por grado, sexo y edad al 1 de septiembre; grupos; discapacidad por tipo; nacidos en otra entidad o país | Listas, CURP y certificado médico |
| Edad | Extraedad y menor edad por grupo | Fecha de nacimiento |

## Qué no vale la pena estudiar

- Cuántos documentos se subieron o faltan, ni el avance de los expedientes: los documentos se suben y ya.
- La calidad de lectura del escaneo ni el inventario: no hablan de los alumnos (el inventario tiene su pestaña).

## Cuándo un número ya habla de la escuela

Cada área (salud, domicilio, boletas) dice con cuántos alumnos se calculó. Cuando pasa de la mitad, sus
porcentajes ya describen a la escuela y la IA de la PC 4 escribe sola su estudio. Antes de eso, los números
hablan solo de los alumnos ya escaneados.

## Lo que pide el gobierno cada año

| Cuándo | Qué | Qué piden de los alumnos |
|---|---|---|
| Septiembre y octubre | Estadística 911 (cuestionario 911.3, en f911.sep.gob.mx). Desde hace varios ciclos es un solo levantamiento: fin del ciclo anterior e inicio del actual | Alumnos por grado, sexo (nuevo ingreso y repetidores) y edad cumplida al 1 de septiembre (menos de 6, de 6 a 14, 15 y más); grupos por grado; discapacidad y condiciones por tipo, grado y sexo; lengua indígena, nacidos fuera de México y afromexicanos (nuevo en 2025-2026); existencia y promovidos del ciclo anterior; egresados de 6.° por sexo y edad |
| Durante el ciclo | Jornadas "Vive saludable, vive feliz" (SEP, Salud, IMSS y DIF; desde marzo de 2025, permanente desde julio de 2026) | Peso, talla e IMC; agudeza visual (carta de Snellen; lentes gratis si los necesita); salud bucal (caries, flúor). La familia recibe un expediente digital de salud escolar |
| Tres veces al año | Boleta de evaluación (Acuerdo 10/09/23, Nueva Escuela Mexicana) | Calificación de 5 a 10 por campo formativo (Lenguajes; Saberes y pensamiento científico; Ética, naturaleza y sociedades; De lo humano y lo comunitario), promedio final con un decimal, asistencias |
| A principios de año | Preinscripción en el SAID (Estado de México) | CURP y acta; la escuela recibe la lista de asignados |
| Con cada convocatoria | Becas (Beca Rita Cetina) | CURP del alumno, clave de la escuela, datos del tutor |

Tipos de discapacidad y condiciones del 911.3 (2026-2027), que SIDP usa tal cual: ceguera, baja visión,
sordera, hipoacusia, sordoceguera, discapacidad motriz, intelectual, psicosocial y múltiple, trastorno del
espectro autista, TDAH, otras condiciones y aptitudes sobresalientes.

Todavía se capturan a mano porque la base no los guarda: nuevo ingreso o repetidor, lengua indígena,
afromexicanos, promovidos, personal y aulas.

## Estado nutricional (OMS 2007, IMC para la edad, 5 a 19 años)

- z = ((IMC / M)^L − 1) / (L · S), con L, M y S del mes cumplido y el sexo; arriba de 3 o abajo de −3, el ajuste
  de la OMS. Tablas en `validacion/oms.py` (60 a 180 meses), del repositorio oficial
  github.com/WorldHealthOrganization/anthroplus; se compararon con el paquete rcpchgrowth y coinciden.
- Cortes: delgadez severa < −3; delgadez < −2; sobrepeso > +1; obesidad > +2.
- Sin peso y talla, se usa lo que escribió el médico ("sobrepeso", "desnutrición"...).
- Es lo más probable que usen las jornadas de la SEP; no publican sus cortes.

## Boletas de años anteriores

- Nueva Escuela Mexicana (desde 2023-2024): 4 campos formativos y 3 periodos; 1.° acredita por haber cursado.
- Plan 2017 (de 2018-2019 a 2022-2023): 3 periodos por asignatura (Lengua materna, Matemáticas, Conocimiento del
  medio o Ciencias naturales, Historia, Geografía, Formación cívica y ética), más Artes y Educación física.
- Plan 2011 (hasta 2017-2018): 5 bimestres por asignatura; mínimo aprobatorio 6.
- SIDP lee el promedio final, los campos formativos si los trae y la lista de materias; cada hoja es un año y
  sus datos llevan el grado al final (`promedio_3` es el promedio de la boleta de 3.°).

## Fuentes

- SEP, boletín 224 (expediente digital de salud escolar); IMSS, comunicado 390/2025; Infobae, 4 de agosto de 2025.
- Guía de llenado 911 primaria (SEV, 2021-2022); formatos 911.3 2018-2019, 2025-2026 y 2026-2027 (planeacion.sec.gob.mx, f911.sep.gob.mx).
- de Onis y cols., Bull World Health Organ 2007;85:660-7; OMS, IMC para la edad de 5 a 19 años.
- Acuerdo 10/09/23 (DOF 27/09/2023); boletín 90 de la SEP; instructivo de llenado de la boleta 2011-2012.
