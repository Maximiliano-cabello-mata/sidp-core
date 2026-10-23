# Qué datos de cada alumno pide el gobierno, y con qué catálogos (2026-10-23)

> **Lo que se decidió con esta investigación (2026-10-23).** SIDP guarda de cada alumno solo lo de esta página, con
> estos catálogos (`validacion/estandar.py`). En salud, Maximiliano eligió **«Solo lo necesario»**: discapacidad o
> condición (para el 911), alergias, medicamentos, padecimientos y contacto de emergencia. Peso, talla, IMC, vista,
> salud bucal, tipo de sangre y vacunas ya no se sacan ni salen en el Excel ni en el estudio; lo que ya estaba
> guardado no se borra. Con estos datos salen el 911 (Excel con su hoja «Revisión»), las constancias de inscripción,
> las listas de grupo, «Lo que la maestra debe saber» y la lista de «Vive saludable» (`validacion/documentos.py`).

Pedido del dueño: que SIDP guarde **un solo conjunto fijo de datos por alumno**: los que pide el gobierno, con
sus catálogos y formatos, y que con ellos salgan los documentos oficiales (911, SAID, boleta, becas).

> **Cómo se hizo y cuánto confiar.** Este entorno bloquea gob.mx, edomex.gob.mx, edugem.gob.mx y también los
> espejos (Scribd, Studocu, Docplayer, Wikipedia, archive.org). Ningún PDF se pudo abrir. Todo lo de abajo
> sale de **fragmentos y resúmenes del buscador** sobre PDF oficiales y notas de prensa. Por eso cada dato lleva
> su nivel de confianza:
>
> - **[O]** el fragmento viene de un PDF o portal oficial, pero solo se vio el fragmento.
> - **[S]** fuente secundaria: prensa, blogs docentes, Studocu o Scribd.
> - **[V]** verificado aquí: se descargó y se leyó el código (solo la biblioteca python-stdnum, desde PyPI).
> - **[?]** no se pudo confirmar. Preguntarlo a la supervisión o a estadística antes de construir.
>
> Se leyeron antes, para no repetirlas: `docs/investigacion/sistemas-escolares-mexico.md`,
> `docs/investigacion/estudios_sep_salud.md` y `docs/investigacion/reportes_oficiales.md`.

## Conclusiones

1. **Qué pide la norma al inscribir:** acta de nacimiento o un documento equivalente; la CURP si la tiene; la
   Cartilla Nacional de Salud o de Vacunación si la tiene; y la solicitud de inscripción. **Si falta un
   documento, igual se inscribe**: el tutor firma una carta compromiso temporal. No tener CURP nunca impide
   inscribir [O, de ediciones anteriores de las Normas].
2. **El certificado médico no aparece en las Normas.** Desde 2022-2023 hay notas de que la Cartilla lo sustituyó
   [S]. Con el brote de sarampión de 2026, algunos estados (Chihuahua) volvieron obligatoria la cartilla para
   inscribir [S]. **Para el Estado de México no se encontró ninguna disposición** [?].
3. **El INE y el comprobante de domicilio del tutor no son requisito de inscripción** en lo encontrado. Los pide
   la Beca Rita Cetina, pero el tutor los sube él mismo al portal de becas. El SAID pide los datos del domicilio,
   no el comprobante.
4. El **911.3** solo pide totales, pero para contarlos SIDP necesita estos indicadores de cada alumno: sexo,
   fecha de nacimiento, grado, grupo, si repite el grado, de qué escuela viene, si promovió, beca, lengua
   indígena, si nació en otro país, si es afromexicano, y discapacidad o condición por tipo.
5. **Minimización:** la ley obliga a tratar solo los datos "adecuados, relevantes y estrictamente necesarios".
   Ningún formato oficial pide **peso, talla, IMC, vista, salud bucal, tipo de sangre, vacunas dosis por dosis ni
   los números del INE**. Esto choca con lo que hoy extrae SIDP (`estudios_sep_salud.md`); ver la sección 6.
6. Cuidado con un falso amigo: en el 911, **"nuevo ingreso" quiere decir que el alumno no repite el grado**, aunque
   ya estuviera en la escuela. Lo contrario es "repetidor". En SIDP, `inscripcion.tipo = 'nuevo_ingreso'`
   significa "nuevo en la escuela", que es otra cosa. Para el 911 hace falta el dato "repite el grado".

---

## 1. Normas de control escolar (SEP, DGAIR)

**Versión.** No se encontró una edición 2024-2025, 2025-2026 ni 2026-2027 publicada. Lo más reciente que apareció:

- "Normas de Control Escolar 2023-2024", una copia en Scribd de 39 páginas que no se pudo abrir [S].
- El oficio circular DGAIR 133/2024 (6 de agosto de 2024), con recomendaciones de inscripción y reinscripción para
  2024-2025, listado por la AEFCM [O, solo el título].
- El Acuerdo 10/09/23 (DOF 27/09/2023), que fija evaluación, acreditación, promoción y certificación y deroga el
  11/03/19 [O].

Los "Lineamientos de los procesos de control escolar" del Estado de México (Gaceta del Gobierno, 30/04/2025) son
**solo para media superior**, así que no aplican a una primaria [O].

### Inscripción

| Tema | Qué dice | Confianza |
|---|---|---|
| Edad para 1.º | 6 años cumplidos al 31 de diciembre del año en que empieza el ciclo; sin dispensa de edad | [O], Normas 2008-2009 y otras ediciones |
| Edad en el SAID 2026 | 1.º de primaria: de 6 a 14 años cumplidos al 31/12/2026 | [S], prensa |
| Documentos | Copia certificada del acta de nacimiento o documento equivalente; CURP si la tiene; Cartilla Nacional de Vacunación o de Salud si la tiene; solicitud de inscripción | [O], ediciones anteriores |
| Documentos equivalentes al acta | Carta de naturalización, acta de adopción o de reconocimiento, pasaporte, certificación consular, documento migratorio, cédula o documento nacional de identidad, certificado de nacionalidad | [O], copia estatal de las Normas |
| Alumnos nacidos fuera | Desde 2015-2016 no se exige el acta apostillada ni legalizada. Derecho a inscribirse sin importar la situación migratoria. El nombre se registra como viene en el documento extranjero | [O], SEP y SEDU Coahuila |
| CURP | "En ningún caso la ausencia de la CURP obstaculizará el acceso"; la autoridad educativa gestiona la que falte | [O], ediciones anteriores |
| Cartilla de salud | "La falta de la documentación... no será obstáculo para el ingreso"; el director orienta al tutor para tramitarla gratis (norma 31.2 de una edición anterior) | [O], ediciones anteriores |
| Documentos faltantes | El director inscribe si el tutor firma una **Carta-Compromiso Temporal** | [O] |
| Certificado médico | No aparece en las Normas. En 2022 la Cartilla lo sustituyó (circular en CDMX según Time Out y El Financiero) | [S] |
| Cartilla en 2026 | Chihuahua la exige para julio de 2026 (sarampión). Algunas notas lo presentan como requisito nacional de la SEP, pero no citan ningún lineamiento federal | [S], contradictorio |
| Edomex | No se encontró una regla propia sobre certificado médico ni cartilla | [?] |
| CURP biométrica | Segob, RENAPO y la SEP dicen que no se exige para inscribir; la escuela debe aceptar la CURP de siempre | [S] |

### Acreditación, promoción y certificación (Acuerdo 10/09/23)

| Tema | Qué dice | Confianza |
|---|---|---|
| Periodos | 1.º: del inicio del ciclo al último día hábil de noviembre. 2.º: de diciembre al último día hábil de marzo. 3.º: de abril al fin del ciclo | [O] y [S] |
| Escala en primaria | Números enteros. 1.º de 6 a 10; de 2.º a 6.º de 5 a 10. Cada campo formativo lleva observaciones | [S]. **Contradice** `sistemas-escolares-mexico.md`, que dice "6 a 10 en 1.º y 2.º" [?] |
| Promoción | 1.º acredita con haber cursado el grado. De 2.º a 6.º hace falta un promedio final mínimo de 6.0 en los campos formativos | [S] |
| Asistencia | El glosario del Acuerdo dice que no es criterio de evaluación. Algunos apuntes hablan de un 80 % | [S], contradictorio |
| Boleta (art. 7) | Nombre del alumno, nivel y grado; datos de la escuela; nombre del docente que registra. En primaria: los campos formativos, tres evaluaciones parciales y una final por cada uno, con observaciones | [O], fragmento |
| Inasistencias en la boleta | No se confirma que el art. 7 las pida. Una nota de 2020 dice que el MIGE captura inasistencias de 3.º a 6.º | [?] y [S] |
| Certificado | El Certificado de Educación Primaria se expide **en versión electrónica**; su diseño y contenido los fijan las Normas de Control Escolar | [O]. Campos exactos [?]; según la investigación previa, el MIGE da certificados con QR por CURP |

### Formatos oficiales

| Formato | Para qué | Campos | Confianza |
|---|---|---|---|
| Solicitud de inscripción | Base del expediente | No se encontró el formato vigente | [?] |
| IAE (Inscripción y Acreditación Escolar), de 1.º a 6.º | Antes era el registro de inscripción de primaria; el director copiaba los datos del acta | De las Normas 2009-2013. Hoy lo sustituye la captura en el MIGE | [O], viejo |
| Carta-Compromiso Temporal | Cuando falta un documento | Documento que falta y plazo | [O] |
| Boleta de evaluación | Tres periodos y la final | Ver art. 7 arriba. Se descarga en el SIGED con la CURP; la digital vale igual que la impresa | [O] y [S] |
| Informe de Calificaciones de Estudios Parciales | Traslado a mitad del ciclo | Calificaciones hasta la fecha de baja | [O], ediciones anteriores; campos [?] |
| Certificado de Educación Primaria | Al terminar 6.º | Electrónico; campos [?] | [O] |
| Constancia de inscripción | La piden las familias para la beca | CCT a la vista, nombre, CURP, grado y ciclo | [S] |

---

## 2. Cuestionario 911.3 (primaria general)

**Ciclo vigente.** Ya están publicados los formatos **2026-2027**: f911.sep.gob.mx/2026-2027/.../PRIMARIA.pdf
y la copia de planeacion.sec.gob.mx [O]. Desde hace varios ciclos es **un solo levantamiento** al inicio de cursos
que también recoge el fin del ciclo anterior.

**Fechas de captura 2026.** Puebla: del 5 al 30 de octubre. Tamaulipas: hasta el 15 de octubre [O, portales
estatales]. **Edomex [?]**: preguntar hoy mismo, porque probablemente ya está abierto.

**Cortes de fecha.** Inscritos = altas menos bajas hasta el **30 de septiembre** [O]. Edad = **años cumplidos al
1 de septiembre** [O, guía de llenado de Veracruz 2023-2024].

**Edades.** "Menos de 6 años", luego cada edad de 6 a 14 años, y "15 años y más" [O].

Las secciones cambian de número de un año a otro [O]. El orden que se encontró en 2025-2026 y 2026-2027:

| Sección | Qué pide | Desgloses | Dato de SIDP por alumno |
|---|---|---|---|
| I. Existencia y promovidos (fin del ciclo anterior) | Alumnos existentes al cierre del ciclo, y promovidos | Grado, sexo y grupos; además hablantes de lengua indígena, nacidos fuera de México, afromexicanos o afrodescendientes, y discapacidad, neurodivergencia u otras condiciones. En promovidos aparecen también aptitudes sobresalientes | `existencia_fin_ciclo`, `promovido` y las banderas de inclusión |
| I. (continuación) Egresados | Promovidos de 6.º, por sexo y edad | Sexo y edad | `promovido` en 6.º y fecha de nacimiento |
| II. Alumnado que viene de otra escuela | Alumnos llegados de otra escuela | Sexo y grado; de la misma entidad, de otra entidad o de otro país | `procedencia` |
| III. Becas | Alumnos con beca y sin beca | Sexo; cuántos con discapacidad; cuántos hablan lengua indígena. Solo becas en dinero; si tiene varias, cuenta la de mayor monto. Origen: federal (incluye Rita Cetina), estatal, municipal, fundación o asociación civil, la propia escuela, particular, otro | `beca_origen` |
| IV. Alumnado y grupos (inicio del ciclo) | Inscritos al 30 de septiembre | Grado, sexo, nuevo ingreso y repetidores, edad. Grupos por grado | `sexo`, `fecha_nacimiento`, `grado`, `grupo`, `repite_grado` |
| Discapacidad (en 2026-2027 es el reactivo 9) | Alumnos con discapacidad, neurodivergencia u otras condiciones | Grado, sexo y tipo (catálogo abajo) | `condiciones_911` |
| Personal, aulas, libros, infraestructura | No son datos de alumnos | — | Fuera de este diccionario |

**Reprobados.** El 911 no los pide directamente. "No promovidos" sale de restar existencia menos promovidos
(deducción propia, no texto del formato).

**Catálogo de discapacidad y condiciones.**

- Confirmado en los fragmentos del formato de primaria 2026-2027 [O]: ceguera, baja visión, sordera,
  sordoceguera, discapacidad motriz, discapacidad intelectual, discapacidad psicosocial, trastorno del espectro
  autista, discapacidad múltiple y otras condiciones.
- **No confirmado en el de primaria [?]:** hipoacusia y TDAH. Sí aparecen en el formato CAM 2025-2026 y en el de
  USAER, junto con "doble excepcionalidad". `estudios_sep_salud.md` sí los pone en el 911.3 2026-2027.
- Aptitudes sobresalientes: aparecen en el desglose de promovidos [S]. USAER las divide en intelectual, artística,
  psicomotriz, socioafectiva y creativa [O].

**Tres dudas que no resuelve ningún formato encontrado [?]:**

- Cómo se reporta a un alumno con sexo **X** en un formato que solo pide hombres y mujeres.
- Si el 911 de primaria **general** pide la lengua indígena concreta o solo cuántos la hablan. El 911 de educación
  indígena sí pide la lengua.
- Si "nacidos fuera de México" se desglosa por país.

---

## 3. SAID, MIGE, SIGED y SIIE

### SAID (preinscripción del Edomex)

- **Ciclo 2026-2027:** registro en línea del 9 de febrero al 20 de marzo de 2026, por letra del primer apellido;
  resultados el 31 de julio; listados en cada escuela el 3 de agosto; segunda fase (cambios de escuela y nuevo
  ingreso) del 6 al 26 de agosto [S, varias notas que coinciden].
- **Portal:** said.edugem.gob.mx. La autoridad es la SECTI (Secretaría de Educación, Ciencia, Tecnología e
  Innovación del Edomex).
- **Quién lo llena:** el tutor. La escuela no captura en el SAID. **Descarga la lista de asignados en el MIGE**,
  en Preinscripciones > Resultados (guía oficial "Guia_descarga_alumnos_asignados_Said.pdf") [O].

Datos que captura el SAID [S: Manual de Preinscripciones MIGE, febrero de 2024, copia en Studocu]:

| Bloque | Campos |
|---|---|
| Aspirante | CURP. Al escribirla, RENAPO llena solo el nombre, la fecha de nacimiento y el sexo, y no se pueden editar. El grado se calcula con el año de nacimiento |
| Domicilio | Municipio, colonia, localidad y código postal (listas desplegables cuando no se llenan solos) |
| Padre o tutor | CURP, apellidos, nombres, fecha de nacimiento, nivel educativo y correo (se escribe dos veces). Datos de la madre cuando ella es la tutora |
| Hermanos | CURP del hermano inscrito en la escuela que se pide |
| Escuelas | De 2 a 5 escuelas cercanas al domicilio |
| Privacidad | El tutor acepta el aviso de privacidad antes de empezar |
| Comprobante | Folio, indispensable para ver resultados; luego la hoja de resultados, que se presenta en la escuela asignada |
| Segunda fase | CURP del aspirante, datos del tutor y CCT; a veces también acta y domicilio [S] |

### MIGE (sistema de control escolar del Edomex)

- **Inscripción:** se escribe la CURP y el sistema consulta a RENAPO. Se capturan los datos de contacto y se pulsa
  "Registrar", que genera un comprobante de inscripción [O, guía oficial de inscripción por infraedad, extraedad,
  extemporánea y traslado (TESI)].
- **Casos especiales** (infraedad, extraedad, extemporáneos, traslados): **un solo PDF con todos los documentos
  del alumno**; los autorizan el supervisor y la subdirección regional [O].
- **Evaluación:** el docente captura calificaciones e inasistencias por periodo [S, nota de 2020]. Boletas en
  PDF; certificados con QR [O, guías oficiales; ver la investigación previa].
- **Plantillas de Excel o carga masiva: no se encontró ninguna** para alumnos ni calificaciones del MIGE. El único
  Excel oficial que apareció es del micrositio EDIEMS de evaluación diagnóstica 2025-2026, que es otro sistema y
  tiene su propia estructura [O].

### SIGED (SEP, nacional)

- Es la plataforma nacional; la llave es la **CURP**. La alimentan los sistemas estatales (en el Edomex, el MIGE)
  [O].
- Muestra nombre, CURP, nivel, escuela, grado, grupo, turno, historial y fecha de la última actualización [S].
- La Beca Rita Cetina cruza sus datos con el SIGED para comprobar que el alumno está inscrito. **Si un dato está
  mal, la familia debe ir a la escuela**, que lo corrige en el sistema estatal [S].
- No se encontró la lista oficial de campos del alumno (lineamientos del Acuerdo 07/03/18, DOF 20/03/2018) [?].

### SIIE

**SIIE Web es el sistema de la AEFCM (Ciudad de México)** y también hay un SIIE en Tamaulipas. **No aplica al
Edomex** [O]. Su guía de inscripción sirve solo para comparar: arma la CURP con el nombre, la fecha de nacimiento,
la entidad y el sexo, y deja completarla después.

---

## 4. Becas y "Vive saludable, vive feliz"

### Beca Universal Rita Cetina en primaria (nueva en 2026)

| Tema | Qué se sabe |
|---|---|
| Fechas | Primer registro de primaria: del 2 al 19 de marzo de 2026 [S]. **Nuevo registro de primaria y secundaria: del 26 de octubre al 6 de noviembre de 2026**, en becaritacetina.gob.mx con Llave MX (Programas para el Bienestar, nota del 9/10/2026) [O, fragmento] |
| Monto | $2,500 por alumno de primaria, un pago por ciclo, para útiles y uniformes [S, varias fuentes] |
| Quién registra | El padre, la madre o el tutor, no la escuela |
| Datos del tutor | CURP certificada, identificación oficial (INE, pasaporte, cartilla militar, credencial del INM o licencia), comprobante de domicilio de hasta 3 meses, celular, correo y cuenta Llave MX [S] |
| Datos del alumno | CURP certificada (que coincida con el acta) y la CCT de la primaria [S] |
| Qué hace la escuela | Que nombre, CURP, grado y grupo estén bien en el MIGE, porque llegan al SIGED. Dar constancia de inscripción con la CCT. La escuela no guarda nada de la beca más que lo que pide el 911 (si tiene beca y de dónde) |
| Beca Benito Juárez | Es de media superior; no aplica a primaria |

Hay sitios no oficiales que imitan el portal de la beca. Conviene avisar a las familias que el único portal es
becaritacetina.gob.mx.

### "Vive saludable, vive feliz" (SEP, Salud, IMSS-Bienestar y DIF)

- **Consentimiento informado:** el maestro lo entrega y el tutor lo firma, para medir peso y talla, revisar boca
  y vista, y aplicar flúor [O, recomendaciones para familias en vidasaludable.gob.mx].
- **Datos del consentimiento:** del alumno, nombre completo, edad, grado, grupo y CURP; del tutor, nombre, firma,
  correo y teléfono. El formato cita la LGPDPPSO [O].
- **Resultados:** los guarda el **sector salud** en el Expediente Digital de Salud Escolar. La familia lo baja en
  resultados.vidasaludable.sep.gob.mx con Llave MX, la CURP del alumno y el teléfono o correo del consentimiento.
  El expediente trae fecha, nombre, CURP, edad, grado, grupo, y clave y nombre de la escuela [S, SEP citada por
  prensa, julio de 2025].
- **Ciclo 2025-2026:** cerró el 1 de julio de 2026, con 10.8 millones de alumnos atendidos [O, boletín IMSS]. No
  se encontraron las fechas de 2026-2027 [?].
- **Consecuencia para SIDP:** a la escuela solo se le pide la lista (nombre, CURP, grado, grupo) y repartir y
  juntar los consentimientos. **Los resultados de salud no tienen que quedarse en SIDP.**

---

## 5. Catálogos

| Catálogo | Valores | Fuente y confianza |
|---|---|---|
| Entidad de nacimiento (CURP, posiciones 12 y 13) | 33 claves: AS Aguascalientes, BC Baja California, BS Baja California Sur, CC Campeche, CL Coahuila, CM Colima, CS Chiapas, CH Chihuahua, DF Ciudad de México, DG Durango, GT Guanajuato, GR Guerrero, HG Hidalgo, JC Jalisco, MC Estado de México, MN Michoacán, MS Morelos, NT Nayarit, NL Nuevo León, OC Oaxaca, PL Puebla, QT Querétaro, QR Quintana Roo, SP San Luis Potosí, SL Sinaloa, SR Sonora, TC Tabasco, TS Tamaulipas, TL Tlaxcala, VZ Veracruz, YN Yucatán, ZS Zacatecas, **NE nacido en el extranjero** | [V] las 33 claves (python-stdnum 2.2, `stdnum/mx/curp.py`). DF, JC y NE también [S]. Qué estado va con cada clave: conocimiento general |
| Entidad, clave INEGI (para domicilios) | 01 Aguascalientes … 09 Ciudad de México … **15 México** … 32 Zacatecas | 15 confirmado [O]. El resto: conocimiento general; usar el Catálogo Único de Claves Geoestadísticas del INEGI |
| Municipio, clave INEGI | **15122 Valle de Chalco Solidaridad** [O, INEGI]; 15025 Chalco [?] | INEGI, Marco Geoestadístico |
| Sexo | **H** hombre, **M** mujer, **X** no binario (CURP, posición 11) | [S]: CONTPAQi y guías de CURP; primeras CURP con X desde 2022-2023. Ojo: python-stdnum rechaza la X [V]; el 911 solo pide hombres y mujeres [?] |
| CURP, formato | 18 caracteres: 4 letras, fecha AAMMDD, sexo, entidad, 3 consonantes internas, un carácter que distingue el siglo (dígito si nació antes de 2000, letra desde 2000) y un dígito verificador | [V], `stdnum/mx/curp.py`. Dígito: con el alfabeto `0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ`, suma = Σ valor × (18 − posición) en los primeros 17, desde la posición 0; dígito = (10 − suma mod 10) mod 10 |
| Discapacidad y condiciones (911) | Ceguera, baja visión, sordera, sordoceguera, motriz, intelectual, psicosocial, TEA, múltiple, otras condiciones; hipoacusia y TDAH [?] | Sección 2 |
| Aptitudes sobresalientes | Sí o no; tipos: intelectual, artística, psicomotriz, socioafectiva, creativa (USAER) | [O], USAER |
| Lengua indígena | Catálogo de las Lenguas Indígenas Nacionales del INALI (DOF 14/01/2008): 11 familias, 68 agrupaciones, 364 variantes. Para SIDP alcanza la agrupación | [O], INALI y anexo 3 del SNIEG |
| País de nacimiento | Propuesta: ISO 3166-1 alfa-3 (MEX, USA, GTM…). El 911 pide "nacidos fuera de México"; la CURP dice NE | Propuesta propia; no se encontró un catálogo SEP [?] |
| Afromexicano | Autoadscripción declarada por el tutor: sí, no, no declara | Lo pide el 911 desde 2025-2026; catálogo propio |
| Procedencia | Misma escuela; otra escuela de la misma entidad; de otra entidad; de otro país | 911, sección II [O] |
| Origen de la beca | Federal (incluye Rita Cetina), estatal, municipal, fundación o asociación civil, la propia escuela, particular, otro | 911, sección III [O] |
| Parentesco | El SAID solo distingue padre, madre o tutor. Propuesta: madre, padre, tutor legal, otro familiar a cargo | No se encontró un catálogo escolar oficial [?] |
| Documento de identidad del alumno | Acta mexicana; acta extranjera; uno de los equivalentes de la sección 1 | Normas [O] |
| Identificación del tutor | INE, pasaporte, cartilla militar, credencial del INM, licencia | Beca [S] |
| Campos formativos | Lenguajes; Saberes y pensamiento científico; Ética, naturaleza y sociedades; De lo humano y lo comunitario | Plan 2022 / Acuerdo 10/09/23 |
| Tipo de sangre | ABO y Rh | **Ningún formato oficial lo pide**; ver la sección 6 |

---

## 6. Datos personales: LGPDPPSO y la ley del Edomex

**Qué ley aplica.** La escuela pública es parte de un sujeto obligado, la secretaría estatal. Aplica la **Ley
General de Protección de Datos Personales en Posesión de Sujetos Obligados**, nueva ley del DOF del 20/03/2025, con
una reforma registrada el 14/11/2025 en el portal de Diputados [O, fragmento]. En el estado aplica la **Ley de
Protección de Datos Personales en Posesión de Sujetos Obligados del Estado de México y Municipios**. El Infoem
siguió operando en 2025 (aprobó el Programa Estatal 2025-2027) [O]. No se encontró si el estado ya armonizó su ley
con la de 2025 [?].

| Tema | Qué dice | Confianza |
|---|---|---|
| Principios | Licitud, finalidad, lealtad, consentimiento, calidad, proporcionalidad, información y responsabilidad | [O]; un resumen lo ubica en el art. 5 y otro en el art. 10 [?] |
| **Proporcionalidad (minimización)** | "El responsable sólo deberá tratar los datos personales que resulten **adecuados, relevantes y estrictamente necesarios** para la finalidad que justifica su tratamiento" | [O]. Es el art. 25 en la ley de 2017; un resumen lo pone en el art. 19 de la de 2025 [?]. La ley del Edomex lo tiene en su art. 26 [O] |
| Datos sensibles | Los de la esfera más íntima, o cuyo mal uso pueda causar discriminación o un riesgo grave. Incluye **origen racial o étnico** y **estado de salud presente o futuro** | [O], ley de 2025 |
| Regla para los sensibles | "Por regla general no podrán tratarse datos personales sensibles, salvo que se cuente con el consentimiento expreso…" (art. 7; las excepciones no se pudieron leer) | [O], fragmento. La ley de 2017 pedía consentimiento expreso **y por escrito** |
| Menores | "Se deberá privilegiar el **interés superior de la niña, el niño y el adolescente**". El consentimiento y los derechos ARCO de un menor se ejercen según las reglas de representación del derecho civil, es decir, por el padre, la madre o el tutor | [O], fragmento |
| Aviso de privacidad | Integral y simplificado. El simplificado (art. 22 de la ley de 2025) lleva las fracciones I, IV, VII y VIII del artículo anterior y dice dónde consultar el integral. Se pone a disposición desde que se recaban los datos y debe señalar cuáles son sensibles | [O], fragmento |

### Qué implica para SIDP

1. **Cada campo necesita una finalidad escrita** en el aviso de privacidad: inscripción, control escolar, 911,
   boleta, certificado, contacto con el tutor. Un campo que no sirve a ninguna de ellas no se guarda.
2. **Sensibles en SIDP:** discapacidad y condición, lengua indígena, afromexicano, alergias y medicamentos si se
   decide guardarlos. Van en una tabla aparte con permiso propio (como `alumno_salud`), con consentimiento
   expreso del tutor y registro de quién los vio.
3. **Lo que el 911 solo usa en totales:** guardar la marca, no el documento. Por ejemplo "discapacidad: TEA", no el
   diagnóstico ni el certificado del especialista.
4. **Lo que nadie pide** (peso, talla, IMC, vista, salud bucal, tipo de sangre, vacunas dosis por dosis, número de
   seguridad social) no debe extraerse ni guardarse. Las jornadas "Vive saludable" ya los miden y los guardan en
   el sector salud. **Esto contradice** el estudio de salud de `estudios_sep_salud.md`. Si la dirección quiere
   mantener ese estudio, necesita una finalidad declarada en el aviso, el consentimiento expreso del tutor, y
   guardar solo totales por grupo, borrando los valores de cada alumno.
5. **Documentos escaneados:** el INE y el comprobante de domicilio traen mucho más de lo necesario (clave de
   elector, CIC y OCR, foto, firma, consumo). Hay que extraer lo que hace falta, marcar "verificado" y decidir con
   la supervisión si se conserva la imagen [?].
6. **Nada biométrico:** ni fotos de la CURP biométrica, ni huellas, ni firmas digitalizadas como dato.
7. **Plazo de conservación:** no se encontró un plazo oficial para expedientes de primaria [?]. Preguntar a la
   supervisión o al área de archivo.

---

## (a) Diccionario de datos propuesto

En la columna "Guardar": **Sí**; **Sí (S)** = dato sensible, en tabla restringida y con consentimiento; **Derivado** =
se calcula y no se guarda aparte; **No** = no guardar, por minimización.

### Alumno: identidad

| Campo | Definición | Formato o catálogo | Trámite o formato oficial | Documento de origen | Obligatorio | Guardar |
|---|---|---|---|---|---|---|
| `curp` | Clave Única de Registro de Población | 18 caracteres; ver sección 5 | Llave del MIGE y del SIGED; SAID; beca; Vive saludable; boleta; certificado | Constancia de CURP o acta reciente | Sí, pero su falta no impide inscribir | Sí |
| `curp_estado` | Si la CURP ya se comprobó en RENAPO | `validada` / `pendiente` / `sin_curp` | MIGE (consulta RENAPO); beca (pide CURP certificada) | — | Sí | Sí |
| `primer_apellido`, `segundo_apellido`, `nombres` | Nombre legal | Como en RENAPO; si no hay CURP, como en el acta o en el documento extranjero | Todos | Acta / CURP | Sí (segundo apellido si lo tiene) | Sí |
| `fecha_nacimiento` | Fecha de nacimiento | AAAA-MM-DD | 911 (edad al 1 de septiembre); edad de ingreso (al 31 de diciembre); SAID | Acta / CURP | Sí | Sí (y comprobar que coincide con la CURP) |
| `sexo` | Sexo legal | H / M / X | 911 (hombres y mujeres; cómo cuenta la X [?]); MIGE | Acta / CURP | Sí | Sí |
| `entidad_nacimiento` | Estado donde nació | Clave RENAPO de 2 letras; NE = extranjero | 911 (nacidos fuera de México) | CURP (posiciones 12 y 13) o acta | Sí | Derivado de la CURP; se guarda solo si no hay CURP |
| `pais_nacimiento` | País, si nació fuera de México | ISO 3166-1 alfa-3 (propuesta) | 911, sección I | Acta extranjera o documento equivalente | Solo si es NE | Sí |
| `nacionalidad` | Nacionalidad | — | Ningún formato encontrado la pide; el 911 pregunta por el país de nacimiento | — | No | **No** |
| `documento_identidad_tipo` | Qué documento presentó | Acta mexicana / acta extranjera / equivalente (sección 1) | Expediente de inscripción (Normas) | El documento mismo | Sí | Sí (tipo y fecha de entrega) |
| Número de acta, libro, foja, oficialía, CRIP, identificador electrónico | Datos registrales del acta | — | Nadie los pide | Acta | No | **No** |
| Padres, abuelos y testigos que aparecen en el acta | Datos de terceros | — | Nadie los pide | Acta | No | **No** (solo se registra al tutor) |
| Fotografía del alumno | — | — | No se encontró ningún formato vigente que la pida | — | No | **No** |

### Alumno: inscripción y trayectoria (un renglón por ciclo)

| Campo | Definición | Formato o catálogo | Trámite o formato oficial | Documento de origen | Obligatorio | Guardar |
|---|---|---|---|---|---|---|
| `ciclo` | Ciclo escolar | `2026-2027` | Todos | — | Sí | Sí |
| `cct` | Clave de la escuela | 10 caracteres; un dato de la escuela, no del alumno | MIGE; 911; beca; constancias | — | Sí | Sí (una sola vez) |
| `turno` | Turno | Matutino / vespertino / otros (catálogo SEP [?]) | 911; boleta | — | Sí | Sí (del grupo) |
| `grado`, `grupo` | Grado y grupo | 1 a 6; letra | 911 (grupos por grado); boleta; Vive saludable | — | Sí | Sí |
| `repite_grado` | Si cursa el grado por segunda vez | sí / no | 911: "nuevo ingreso" = no repite; "repetidor" = sí repite | Boleta del ciclo anterior | Sí | Sí. **Hoy falta en SIDP** |
| `procedencia` | De dónde llegó | Misma escuela / otra de la entidad / otra entidad / otro país | 911, sección II; traslado en el MIGE | Boleta o certificado anterior | Sí | Sí |
| `cct_procedencia` | Clave de la escuela anterior | 10 caracteres | Traslado; SAID segunda fase | Boleta anterior | Si viene de otra escuela | Sí |
| `ultimo_grado_acreditado`, `promedio_ultimo_grado`, `ciclo_ultimo_grado` | Lo que acredita la boleta anterior | Grado de 1 a 6; promedio con un decimal | Inscripción en 2.º a 6.º | Boleta anterior | Sí, de 2.º en adelante | Sí |
| Calificaciones por campo de cada boleta anterior | Historial completo | — | Ningún formato lo pide; el SIGED ya lo tiene | Boletas | No | **No** (basta el último grado) |
| `folio_said` | Folio de la preinscripción | Texto | SAID (lista de asignados) | Hoja de resultados del SAID | Solo en 1.º | Sí |
| `fecha_alta`, `fecha_baja`, `motivo_baja` | Movimientos | Fechas; motivo según catálogo del MIGE [?] | 911 (altas y bajas al 30 de septiembre; existencia al fin del ciclo); MIGE | — | Sí | Sí |
| `documentos` | Lista de documentos con su estado | Pendiente / recibido / validado; con fecha | Normas (carta compromiso) | — | Sí | Sí |
| `carta_compromiso` | Fecha y plazo de la carta | Fecha; documentos que debe | Normas | Carta firmada | Si falta algo | Sí |
| `calificacion[campo][periodo]` | Calificación por campo formativo | Entero de 5 a 10 (1.º: de 6 a 10 [S]); 3 periodos y la final | Boleta; MIGE | Captura del docente | Sí | Sí |
| `observaciones[campo][periodo]` | Observaciones del docente | Texto | Boleta (art. 7) | Captura | Sí | Sí |
| `inasistencias[periodo]` | Faltas | Número | MIGE [S]; si la boleta las pide [?] | Lista de asistencia | Por confirmar | Sí |
| `promedio_final` | Promedio del ciclo | Un decimal | Boleta; promoción | Calculado | Sí | Derivado |
| `promovido` | Si acreditó el grado | sí / no | 911, sección I; boleta final | Calculado | Sí | Sí (queda fijo al cerrar el ciclo) |
| `existencia_fin_ciclo` | Seguía inscrito el último día del ciclo | sí / no | 911, sección I | Calculado con las bajas | Sí | Derivado |
| `egresado` | Promovido de 6.º | sí / no | 911 (egresados por sexo y edad); certificado | Calculado | Sí | Derivado |
| `beca_origen` | Beca en dinero de mayor monto | Catálogo del 911, o "ninguna" | 911, sección III | Lo declara el tutor | Sí | Sí. **No** guardar el monto, la cuenta ni la tarjeta |

### Alumno: inclusión (sensibles)

| Campo | Definición | Formato o catálogo | Trámite o formato oficial | Documento de origen | Obligatorio | Guardar |
|---|---|---|---|---|---|---|
| `condiciones_911` | Discapacidad, neurodivergencia u otra condición | Catálogo del 911 (sección 5); puede ser más de una | 911 (existencia, promovidos, inscritos, becas) | Diagnóstico, USAER o certificado médico, si lo traen | Sí, cuando aplica | **Sí (S)**: solo el tipo |
| `aptitudes_sobresalientes` | Aptitudes sobresalientes | sí / no (y el tipo de USAER) | 911 | Evaluación de USAER | Cuando aplica | Sí (S) |
| `lengua_indigena` | Habla una lengua indígena | sí / no; agrupación del INALI | 911 | Lo declara el tutor en la cédula; no está en ningún documento del expediente | Sí | Sí (S) |
| `afromexicano` | Autoadscripción | sí / no / no declara | 911 (desde 2025-2026) | Lo declara el tutor | Sí | Sí (S) |
| Diagnóstico clínico, CIE-10, nombre del especialista, estudios | Detalle médico | — | Nadie lo pide | Certificado médico, informes | No | **No** |

### Alumno: salud (minimización)

| Campo | Definición | Formato o catálogo | Trámite o formato oficial | Documento de origen | Obligatorio | Guardar |
|---|---|---|---|---|---|---|
| `cartilla_presentada` | Si entregó la cartilla de vacunación o de salud | sí / no | Normas ("si la tiene"); sarampión 2026 | Cartilla | Si la tiene | Sí (solo la marca) |
| `esquema_srp` | Vacuna SRP según la cartilla | completo / incompleto / no revisado | Solo si el estado lo pide [?] | Cartilla | Por confirmar | Solo si llega una instrucción oficial |
| `alergias_medicamentos_atencion` | Lo que el personal debe saber en una emergencia | Texto corto | Ningún formato oficial; finalidad de seguridad del alumno | Lo declara el tutor | No | Opcional (S): solo con consentimiento expreso y finalidad en el aviso |
| `contacto_emergencia` | Persona y teléfono para emergencias | Nombre, teléfono, parentesco | Operativo, no oficial | Tutor | Recomendado | Sí |
| Peso, talla, IMC, agudeza visual, salud bucal | Mediciones | — | Las hace "Vive saludable" y las guarda Salud | Certificado médico | No | **No** |
| Tipo de sangre | Grupo ABO y Rh | — | Nadie lo pide | Certificado médico | No | **No** (como mucho, opcional en el contacto de emergencia con consentimiento) |
| Vacunas dosis por dosis | — | — | Nadie lo pide | Cartilla | No | **No** |
| NSS o derechohabiencia | — | — | Nadie lo pide | — | No | **No** |
| Imagen del certificado médico | — | — | No es requisito según las Normas | — | No | **No** pedirlo; si lo traen, no extraer de él más que `condiciones_911` |

### Domicilio

| Campo | Definición | Formato o catálogo | Trámite o formato oficial | Documento de origen | Obligatorio | Guardar |
|---|---|---|---|---|---|---|
| `domicilio`: calle, número exterior e interior | Dirección del alumno | Texto | MIGE (contacto); localizar a la familia | Comprobante de domicilio / INE | Sí | Sí |
| `colonia`, `localidad`, `codigo_postal` | | Catálogo de asentamientos de SEPOMEX; CP de 5 dígitos | SAID; MIGE | Comprobante | Sí | Sí |
| `municipio`, `entidad` | | Claves INEGI (15025 [?], 15122) | SAID | Comprobante | Sí | Sí |
| Número de servicio, titular, consumo, adeudo | Datos del recibo | — | Nadie los pide | Comprobante | No | **No** |

### Tutor (uno principal y, si hay, otro)

| Campo | Definición | Formato o catálogo | Trámite o formato oficial | Documento de origen | Obligatorio | Guardar |
|---|---|---|---|---|---|---|
| `curp` | CURP del tutor | 18 caracteres | SAID; beca; MIGE | INE (desde 2014 trae la CURP) / constancia | Sí | Sí |
| `primer_apellido`, `segundo_apellido`, `nombres` | | Como en la CURP | SAID; Vive saludable; firmas | INE / CURP | Sí | Sí |
| `parentesco` | Relación con el alumno | Madre / padre / tutor legal / otro familiar a cargo | SAID (padre, madre o tutor) | Acta (padres) o documento de tutela | Sí | Sí |
| `telefono` | Celular | 10 dígitos | Vive saludable; beca; contacto | Lo da el tutor | Sí | Sí |
| `correo` | Correo electrónico | Texto | SAID (obligatorio); Vive saludable; beca | Lo da el tutor | Sí | Sí |
| `identificacion_tipo`, `identificacion_verificada` | Qué identificación mostró y si se revisó | INE / pasaporte / cartilla militar / INM / licencia; fecha | Comprobar quién es el tutor; la beca la pide, pero la sube el tutor | INE | Sí | Sí (solo el tipo y la fecha) |
| Clave de elector, CIC, OCR, sección, vigencia, foto, firma, huella | Datos del INE | — | Nadie los pide a la escuela | INE | No | **No** |
| Fecha de nacimiento y sexo del tutor | | — | El SAID los saca de la CURP | CURP | No | Derivado de la CURP |
| Escolaridad, ocupación, estado civil, ingresos | | — | El SAID pide la escolaridad, pero la captura el tutor allá | — | No | **No** |
| Domicilio del tutor | Solo si es distinto al del alumno | Igual que el del alumno | Contacto | Comprobante / INE | Si es distinto | Sí |
| `personas_autorizadas` | Quién puede recoger al alumno | Nombre, parentesco, teléfono | Operativo | Tutor | Recomendado | Sí |
| CURP de hermanos | Hermano inscrito | — | SAID | — | — | Derivado (relación entre alumnos de SIDP) |

### Consentimientos

| Campo | Definición | Formato o catálogo | Trámite o formato oficial | Obligatorio | Guardar |
|---|---|---|---|---|---|
| `aviso_privacidad` | Versión y fecha del aviso que se dio | Texto y fecha | LGPDPPSO | Sí | Sí |
| `consentimiento_sensibles` | Consentimiento expreso para los campos (S) | Fecha y quién firmó | LGPDPPSO, art. 7 | Sí, si se guarda algún (S) | Sí |
| `consentimiento_vive_saludable` | Si entregó el consentimiento de las jornadas | sí / no | Vive saludable (el original va a Salud) | No | Opcional |

---

## (b) Documentos oficiales que la escuela produce o llena cada año (Edomex, primaria)

| Cuándo (fechas de 2026) | Documento o trámite | Quién | Estructura | Lo que pone SIDP |
|---|---|---|---|---|
| Febrero y marzo (9/02 al 20/03) | Preinscripción al SAID (1.º) | El tutor en línea; la escuela solo informa | Ver sección 3 | Nada; avisar a las familias |
| 2 al 19 de marzo y **26 de octubre al 6 de noviembre** | Registro de la Beca Rita Cetina | El tutor | Ver sección 4 | Constancia de inscripción con CCT; datos correctos en el MIGE |
| 31 de julio y 3 de agosto | Resultados del SAID y listado en la escuela | La escuela descarga los asignados del MIGE | Lista con folio | Carga la lista; abre el expediente con `folio_said` |
| 6 al 26 de agosto | SAID, segunda fase (cambios y nuevo ingreso) | El tutor | CURP, tutor, CCT | `procedencia`, `cct_procedencia` |
| Agosto y septiembre | Inscripción y reinscripción en el MIGE | Director | CURP (consulta a RENAPO), datos de contacto; casos especiales con un PDF único y autorización | Lista para capturar: identidad, domicilio, tutor, grado y grupo, `repite_grado` |
| Hasta el 30 de septiembre | Altas y bajas | Director | Movimientos en el MIGE | `fecha_alta`, `fecha_baja` |
| Al inscribir, si falta algo | Carta-Compromiso Temporal | Tutor y director | Documento que falta y plazo | Plantilla y seguimiento |
| Al recabar los datos | Aviso de privacidad (lo publica la secretaría [?]) | Escuela | Integral y simplificado | Marca de entrega y consentimiento |
| Octubre (Edomex [?]) | 911.3 de inicio de cursos (con el fin del ciclo anterior) | Director en f911.sep.gob.mx | Secciones I a IV y discapacidad (sección 2) | Hoja con los totales listos para copiar |
| Durante el ciclo | Jornadas "Vive saludable" | Personal de salud; la escuela reparte consentimientos | Consentimiento con datos del alumno y del tutor | Lista del grupo (nombre, CURP, grado, grupo) |
| Hasta el último día hábil de noviembre | 1.er periodo de evaluación | Docentes en el MIGE | Calificación y observaciones por campo formativo | `calificacion`, `observaciones`, inasistencias |
| Hasta el último día hábil de marzo | 2.º periodo | Igual | Igual | Igual |
| Fin del ciclo (junio y julio) | 3.er periodo, calificación final y promoción; boleta | Docentes y director | Art. 7: tres parciales y final por campo | `promovido`, `promedio_final` |
| Julio | Certificado de 6.º | MIGE (electrónico, con QR) | Campos [?] | Guarda el PDF oficial en el expediente |
| Cuando un alumno se va | Informe de calificaciones parciales o constancia; baja en el MIGE | Director | Calificaciones a la fecha | `fecha_baja`, `motivo_baja` |
| Cuando lo pidan | Constancia de inscripción o de estudios | Director | CCT, nombre, CURP, grado, ciclo | Plantilla |

---

## Preguntas para la supervisión o para estadística

1. ¿Qué edición de las Normas de Control Escolar usan este ciclo? ¿El Edomex o el SEIEM tienen lineamientos
   propios para primaria?
2. ¿En el Estado de México es obligatoria la cartilla de vacunación para inscribir en 2026-2027, o hay una
   instrucción por el sarampión?
3. ¿Hasta cuándo se captura el 911 de inicio 2026-2027 en el Edomex?
4. En el 911.3: ¿cómo se cuenta a un alumno con sexo X? ¿Se pide la lengua indígena concreta? ¿Hipoacusia y TDAH
   son renglones aparte?
5. ¿Hay un aviso de privacidad de control escolar de la secretaría o del SEIEM que deba usar la escuela?
6. ¿Cuánto tiempo se guarda el expediente de un alumno, y se conservan las copias del INE y del comprobante de
   domicilio?
7. ¿Qué catálogo de motivos de baja usa el MIGE?

---

## (c) Fuentes

Ningún enlace se pudo abrir desde este entorno. Las marcadas **[O]** son documentos oficiales vistos **solo como
fragmento del buscador**; las **[S]** son secundarias.

**Normas, evaluación y control escolar**

- [O] Acuerdo 10/09/23, DOF 27/09/2023: https://dgair.sep.gob.mx/storage/recursos/CE/acuerdo_10092023.pdf · https://sidof.segob.gob.mx/notas/docFuente/5703099
- [O] DGAIR, documentos normativos: https://dgair.sep.gob.mx/documentos_normativos
- [O] AEFCM, control escolar (oficio DGAIR 133/2024): https://www.aefcm.gob.mx/controlescolar/
- [O] Normas Específicas de Control Escolar, educación básica (copia municipal, sin fecha visible): https://rinconderomos.gob.mx/assets/normas_especificas_basica.pdf
- [O] Normas 2009-2010 (SEV): http://dgece.sev.gob.mx/docs/normas_ctrl_esc_09_10.pdf · Normas de primaria 2012-2013: http://www.sicres.gob.mx/sicres/documentos/primarias/normas_primarias_2012_2013.pdf · Guanajuato: http://www.ordenjuridico.gob.mx/Estatal/GUANAJUATO/Normas/GTONORM02.pdf
- [O] SEDU Coahuila, preguntas frecuentes sobre las Normas: https://www.seducoahuila.gob.mx/planeacion/incorporacionyrevalidacion/assets/preguntas-frecuentes.pdf
- [O] SEP, preguntas frecuentes de control escolar: http://www.controlescolar.sep.gob.mx/es/controlescolar/preguntas_frecuentes
- [O] Lineamientos de control escolar del Edomex (media superior), Gaceta del 30/04/2025: https://legislacion.edomex.gob.mx/sites/legislacion.edomex.gob.mx/files/files/pdf/gct/2025/abril/abr301/abr301a.pdf
- [S] Normas de Control Escolar 2023-2024 (Scribd): https://www.scribd.com/document/492638647/NORMAS-ESPECIFICAS-DE-CONTROL-ESCOLAR-RELATIVAS-A-LA-INSCRIPCION
- [S] Resumen de las Normas (Studocu): https://www.studocu.com/es-mx/document/universidad-pedagogica-nacional/metodologia-de-investigacion/normas-especificas-de-control-escolar-sep-inscripcion-y-certificacion/151589044
- [S] Certificado médico sustituido por la cartilla: https://www.timeoutmexico.mx/ciudad-de-mexico/ninyos/dejaran-de-pedir-certificado-medico-en-las-inscripciones-escolares · https://www.elfinanciero.com.mx/cdmx/2022/08/17/escuelas-dicen-adios-al-certificado-medico-este-sera-el-nuevo-requisito/
- [S] Cartilla y sarampión en 2026: https://www.adn40.mx/mexico/2026-02-03/brote-sarampion-escuelas-que-niegan-inscripcion-alumnos-sin-cartilla-vacunacion/ · https://www.aztecasinaloa.com/noticias/inscripciones-2026-2027-cartilla-vacunacion-requisito-obligatorio-sep/ · https://soydocente.online/sep/vacunas-para-el-regreso-a-clases-la-guia-oficial-de-la-sep-y-por-que-son-obligatorias/
- [S] CURP biométrica no exigible para inscribir: https://www.adn40.mx/mexico/2025-08-09/la-curp-biometrica-es-obligatoria-para-las-inscripciones-escolares-2025 · https://www.ejecentral.com.mx/nuestro-eje/curp-biometrica-2026-es-obligatoria-para-la-inscripcion-al-ciclo-escolar-2027-paso-a-paso-para-hacer-el-tramite-sin-fila
- [S] Acuerdo 10/09/23, escala y periodos: https://www.nmas.com.mx/nacional/acuerdo-evaluacion-2023-sep-como-sacaran-calificaciones-en-primaria-secundaria/ · https://diarioeducacion.com/acuerdo-numero-10-09-23-normas-generales-para-la-evaluacion-del-aprendizaje-acreditacion-promocion-regularizacion-y-certificacion/

**911**

- [O] Formato 911.3 2026-2027: https://www.f911.sep.gob.mx/2026-2027/Documento/Formatos911BasicaSV/PRIMARIA.pdf · https://planeacion.sec.gob.mx/upeo/FormatosInicio2026_2027/Basica/PRIMARIA%20_%20911-3.pdf
- [O] Formato 911.3 2025-2026: https://www.f911.sep.gob.mx/2025-2026/Documento/Formatos911BasicaSV/PRIMARIA.pdf · https://planeacion.sec.gob.mx/upeo/FormatosInicio2025_2026/B%C3%A1sica/PRIMARIA%20_%20911-3.pdf
- [O] Formato CAM 2025-2026 (hipoacusia, TDAH, doble excepcionalidad): https://www.f911.sep.gob.mx/2025-2026/Documento/Formatos911BasicaSV/CAM.pdf · USAER: https://911.usebeq.edu.mx/Content/resources/cuestionarios-en-blanco/usaer.pdf
- [O] Guía de llenado 911, primaria general (SEV): https://www.sev.gob.mx/upece/investigacion/wp-content/uploads/sites/4/2020/09/Gu%C3%ADa-de-llenado-Educaci%C3%B3n-B%C3%A1sica-Primaria-General-IC2324.pdf
- [O] Fechas de captura 2026: https://unidadoperacionpuebla.blogspot.com/ · https://tamaulipas.gob.mx/educacion/2026/10/llenado-del-formato-estadistico-911-correspondiente-al-ciclo-escolar-2026-2027/
- [S] Plandocente, qué se llena en el 911 de 2026-2027: https://plandocente.com/blog/formato-911-inicio-de-ciclo-que-se-llena/ · Studocu, 911.3 de 2026-2027: https://www.studocu.com/es-mx/document/universidad-nacional-autonoma-de-mexico/vias-terrestres/estadistica-educativa-primaria-9113-ciclo-escolar-2026-2027/174816745
- [S] Glosario del 911 de primaria (SlideShare): https://www.slideshare.net/slideshow/911-de-primaria/65560467

**SAID, MIGE, SIGED y SIIE**

- [O] MIGE, descarga de alumnos asignados del SAID: https://edugem.gob.mx/mige/tutoriales/Guia_descarga_alumnos_asignados_Said.pdf · inscripción por infraedad, extraedad y traslado: https://edugem.gob.mx/mige/tutoriales/Guia_inscripcion_TESI.pdf · descarga de boletas: https://edugem.gob.mx/mige/tutoriales/Guia_descargas_de_boletas.pdf
- [S] Manual de Preinscripciones MIGE (febrero de 2024, Studocu): https://www.studocu.com/es-mx/document/tecnologico-de-estudios-superiores-de-coacalco/programacion-web/manual-de-preinscipciones-mige-2/89463066 · Manual MIGE (Scribd): https://es.scribd.com/document/587243848/MIGE-4-MANUAL-MIGE
- [S] SAID 2026: https://politica.expansion.mx/estados/2026/01/30/fechas-preinscripciones-said-preescolar-primaria-secundaria · https://www.adn40.mx/tramites/2026-01-27/preinscripciones-said-edomex-2026-2027-fechas-requisitos-registro-en-linea-preescolar-primera-secundaria/ · https://www.infobae.com/mexico/2026/07/31/resultados-said-edomex-2026-aqui-puedes-consultar-fechas-y-requisitos-para-solicitar-tu-cambio-de-escuela/ · https://www.digitalmex.mx/estado-de-mexico/story/69477/secretaria-educacion-edomex-abre-segunda-fase-said-2026-cambios-escuela-nuevo-ingreso
- [O] SIGED, Acuerdo 07/03/18: https://sigedqa.sep.gob.mx/SIGED/archivos/DOF_200318.pdf · consulta por CURP: https://siged.sep.gob.mx/SIGED/alumnos.html
- [O] SIIE Web (AEFCM, CDMX): https://www.aefcm.gob.mx/siieweb/archivos-guias/basica-publica/Control-Escolar/guia_apoyo_inscripcion_actualizacion_datos_alumnos_21032018.pdf
- [O] EDIEMS (otro sistema, con carga en Excel): https://evaluaciondiagnostica-eb-ems.edugem.gob.mx/Manual_del_sistema_de_captura_de_los_resultados.pdf

**Becas y salud**

- [O] Programas para el Bienestar, nuevo registro de la Rita Cetina del 26/10 al 6/11/2026: https://www.programasparaelbienestar.gob.mx/noticias-y-comunicados/noticia/beca-rita-cetina-del-26-de-octubre-al-6-de-noviembre-nuevo-registro-para-primaria-y-secundaria/
- [S] Rita Cetina en primaria, requisitos y SIGED: https://www.eluniversal.com.mx/tendencias/beca-rita-cetina-2026-cuales-son-los-requisitos-para-el-registro-sigue-el-paso-a-paso/ · https://www.nmas.com.mx/sociedad/programas-sociales/siged-primaria-registro-beca-rita-cetina-2026-como-verificar-datos-link-que-hacer/ · https://www.foxsports.com.mx/2026/03/14/beca-rita-cetina-2026-que-es-el-cct-y-como-conseguirlo-para-tramitar-tu-registro-en-primaria/
- [O] "Vive saludable", recomendaciones a familias (consentimiento): https://vidasaludable.gob.mx/storage/recursos/materiales/Recomendaciones-Jornadas_Salud_Escolar.pdf · cierre 2025-2026 (IMSS): https://www.imss.gob.mx/sites/all/statics/i2f_news/BOLETIN%20CONJUNTO.-%20Gobierno%20de%20M%C3%A9xico%20cierra%20a%20nivel%20nacional%20las%20Jornadas%20de%20Salud%3B%20fueron%20atendidos%2010.8%20millones%20de%20estudiantes%20en%20el%20ciclo%20escolar%202025-2026.pdf
- [S] Expediente Digital de Salud Escolar: https://www.jornada.com.mx/2025/07/15/politica/009n2pol · https://www.proceso.com.mx/nacional/2025/7/14/expediente-digital-de-salud-para-alumnos-de-primaria-ya-esta-disponible-que-es-como-consultarlo-353122.html

**Catálogos**

- [V] python-stdnum 2.2, `stdnum/mx/curp.py` (claves de entidad, formato y dígito verificador de la CURP), bajado de PyPI: https://pypi.org/project/python-stdnum/
- [S] CURP con sexo X: https://conocimiento.blob.core.windows.net/conocimiento/2024/General/Componentes/NotasTecnicas/NT_SP_Componentes_831/actualizacion_en_el_parametro_curp_print.html · https://www.milenio.com/politica/comunidad/jalisco-emiten-primera-curp-de-genero-no-binario
- [O] INALI y SNIEG, agrupaciones lingüísticas: https://www.snieg.mx/Documentos/Normatividad/Vigente/ntrngcfrs_anexo_3_agrup_ling_snieg.pdf
- [O] INEGI, Valle de Chalco Solidaridad 15122: https://www.inegi.org.mx/contenidos/app/mexicocifras/datos_geograficos/15/15122.pdf

**Datos personales**

- [O] LGPDPPSO, DOF 20/03/2025: https://www.diputados.gob.mx/LeyesBiblio/ref/lgpdppso/LGPDPPSO_orig_20mar25.pdf · https://www.scjn.gob.mx/sites/default/files/marco_normativo/documeto/2025-04/Ley-General-de-Proteccion-Datos-Personales-en-Posesion-Sujetos-Obligados-DOF-20250320.pdf · texto vigente: http://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf
- [O] Ley de datos personales del Edomex (art. 26): https://legislacion.edomex.gob.mx/sites/legislacion.edomex.gob.mx/files/files/pdf/ley/vig/leyvig244.pdf · Infoem: https://infoem.org.mx/
- [S] Baker Tilly, avisos de privacidad tras la reforma: https://www.bakertilly.mx/en/insights/nuevas-disposiciones-en-materia-de-datos-personales
