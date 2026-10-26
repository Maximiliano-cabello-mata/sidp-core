# Base tecnica de validacion documental

Fecha: 2026-10-11. Diseno, sin codigo todavia. Ver ADR-022 y modulo_expediente.md. Los documentos del alumno deben **cumplir validacion real**, no solo almacenarse. Este documento define la base tecnica; el modulo de expediente la usa.

## Principio

Un documento solo pasa a `validado` cuando cumple todas las reglas obligatorias de su tipo **y** una persona con permiso confirma el cotejo contra el original. Ningun proceso automatico (reglas, OCR, consulta oficial) marca por si solo un documento como validado. Cada comprobacion deja **evidencia** guardada: que regla, resultado, fuente, quien o que la ejecuto y cuando. Asi la validacion es explicable y auditable.

## Cuatro niveles de comprobacion

| Nivel | Que hace | Donde corre | Resultado |
|---|---|---|---|
| 1 Integridad y estructura | Archivo legible, formato y tamano aceptables, hash (duplicados), vigencia, estructura y digito verificador de la CURP, coherencia de fecha de nacimiento, sexo y entidad de la CURP con los datos del alumno | Plataforma, determinista | `cumple` / `no_cumple` / `advertencia` |
| 2 Extraccion y cruce | Lee el texto del PDF o la imagen (texto incrustado y, si no hay, OCR local), extrae campos (CURP, nombre, fecha, folio, identificador electronico y cadena del acta, CCT, grado, ciclo, promedio) y los compara campo por campo con el registro del alumno | Capacidad de agente `documento.analizar`, una tarea a la vez | Campos con confianza y coincidencias; baja confianza se marca para revision |
| 3 Verificacion oficial | CURP contra RENAPO (portal gob.mx/curp). Acta de nacimiento por su codigo QR (debe apuntar a un dominio .gob.mx) y por el sistema CEVAR del Registro Civil con identificador electronico, cadena y codigo de verificacion | Asistida: el sistema prepara los datos y abre el portal oficial; el personal registra el resultado y adjunta la constancia | Evidencia con fecha, quien consulto y comprobante |
| 4 Cotejo humano | Comparar con el documento original y resolver advertencias | Interfaz del administrativo | `validado` o `rechazado` con motivo |

## Sobre la verificacion oficial (nivel 3)

- Segun una busqueda web que debe confirmarse con direccion y supervision, el Gobierno no ofrece una API publica gratuita para consulta masiva de CURP; la consulta oficial individual esta en gob.mx/curp, y existen proveedores autorizados de API de pago. El acta digital se verifica por su QR y por CEVAR.
- Por eso el nivel 3 se disena **asistido**: no se automatiza saltando captchas ni terminos de uso. El sistema calcula que consultar, abre el portal con los datos listos, y registra el resultado y la constancia.
- Se deja una interfaz `VerificadorOficial` con implementacion `Asistido` hoy y espacio para un proveedor de API autorizado si la escuela lo contrata (costo, aviso de privacidad y LFPDPPP por evaluar).
- Hasta confirmar un canal valido, el sistema nunca afirma validez oficial por si mismo: lo marca `pendiente de verificacion oficial` si es requisito de ese tipo.

## Reglas por tipo de documento (catalogo editable por direccion)

| Documento | Reglas obligatorias (ejemplos) |
|---|---|
| CURP | Estructura y digito correctos; datos coinciden con el alumno; constancia de verificacion oficial |
| Acta de nacimiento | Nombre, fecha y CURP coinciden; identificador y cadena presentes; QR a dominio .gob.mx o verificacion CEVAR registrada |
| Certificado medico | Fecha dentro del ciclo; nombre del alumno; datos del medico presentes; firma visible |
| Calificaciones anteriores | Nombre, CCT, grado y ciclo extraidos; grado anterior consistente con el que se inscribe |
| Carta responsiva | Tutor registrado coincide; firma y fecha presentes |

Cada regla es obligatoria, advertencia o informativa segun lo defina direccion. Las reglas viven en paquetes por tipo, versionados; cambiar una regla no reescribe evidencia pasada.

## Modelo de datos (nuevo modulo `validacion`)

- `regla(id, tipo_documento, clave, nivel, severidad, version, activa)`
- `evidencia(id UUID, documento, regla, resultado, detalle, fuente, ejecutor, fecha, constancia_hash)`
- `extraccion(id, documento, campo, valor, confianza, metodo, fecha)`
- `veredicto(documento, estado, revisor, motivo, fecha)` con estados `pendiente | en_revision | validado | rechazado | vencido`

Las evidencias son de solo anadir. El veredicto cambia solo por accion humana y se audita en la misma transaccion (modulo de auditoria de la base tecnica). Eventos `documento.evidencia_agregada` y `documento.validado` se publican por el diario existente, sin contenido del documento.

## Integracion con la base tecnica

- Modulo de plataforma `validacion` (depende de `identidad`, `escolar`, `expediente`) con migraciones propias, segun el contrato de modulos.
- Capacidad de agente `documento.analizar`: idempotente (se puede repetir sin efecto externo), una tarea por equipo, limitada por la politica de recursos. El OCR corre en el equipo que tenga el archivo o en cualquiera con capacidad, por la cola.
- Los archivos se guardan en `SIDP_HOME` con hash; los metadatos en la base. Sin enviar contenido de documentos a servicios externos por defecto.
- El resultado de analisis se acepta solo de un agente con reserva vigente (misma regla de reservas que las demas tareas).

## Seguridad y privacidad

1. El texto dentro de un documento es dato, nunca instruccion para el sistema.
2. Los archivos se tratan como no confiables: limites de tamano, tipo MIME real, sin ejecutar contenido, analisis de PDF en proceso aislado y con tiempo limite.
3. Permisos: solo administrativos y direccion ven el contenido; docentes ven solo el estado.
4. Constancias de verificacion oficial se guardan con hash; retencion y aviso de privacidad por definir.
5. Todo cambio de veredicto queda en auditoria con el nombre de la persona.

## Pruebas obligatorias

- Vectores de prueba de CURP validas e invalidas, incluyendo digito verificador y fecha imposible.
- Cruce de campos con alumnos de prueba: coincide, discrepa, falta.
- Un documento no puede pasar a `validado` si falta una regla obligatoria o la confirmacion humana.
- Repetir `documento.analizar` con la misma reserva no duplica evidencia.
- Archivo corrupto, demasiado grande o de tipo falso se rechaza sin afectar al sistema.

## Limites honestos

El OCR no es exacto; por eso todo campo extraido lleva confianza y la persona decide. Validar el contenido no prueba que un documento fisico sea autentico; eso lo da la verificacion oficial y el cotejo con el original. Alumnos sin CURP, extranjeros o con documentos de otra entidad necesitan estado `no_aplica` o prorroga con motivo.

## Plataforma web de padres (2026-10-14)

Decidido con Maximiliano el 2026-10-14. Amplia este documento y el alcance del buzon de ADR-028. El orden esta en [PLAN.md](../PLAN.md#validación-de-documentos-y-plataforma-web-de-padres).

Documentos:

- **Alumno:** acta de nacimiento, certificado medico, boletas de los grados cursados. La CURP se escribe y se valida que exista, sin pedir el documento.
- **Tutor:** INE, acta de nacimiento (prueba el parentesco con el acta del alumno), CURP, comprobante de domicilio.
- **Formatos:** ficha de inscripcion y ficha de autorizacion. SIDP las llena con datos validados y el tutor las firma.

Como funciona:

1. **Plataforma web de padres.** El padre se registra con su correo (confirmado con un codigo), captura los datos del alumno y sube cada documento. Al subirlo, una revision rapida avisa si la foto esta borrosa o no es el documento pedido.
2. **Plantilla de lo esperado** por tipo y version: textos fijos, campos y formatos, contenido del QR y reglas internas y cruzadas. Se arma con ejemplos tachados, sin datos de nadie.
3. **Validacion automatica con procesos, sin IA.** Programas fijos (lector de QR, texto del PDF, OCR clasico con Tesseract, medida de nitidez de la foto) reconocen el tipo por los textos de la plantilla, leen los datos, comparan con la plantilla y el expediente, y anotan inconsistencias. Es la revision superficial de los niveles 1 a 3. Lo que no se puede leer se marca "no se pudo leer" y lo revisa el administrador. El cerebro (PC 4) es una ayuda opcional para despues, solo si las mediciones muestran que los procesos no alcanzan; la validacion no depende de el.
4. **Existencia de la CURP.** Se revisa el digito verificador y luego el QR del acta, validado en gob.mx (por probar si tiene captcha). Las excepciones las consulta en RENAPO una persona, por lote. No hay API publica; el servicio web es por convenio con secretarias estatales de educacion. `backend/conectores/renapo.py` devuelve datos simulados y debe reemplazarse.
5. **Autorizacion manual** (nivel 4). El sistema muestra al administrador que falta y que inconsistencias encontro. Solo el administrador dice si o no (se mantiene ADR-023). Con el si, el padre recibe un correo positivo. Con el no, el sistema le envia el reporte de inconsistencias y que corregir, hecho con plantillas fijas y sin copias de documentos.
6. **Datos para analisis.** Los campos extraidos se guardan ordenados y se analizan en cifras agregadas por grupo y ciclo. Los datos de salud no entran al analisis.

Los documentos se procesan en las computadoras de la escuela: la plataforma en internet solo recibe y entrega (ADR-028).

Faltan en `tipo_documento` de [diseno_integral.sql](../../database/diseno_integral.sql): acta y CURP del tutor, ficha de inscripcion y ficha de autorizacion. Las interfaces de Paola proponen ademas hoja de registro, carta compromiso, formato SAID y certificado de 3o de kinder; se confirman con la escuela.

## Orden de construccion

Sustituido el 2026-10-14 por los pasos de [PLAN.md](../PLAN.md#validación-de-documentos-y-plataforma-web-de-padres). Se conserva como referencia:

1. Nivel 1 (CURP estructural, hash, vigencia) y el modelo `evidencia` y `veredicto`.
2. Interfaz de validacion del administrativo con el veredicto humano.
3. Nivel 2 con texto incrustado en PDF y luego OCR.
4. Nivel 3 asistido con registro de constancia.
5. Evaluar proveedor oficial de API solo si hay presupuesto y aprobacion.

## Entorno de pruebas (2026-10-15)

Lo construido hasta hoy, en versión de prueba:

- **Lector** (`validacion/lector.py`): texto del PDF; páginas escaneadas a imagen; fotos recortadas, sin perspectiva, sin sombra y giradas; nitidez; QR y códigos de barras; OCR con PaddleOCR si está instalado, si no Tesseract.
- **Franja de la INE** (`validacion/mrz.py`): nombre, fechas y sexo con dígito verificador. La INE vencida es hallazgo.
- **Expediente** (`validacion/expediente.py`): lo capturado contra cada documento; tipo de documento por sus textos fijos, con tolerancia a errores del OCR.
- **SIDP-Validador.exe** (PC del administrador): recibe a los padres, guarda archivos y datos como propuesta y deja autorizar o rechazar.
- **Cerebro** (PC 4): valida por IP con clave y opina en la zona gris.

Cómo se arma: [ENTORNO_PRUEBAS.md](../guias/ENTORNO_PRUEBAS.md). Resultados y errores: [bitácora del 2026-10-15](../bitacoras/2026-10-15.md).

## CURP ante RENAPO, asistida por una persona (2026-10-15)

Decisión de Maximiliano: el sistema no tiene que estar automatizado al 100%. No hay bots ni se
resuelve el captcha de forma automática. Así funciona:

1. Toda CURP entra "Sin validar" (`alumno.curp_confirmada = 0`).
2. En el panel, la persona copia la CURP y abre gob.mx/curp. Ahí la pega, resuelve el captcha,
   descarga la constancia en PDF y la arrastra al panel.
3. `validacion/renapo.py` lee la constancia: busca la frase de RENAPO, la CURP con su dígito
   verificador correcto y el nombre.
4. El alumno se encuentra por la CURP, sin elegirlo a mano. Si el nombre coincide,
   `sp_validar_curp_renapo` guarda la constancia como documento `curp` validado y pone
   `curp_confirmada = 1`. La revisión y la bitácora registran quién y cuándo.
5. Si el nombre no coincide, o si la constancia trae otra CURP pero el nombre de un alumno, el
   documento queda rechazado y el motivo se muestra para hablar con el padre.
6. "RENAPO no la encontró" queda anotado en la bitácora.

Pendiente: confirmar con una constancia real que su texto se lee con pypdf. Solo se probó con
constancias inventadas, porque gob.mx no se puede abrir desde el entorno en la nube.

Además, desde ese mismo día el vínculo tutor–alumno se aplica solo cuando el administrador
autoriza el expediente. Antes se aplicaba al recibirlo, y cualquiera que escribiera la CURP de un
alumno quedaba como su tutor principal.

## Expedientes escaneados, ya revisados en papel (2026-10-15)

Para las carpetas que la escuela ya revisó, no se corre la validación completa: solo se extraen los
datos. En el panel, el cuadro "Escanear expediente" recibe los escaneos de un alumno (un PDF con varias
hojas o varios archivos), separa las hojas, reconoce cada documento por sus textos fijos y propone los
datos del alumno y del tutor (`validacion/extraer.py`, procesos fijos, sin IA):

- La CURP se busca con su dígito verificador; las confusiones del OCR (O y 0, I y 1...) se corrigen por
  posición. Una letra de más solo se quita si queda una sola CURP posible que cuadre con un nombre del texto.
- El nombre se encuentra con las letras que trae la CURP, en cualquier orden del documento. Si no, se usan
  las etiquetas del acta ("Nombre(s): ... Primer apellido: ...") o del frente de la INE, con un aviso.
- La persona revisa, corrige y guarda. El expediente queda "validado en papel": sus documentos quedan
  validados con origen `escaneo`, el tutor vinculado, y "Revisar todo" no lo vuelve a revisar. La CURP
  sigue "sin validar" ante RENAPO hasta que alguien haga ese paso.

## Plantillas de documentos (2026-10-15)

Pedido de Maximiliano: que los administrativos agreguen documentos sin programar, y que se validen por
plantilla. Una plantilla (`validacion/plantillas.py`) es solo datos:

| Campo | Qué es |
|---|---|
| nombre, de | Cómo lo ven los padres y si es del alumno o del tutor |
| obligatorio, para_padres | Si falta es hallazgo; si la página de padres lo pide |
| textos | Frases fijas del documento (título, etiquetas), sin datos de nadie |
| minimo | Cuántas de esas frases debe tener para aceptarlo |
| reglas | Elegidas de una lista fija: nombre del alumno, nombre del tutor, CURP del alumno, domicilio, fecha reciente (con meses) |

- **Cómo se arma.** El administrativo sube una muestra: el formato en blanco, o dos o tres llenos de personas
  distintas. El sistema propone los renglones que se repiten y, de cada "Etiqueta: dato", solo la etiqueta.
  La persona quita lo que sobre y guarda.
- **Dónde se usa.** La página de padres pide los documentos con `para_padres`; el escaneo reconoce las hojas
  de cada plantilla (las de la escuela ganan a las de fábrica porque son más específicas); la revisión valida
  cada documento con sus textos y sus reglas, en esta PC o en el cerebro (la plantilla viaja con el pedido).
- **De fábrica.** Acta, INE, comprobante y demás aparecen como plantillas versión 0. Se les pueden agregar
  textos fijos (otra compañía de agua o de luz) y cambiar si son obligatorios; sus revisiones propias (CURP
  del acta, franja de la INE, vigencia) siguen siendo código.
- **Sin sobrescribir.** Cada cambio es otra versión (`plantillas/<clave>/v001.json`) y las muestras se guardan
  junto a ella. Dar de baja un documento es otra versión con `activa: false`.
- **En la base.** Cada plantilla de la escuela es una fila de `tipo_documento` (clave `p_...`), así sus
  documentos se registran como cualquier otro.
- **Límite honesto.** La plantilla reconoce un documento por lo que dice, no por cómo se ve: un documento
  falso que copie las frases pasa este filtro. Para eso siguen la persona que autoriza y, después, el modelo
  que ve (borrador en `propuestas/`).

## Listas de grupo y panel por pestañas (2026-10-15)

Pedido de Maximiliano: un solo panel, por pestañas, con el diseño de Paola, y los expedientes divididos
por grado y grupo. El trabajo empieza por las listas de cada grupo y después va el expediente de cada niño.

- **Listas de grupo** (`validacion/grupos.py`). La lista escaneada o escrita se lee renglón por renglón
  (`extraer.lista_de_grupo`, `extraer.grado_y_grupo`); una CURP mal leída no se mete al nombre y el
  renglón queda como duda. La persona corrige y guarda; cada alumno se inscribe en su grupo del ciclo
  (agosto a julio) con `sp_inscribir_alumno`. Guardar otra vez no duplica (misma CURP, o mismo nombre sin CURP).
- **Ligar expedientes.** Al escanear, el sistema propone los alumnos parecidos de las listas (nombre sin
  orden ni acentos) y **la persona elige**; nunca se liga solo. El alumno de la lista recibe CURP, fecha y
  sexo, con versión y bitácora (`alumno.completado`). Lo de la página de padres cae solo en su grupo cuando
  el nombre es idéntico o la CURP ya está; si no, el panel propone el parecido y la persona lo ubica
  (`alumno.unido`: el renglón de la lista, sin documentos, se cancela y se archiva; nada se borra).
- **Análisis.** Matrícula por grado y sexo, faltantes por alumno y descargas a Excel (`validacion/hoja.py`,
  `.xlsx` sin instalar nada) y CSV con protección contra fórmulas.
- **Panel** (`validacion/interfaz/panel.html`): Inicio, 1 Listas de grupo, 2 Escanear expediente
  (validación manual), 3 Fila de revisión (validación automática, por grupo y estado), 4 CURP y RENAPO,
  Análisis 911 y SAID, Plantillas y Ajustes. Funciona sin internet (sin Tailwind ni Font Awesome) y en celular.

## Lista oficial de la escuela y base de datos del cerebro (2026-10-15)

Pedido de Maximiliano: usar la lista oficial de la estadística de la SEP (un PDF con toda la escuela, un
grupo por grado) como base de alumnos, y que la PC 4 tenga su propia base de datos, PostgreSQL, para hacer
mejores procesos. Después solo se escanean los documentos físicos de cada alumno.

- **Formato del PDF oficial.** Es una hoja de cálculo exportada: cada renglón trae CURP, número y nombre
  (primer apellido, segundo apellido, nombre). Hay que leerlo con `extract_text(extraction_mode='layout')`;
  el modo normal no separa los renglones. Algunas CURP traen letras griegas que se ven iguales a las
  latinas (Α, Ε, Μ...): `expediente.mayusculas` las cambia. El número del encabezado es la **fase**, no el
  grado, así que el grado sale de la edad de la mayoría (`extraer.grado_por_edad`: año de inicio del ciclo
  − año de nacimiento − 5). La letra no viene: se pone A y la persona la confirma.
- **Importar de un jalón.** `lista_leer` lee hoja por hoja y devuelve todos los grupos; una hoja que sigue
  la lista del grupo anterior se une a él, y las hojas sin CURP (instrucciones) se ignoran.
  `lista_guardar({'grupos': [...]})` revisa todo antes de guardar, así nada queda a medias.
- **Base del cerebro** (`validacion/base_cerebro.py` y `base_cerebro.sql`). PostgreSQL en la PC 4,
  escuchando solo en 127.0.0.1. Guarda `padron_alumno` (un alumno que sale de la lista se apaga, no se
  borra) y `lectura` (cuánto se leyó de cada página y qué tan cerca quedó del padrón, para medir).
  Los procesos viven en la base: `sidp_cargar_padron`, `sidp_curp_cercana` (levenshtein, hasta 2 letras)
  y `sidp_nombre_cercano` (trigramas: aguanta faltas de ortografía y otro orden). Se conecta con pg8000,
  que es solo Python. Sin PostgreSQL el cerebro funciona igual, sin comparar.
- **Cómo se usa.** El .exe manda el padrón al cerebro (`POST /padron`, con la clave) al conectarse y cada
  vez que se guardan listas. En `/leer`, cada página regresa con sus sugerencias del padrón. Al escanear,
  si la CURP leída no es de nadie pero está a una o dos letras de la de un alumno, o no se leyó la CURP y
  el nombre se parece a uno solo, el panel propone ese alumno **con un aviso**; la persona compara con el
  acta y decide. Dos alumnos igual de parecidos (hermanos) no se proponen.
- **Dónde vive cada cosa.** El .exe del administrador sigue guardando los archivos y su SQLite; la base
  de la PC 4 es para procesar mejor. Desde la versión 2 guarda el expediente completo con sus procesos:
  ver [base_cerebro.md](base_cerebro.md). Instalación: Tarea 008; carga de los alumnos: Tarea 009.

## Lectura completa, filtro de datos y auditoría (2026-10-26)

Pedido de Maximiliano: no salían los contactos de emergencia (nombre, teléfonos, correos) y del certificado médico casi
nada; algunos alumnos aparecían con hipertensión o «enfermedad mental o nerviosa» que eran de la familia. Quiere que la
lectura vea todo lo que trae la hoja, aunque tarde más, y que de eso se queden solo los datos del estándar.

- **Primero se transcribe todo.** `vision.transcribir` copia cada hoja tal como está (etiquetas con su valor, casillas
  `[X]`/`[ ]`, dígitos uno por uno), hasta 4 hojas por documento: el certificado de frente y vuelta entra completo. Una
  hoja sin título que viene justo después de otra se toma como su reverso (`servicio._clasificar`).
- **Luego se filtra.** `validacion/purificar.py` saca de ese texto solo teléfonos y correos (con de quién son: madre,
  padre, tutor o emergencia; nunca los de la escuela, la clínica o el médico), el contacto de emergencia con su
  parentesco y la salud del alumno. Un antecedente heredofamiliar o una opción impresa sin marcar no cuenta. Todo lo
  demás de la hoja se descarta: solo se guarda lo que permite `estandar.permitido`.
- **La salud se revisa varias veces.** Cada valor se compara entre la transcripción, el texto del PDF o el OCR y dos
  lecturas con campos (una en orden inverso). Después, `vision.pregunta_verificar` le pregunta al modelo por cada
  valor si es del alumno, de un familiar, solo impreso o no aparece. Lo grave (hipertensión, epilepsia, enfermedad
  mental, cardiopatía, asma, autismo...) siempre queda por confirmar por una persona, aunque todas las lecturas
  coincidan. Lo que todavía no confirma una persona no sale en los formatos de salud.
- **Repetidos.** Lo que la máquina leyó casi igual a un dato más seguro queda reemplazado (`purificar.duplicados`), y la
  base misma no deja guardar dos veces el mismo dato (ver [base_cerebro.md](base_cerebro.md)). Nada se borra, y lo
  que escribió o confirmó una persona no se toca.
- **Auditoría.** **Por revisar > Volver a leer todo** encarga de nuevo cada expediente autorizado. Lo nuevo que se
  escanea va primero; lo que la máquina había leído de ese expediente se cambia por la lectura nueva.
- **Los archivos de la escuela no se tocan.** SIDP no mueve, renombra ni borra los archivos de los directivos aunque
  tengan copias repetidas: solo concentra los datos dentro de la plataforma.

## Salud general del certificado médico (2026-10-26)

Pedido de Maximiliano: del certificado no solo quiere los padecimientos o la discapacidad, sino cómo está cada alumno
en general (peso, estatura, lo que pide el gobierno y lo que anotan los centros de salud), en una tabla con datos y con
generalidades. Esto deja atrás el «Solo lo necesario» del 23 de octubre.

- **Qué se saca.** Peso, talla, tipo de sangre, agudeza visual y lentes, audición, salud bucal, esquema de vacunación,
  aptitud para educación física, servicio médico, conclusión del médico, recomendaciones y fecha del certificado
  (`estandar.DICCIONARIO`, categoría salud). Los signos vitales, el nombre y la cédula del médico no se guardan.
- **Cómo se lee.** `purificar.salud_general` saca esos datos de la transcripción completa por sus etiquetas, sin tomar
  los de la sección de la familia ni el peso al nacer, y sin contar opciones impresas sin marcar. La lectura con
  campos del modelo los confirma. La talla en centímetros pasa a metros (`indicadores.medida`); lo que no cabe en una
  medida de niño se descarta. Un texto que suena grave queda por confirmar, como en las listas.
- **Generalidades.** `indicadores.salud_general` agrupa cada dato en pocas clases (vista normal o necesita valoración,
  dientes sanos o necesita dentista, vacunas completas o incompletas...), calcula el estado nutricional con la OMS y
  arma una frase por alumno: lo que concluyó el médico y lo que requiere atención.
- **Dónde sale.** Formatos oficiales > **Estado de salud del grupo** (Excel y PDF, una hoja por grupo, con la columna
  «En general»), la tarjeta «Estado de salud» de la ficha del alumno, y las columnas de salud del Metadato (sangre,
  peso, talla, lentes, servicio médico, certificado entregado, vacunas completas).
