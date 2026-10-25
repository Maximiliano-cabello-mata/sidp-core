# Plantillas Estructuradas de Formatos Word (`.docx`) — Directivos y Profesores (SEIEM / Zona 49)

Este archivo contiene las plantillas textuales y tabulares exactas extraídas de los formatos Word utilizados en la escuela primaria (**CCT `15DPR3027Z`**, Sector `II`, Zona `49`, SEIEM), completamente anonimizadas y parametrizadas con variables `{{...}}` para su automatización directa en `sidp-core`.

---

## 1. Expediente de Inscripción del Alumno (`FORMATOS DE INSCRIPCION CICLO ESCOLAR.docx`)

Se imprime en **3 páginas** por alumno al inicio del ciclo escolar o en altas por traslado:

### Página 1: Ficha de Inscripción y Datos Médicos / Domicilio
```text
SERVICIOS EDUCATIVOS INTEGRADOS AL ESTADO DE MÉXICO
ESC. PRIM. "{{ESCUELA_NOMBRE}}" | C.C.T.: {{CCT}}
FICHA DE INSCRIPCIÓN — NIVEL EDUCATIVO: PRIMARIA — CICLO ESCOLAR: {{CICLO_ESCOLAR}}

I. DATOS DEL ALUMNO(A):
- GRADO Y GRUPO: {{GRADO_GRUPO}}    - SITUACIÓN: [ ] NUEVO INGRESO  [ ] PROMOVIDO  [ ] REPETIDOR
- APELLIDO PATERNO: {{ALUMNO_PATERNO}}   - APELLIDO MATERNO: {{ALUMNO_MATERNO}}   - NOMBRE(S): {{ALUMNO_NOMBRES}}
- CURP: {{ALUMNO_CURP}}    - FECHA DE NACIMIENTO: {{ALUMNO_FECHA_NAC}}    - EDAD: {{ALUMNO_EDAD}}    - SEXO: {{ALUMNO_SEXO}}
- LUGAR DE NACIMIENTO: {{ALUMNO_ENTIDAD_NAC}}    - NACIONALIDAD: {{ALUMNO_NACIONALIDAD}}
- TIPO DE SANGRE: {{ALUMNO_TIPO_SANGRE}}    - PESO (KG): {{ALUMNO_PESO}}    - TALLA (CM): {{ALUMNO_TALLA}}
- ¿CUENTA CON SERVICIO MÉDICO?: {{SERVICIO_MEDICO_SI_NO}}    - INSTITUCIÓN: {{INSTITUCION_MEDICA}}
- ENFERMEDAD CRÓNICA / ALERGIAS / TRATAMIENTO MÉDICO: {{PADECIMIENTOS_Y_ALERGIAS}}
- ¿UTILIZA LENTES, APARATO AUDITIVO O PRÓTESIS?: {{APOYOS_FISICOS}}
- CONDICIÓN O DISCAPACIDAD (BAP): {{CONDICION_DISCAPACIDAD}}

II. DOMICILIO DEL ALUMNO(A):
- CALLE: {{DOM_CALLE}}   No. EXT: {{DOM_NUM_EXT}}   No. INT: {{DOM_NUM_INT}}   COLONIA: {{DOM_COLONIA}}
- C.P.: {{DOM_CP}}   LOCALIDAD: {{DOM_LOCALIDAD}}   MUNICIPIO: {{DOM_MUNICIPIO}}   ESTADO: {{DOM_ESTADO}}
- ENTRE QUÉ CALLES: {{DOM_ENTRE_CALLES}}   REFERENCIA DEL DOMICILIO: {{DOM_REFERENCIA}}

III. DATOS DE LA MADRE, PADRE O TUTOR(A):
- NOMBRE COMPLETO: {{TUTOR_PATERNO}} {{TUTOR_MATERNO}} {{TUTOR_NOMBRES}}   - PARENTESCO: {{TUTOR_PARENTESCO}}
- CURP: {{TUTOR_CURP}}   - FECHA NAC.: {{TUTOR_FECHA_NAC}}   - EDAD: {{TUTOR_EDAD}}   - ESTADO CIVIL: {{TUTOR_EDO_CIVIL}}
- ESCOLARIDAD: {{TUTOR_ESCOLARIDAD}}   - OCUPACIÓN: {{TUTOR_OCUPACION}}
- TEL. CASA: {{TEL_CASA}}   - CELULAR TUTOR: {{CEL_TUTOR}}   - CELULAR FAMILIAR: {{CEL_FAMILIAR}}
- CORREO ELECTRÓNICO: {{TUTOR_EMAIL}}
- CONTACTO DE EMERGENCIA ADICIONAL: {{CONTACTO_EMERGENCIA_NOMBRE}} ({{CONTACTO_EMERGENCIA_TEL}})

____________________________________________________
NOMBRE Y FIRMA DE LA MADRE, PADRE DE FAMILIA O TUTOR
```

### Página 2: Formato de Autorización de Recolección del Alumno (con copias de INE)
```text
FORMATO DE AUTORIZACIÓN DE ENTREGA DE ALUMNO(A) — CICLO ESCOLAR {{CICLO_ESCOLAR}}

EL (LA) QUE SUSCRIBE, C. {{TUTOR_NOMBRE_COMPLETO}}, EN MI CARÁCTER DE {{TUTOR_PARENTESCO}} DEL ALUMNO(A)
{{ALUMNO_NOMBRE_COMPLETO}} INSCRITO EN EL {{GRADO_GRUPO}}, AUTORIZO A LAS SIGUIENTES PERSONAS MAYORES DE EDAD
PARA RECOGER A MI HIJO(A) A LA HORA DE SALIDA EN CASO DE QUE YO NO PUEDA ASISTIR:

1. PERSONA AUTORIZADA 1: {{AUTORIZADO_1_NOMBRE}} (PARENTESCO: {{AUTORIZADO_1_PARENTESCO}} | TEL: {{AUTORIZADO_1_TEL}})
   [ RECUADRO INE ANVERSO ]                [ RECUADRO INE REVERSO ]
   ________________________________________
   FIRMA DE LA PERSONA AUTORIZADA 1

2. PERSONA AUTORIZADA 2: {{AUTORIZADO_2_NOMBRE}} (PARENTESCO: {{AUTORIZADO_2_PARENTESCO}} | TEL: {{AUTORIZADO_2_TEL}})
   [ RECUADRO INE ANVERSO ]                [ RECUADRO INE REVERSO ]
   ________________________________________
   FIRMA DE LA PERSONA AUTORIZADA 2

____________________________________________________
NOMBRE Y FIRMA DEL TUTOR QUE AUTORIZA
```

### Página 3: Anexo 1 — Carta Responsiva y Autorización de Revisión de Mochila (Gaceta del Gobierno)
```text
G A C E T A   D E L   G O B I E R N O (5 DE SEPTIEMBRE DE 2018, PÁGINA 53)
ANEXO 1: CARTA RESPONSIVA

Nombre de la escuela: ESC. PRIM. "{{ESCUELA_NOMBRE}}" | C.C.T.: {{CCT}}
Lugar y fecha: {{LOCALIDAD}}, {{MUNICIPIO}}, México, a {{FECHA_INSCRIPCION}}.

Autorizo que sea revisada la mochila, bolsa o portafolio de mi hijo(a) {{ALUMNO_NOMBRE_COMPLETO}} del grado {{GRADO}}
grupo {{GRUPO}}, cuando ingrese al plantel escolar o en el momento que las autoridades escolares y el Comité de
Seguridad Escolar lo consideren necesario para salvaguardar la integridad física de la comunidad escolar.
Asimismo, me comprometo a revisar diariamente desde casa los útiles y objetos que porta mi hijo(a).

____________________________________________________
NOMBRE Y FIRMA DE LA MADRE, PADRE DE FAMILIA O TUTOR
```

---

## 2. Oficio de Asignación de Grado y Grupo (`ASIGNACION Y COMISION.docx`)

Se genera **1 oficio foliado por docente** al inicio y cierre del ciclo escolar:

```text
OFICIO No. {{FOLIO_OFICIO}}/{{CICLO_ESCOLAR}}
ASUNTO: ASIGNACIÓN DE GRADO Y GRUPO

Col. {{LOCALIDAD}}, {{MUNICIPIO}}, México, a {{FECHA_TEXTO}}.

C. PROFR.(A) {{DOCENTE_NOMBRE_COMPLETO}}
FILIACIÓN: {{DOCENTE_RFC}} | CURP: {{DOCENTE_CURP}}
CLAVE(S) PRESUPUESTAL(ES): {{DOCENTE_CLAVES_PRESUPUESTALES}}
MTRO.(A) DE GPO. PRIM. FOR.
P R E S E N T E

El que suscribe, Profr. {{DIRECTOR_NOMBRE}}, Director de la Escuela Primaria "{{ESCUELA_NOMBRE}}",
con C.C.T. {{CCT}}, ubicada en {{DOMICILIO_ESCUELA}}, turno {{TURNO_ESCOLAR}}, por medio del presente
le comunica que para el Ciclo Escolar {{CICLO_ESCOLAR}} le ha sido asignado el **{{GRADO_ASIGNADO}}° GRADO, GRUPO "{{GRUPO_ASIGNADO}}"**,
así como la comisión escolar de **{{COMISION_ANUAL}}**.

Sin otro particular, le reitero mi consideración y respeto institucional.

A T E N T A M E N T E
DIRECTOR ESCOLAR

________________________________________
PROFR. {{DIRECTOR_NOMBRE}}
```

---

## 3. Oficio de Funciones Docentes — 24 Fracciones Normativas SEIEM (`Funciones mtros 26 27.docx`)

Se genera **1 oficio foliado por docente** en agosto al iniciar el ciclo escolar, donde cada docente firma de recibido las 24 obligaciones frente a grupo del Manual de Organización de Educación Primaria de SEIEM:

```text
Colonia {{LOCALIDAD}}, {{MUNICIPIO}}, México, a {{FECHA_INICIO_CICLO}}.
Oficio No. {{FOLIO_OFICIO}}/{{CICLO_ESCOLAR}}
Asunto: Funciones docentes.
Ciclo Escolar: {{CICLO_ESCOLAR}}.

PROFR.(A) {{DOCENTE_NOMBRE_COMPLETO}}
FILIACIÓN: {{DOCENTE_RFC}}
CLAVE PRESUPUESTAL: {{DOCENTE_CLAVES_PRESUPUESTALES}}
MTRO.(A) FRENTE A GRUPO ESC. PRIM. "{{ESCUELA_NOMBRE}}" C.C.T. {{CCT}}
P R E S E N T E

El que suscribe, PROFR. {{DIRECTOR_NOMBRE}}, Director de la Escuela Primaria "{{ESCUELA_NOMBRE}}", C.C.T. {{CCT}},
con fundamento en el Manual de Organización de la Escuela de Educación Primaria de SEIEM, le da a conocer las
funciones que deberá desempeñar durante el Ciclo Escolar {{CICLO_ESCOLAR}}:

1. Conducir el proceso de enseñanza-aprendizaje conforme al plan y programas de estudio vigentes (NEM)...
2. Elaborar y presentar al Director el Plan Anual de Trabajo / Plano Didáctico...
3. Cumplir con los propósitos educativos de conformidad con el grado y Fase que le corresponde...
4. Adecuar las tareas educativas a las aptitudes, necesidades e intereses de los alumnos (BAP)...
5. Organizar las actividades educativas diarias disponiendo de los recursos materiales...
6. Participar en la planeación y evaluación del centro escolar y en los Consejos Técnicos Escolares (CTE)...
7. Entablar comunicación respetuosa con padres de familia o tutores...
8. Realizar las evaluaciones diagnósticas, formativas y trimestrales en tiempo y forma...
9. Conservar dentro del plantel la documentación oficial del grupo a su cargo...
10. Cumplir con el calendario y horario escolar vigente ({{HORARIO_LABORAL}})...
11. Asistir puntualmente a la Escuela de Educación Primaria...
12. Elaborar y entregar a la Dirección la documentación de control escolar en los plazos estipulados...
13. Cuidar la disciplina e integridad de los educandos en salones, recreo y salida...
14. Vigilar la asistencia diaria de los alumnos y reportar ausencias e inasistencias reiteradas...
15. Cubrir las guardias semanales de entrada, recreo y salida según el rol institucional...
16. Organizar la ceremonia cívica de honores a la bandera los lunes que corresponda a su grado...
17. Estimular la práctica de valores y convivencia armónica...
18. Participar en los programas de actualización y capacitación convocados por la estructura educativa...
19. Promover con el ejemplo la cultura de la legalidad...
20. Asistir a las reuniones convocadas por la Dirección Escolar...
21. Mantener su salón de clases en óptimas condiciones de orden e higiene...
22. Cuidar la correcta utilización y conservación de los anexos y mobiliario escolar...
23. Participar activamente en las sesiones del Consejo Técnico Escolar (CTE)...
24. Realizar las comisiones y funciones adicionales afines que le encomiende la Dirección Escolar.

A T E N T A M E N T E                          RECIBÍ DE CONFORMIDAD
DIRECTOR ESCOLAR                              DOCENTE FRENTE A GRUPO

_________________________________             _________________________________
PROFR. {{DIRECTOR_NOMBRE}}                    PROFR.(A) {{DOCENTE_NOMBRE_COMPLETO}}
```

---

## 4. Solicitud de Días Económicos (`SOLICITUD DE DIAS ECONOMICOS.docx`)

En escuelas de Tiempo Completo / Doble Plaza, cuando un docente solicita día económico, se genera **una solicitud por cada clave presupuestal** que posea el docente:

```text
Colonia {{LOCALIDAD}}, {{MUNICIPIO}}, México, a {{FECHA_SOLICITUD}}.

PROFR. {{DIRECTOR_NOMBRE}}
DIRECTOR ESCOLAR DE LA ESC. PRIM. "{{ESCUELA_NOMBRE}}" (C.C.T. {{CCT}})
P R E S E N T E

El (La) que suscribe, Profr.(a) {{DOCENTE_NOMBRE_COMPLETO}}, con filiación {{DOCENTE_RFC}}, CURP {{DOCENTE_CURP}}
y clave presupuestal **{{CLAVE_PRESUPUESTAL_INDIVIDUAL}}**, adscrito(a) al C.T. {{CCT}} desempeñando la función de
{{FUNCION_DOCENTE}}, solicita a usted autorización para gozar de **{{NUM_DIAS}} DÍA(S) ECONÓMICO(S)** el(los) día(s)
**{{FECHAS_DIAS_ECONOMICOS}}**, por motivos estrictamente personales, haciendo constar que es el {{ORDINAL_SOLICITUD}}
permiso económico solicitado en el presente ciclo escolar.

Sin más por el momento, agradezco su atención.

A T E N T A M E N T E                         Vo. Bo. DIRECTOR ESCOLAR

_________________________________             _________________________________
PROFR.(A) {{DOCENTE_NOMBRE_COMPLETO}}         PROFR. {{DIRECTOR_NOMBRE}}
```

---

## 5. Constancia Laboral para Personal Docente / Administrativo (`OFICIO NUEVO NO. DELFINO PANDO.docx`)

```text
OFICIO No. {{FOLIO_OFICIO}}/{{CICLO_ESCOLAR}}
ASUNTO: CONSTANCIA LABORAL

Colonia {{LOCALIDAD}}, {{MUNICIPIO}}, México, a {{FECHA_TEXTO}}.

A QUIEN CORRESPONDA:
P R E S E N T E

El que suscribe, PROFR. {{DIRECTOR_NOMBRE}}, Director de la Escuela Primaria "{{ESCUELA_NOMBRE}}", con C.C.T. {{CCT}},
perteneciente a la Zona Escolar {{ZONA}}, Sector Educativo {{SECTOR}}, ubicada en {{DOMICILIO_ESCUELA}}:

H A C E   C O N S T A R

Que el(la) C. PROFR.(A) **{{DOCENTE_NOMBRE_COMPLETO}}**, con RFC **{{DOCENTE_RFC}}**, CURP **{{DOCENTE_CURP}}** y
clave(s) presupuestal(es) **{{DOCENTE_CLAVES_PRESUPUESTALES}}**, presta sus servicios en esta institución educativa
desempeñando la función de **{{FUNCION_DOCENTE}}**, con un horario laboral de **{{HORARIO_ENTRADA}} a {{HORARIO_SALIDA}} horas**
de lunes a viernes, encontrándose activo(a) desde el {{FECHA_ADSCRIPCION_CT}} a la fecha.

Se extiende la presente a petición del(la) interesado(a) para los fines legales y administrativos que le convengan.

A T E N T A M E N T E
DIRECTOR ESCOLAR

________________________________________
PROFR. {{DIRECTOR_NOMBRE}}
```

---

## 6. Acta de Hechos y Acuerdos Escolares (`ACTA DE HECHOS.docx`)

```text
ACTA DE HECHOS Y ACUERDOS

En la localidad de {{LOCALIDAD}}, del municipio de {{MUNICIPIO}}, Estado de México, siendo las {{HORA_INICIO}} horas
del día {{DIA}} de {{MES}} de {{ANIO}}, reunidos en las instalaciones de la Dirección de la Escuela Primaria
"{{ESCUELA_NOMBRE}}" con C.C.T. {{CCT}}, el C. Profr. {{DIRECTOR_NOMBRE}}, Director Escolar; el(la) Profr.(a)
{{DOCENTE_GRUPO}}, docente titular del {{GRADO_GRUPO}}; y el(la) C. {{TUTOR_NOMBRE}}, en su carácter de {{TUTOR_PARENTESCO}}
del alumno(a) {{ALUMNO_NOMBRE}}, se procede a levantar la presente ACTA DE HECHOS con motivo de:

HECHOS:
{{DESCRIPCION_DETALLADA_DE_LOS_HECHOS}}

ACUERDOS Y COMPROMISOS:
1. {{ACUERDO_1}}
2. {{ACUERDO_2}}
3. {{ACUERDO_3}}

Siendo las {{HORA_CIERRE}} horas del mismo día de su inicio, previa lectura de la presente acta, firman al margen y
al calce los que en ella intervinieron para constancia y conformidad.

DOCENTE FRENTE A GRUPO                        MADRE / PADRE O TUTOR(A)
_________________________________             _________________________________
PROFR.(A) {{DOCENTE_GRUPO}}                   C. {{TUTOR_NOMBRE}}

Vo. Bo. DIRECTOR ESCOLAR
_________________________________
PROFR. {{DIRECTOR_NOMBRE}}
```

---

## 7. Reporte Trimestral de Alumnos en Rezago (`ALUMNOS CON REZAGO.docx` / `APROVECHAMIENTO POR GRADO.docx`)

```text
ESCUELA PRIMARIA "{{ESCUELA_NOMBRE}}"
TURNO: {{TURNO_ESCOLAR}} | C.C.T.: {{CCT}} | ZONA: {{ZONA}} | SECTOR: {{SECTOR}}
LISTA DE ALUMNOS CON REZAGO EDUCATIVO (PROMEDIO MENOR A 7.0)
PERIODO: {{PERIODO_TRIMESTRAL}} — CICLO ESCOLAR {{CICLO_ESCOLAR}}

| No. | C.C.T.      | GRADO Y GRUPO | NOMBRE DEL ALUMNO(A)             | PROMEDIO | CAMPO FORMATIVO CON MAYOR REZAGO |
|-----|-------------|---------------|----------------------------------|----------|----------------------------------|
| 1   | {{CCT}}     | {{GRADO_GPO}} | {{ALUMNO_APELLIDOS_Y_NOMBRES}}   | {{PROM}} | {{CAMPO_REZAGO}}                 |

DIRECTOR ESCOLAR
____________________________________
PROFR. {{DIRECTOR_NOMBRE}}
```
