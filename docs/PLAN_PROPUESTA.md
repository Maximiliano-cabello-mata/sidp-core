# Propuesta de plan (2026-10-14)

> **Estado: borrador, sujeto a cambios mayores.** [PLAN.md](PLAN.md) sigue siendo el plan vigente hasta que esta propuesta se apruebe. Aquí se junta el análisis del 2026-10-14 para trabajarlo en el repositorio.

Documentos completos (Claude Docs):

- [SIDP: análisis y plan claro](https://claude.ai/code/artifact/885ebf90-7ec1-4528-9e65-57a22650d7cc): qué está mal, qué tenemos, diagramas y fases.
- [SIDP: cómo validar los documentos de inscripción](https://claude.ai/code/artifact/f40f536e-91ff-4ca8-8188-0207fa57928b): documentos, niveles de validación, CURP y RENAPO, cerebro y pasos.

## Diagnóstico

La conectividad funciona: dos PCs reales se unieron con la clave el 2026-10-13 ([bitácora](SESION_2026-10-13.md)). Pero la escuela todavía no puede usar nada: no hay cuentas del personal, expedientes ni pantallas, y la [base de datos integral](arquitectura/base_de_datos.md) de 39 tablas está diseñada sin usarse. En seis días se hicieron 40 commits y 29 ADR, casi todo de red.

## Paso 0: red congelada

No se agregan funciones de conexión. Solo se corrigen errores que salgan en la prueba de la escuela (3e). El reparto de tareas (ADR-026) se deja como está.

## Fases

Cada fase usa las tablas de [diseno_integral.sql](../database/diseno_integral.sql) y termina con algo que la secretaria usa desde el navegador. El backend hace tablas, reglas y API; la pantalla de cada fase se hace en la rama de diseño sobre esa API.

| Fase | Backend | Lista cuando |
|---|---|---|
| A. Cuentas | Usuarios del personal, roles, sesión con vencimiento, límite de intentos, bitácora | Cada persona entra con su usuario y ve solo lo de su rol |
| B. Alumnos, tutores y grupos | Alumnos en las tablas nuevas, tutores, ciclo y grupos, carga desde Excel | Un grupo real se carga desde Excel y un dato se corrige sin perder el anterior |
| C. Expediente | Recibir documentos, guardarlos sin sobrescribir, revisión con motivo, folio de recibido | Secretaría arma el expediente de un grupo y ve qué falta |
| D. Búsqueda y faltantes | Búsqueda por nombre, CURP, grupo o tipo; faltantes por grupo; exportar todo | Cualquier alumno aparece en segundos |
| E. Copias (3g) | Copia a otra PC y cada noche al disco externo; prueba de restauración | Se apaga el servidor y no se pierde nada |

La plataforma de padres y el cerebro ya no van al final: ver la sección de validación. Después: docentes, formatos y piloto.

## Validación de documentos: plataforma web de padres

Corregido el 2026-10-14 con la idea de Maximiliano. Amplía [validacion_documental.md](arquitectura/validacion_documental.md) (ADR-022) y cambia el alcance del buzón de ADR-028.

Documentos:

- **Alumno:** acta de nacimiento, certificado médico, boletas de los grados cursados. La CURP se escribe y se valida que exista, sin pedir el documento.
- **Tutor:** INE, acta de nacimiento (prueba el parentesco con el acta del alumno), CURP, comprobante de domicilio.
- **Formatos:** ficha de inscripción y ficha de autorización. SIDP las llena con datos validados y el tutor las firma.

Cómo funciona:

1. **Plataforma web de padres.** El padre se registra con su correo (confirmado con un código), captura los datos del alumno y sube cada documento. Al subirlo, una revisión rápida avisa si la foto está borrosa o no es el documento pedido.
2. **Plantilla de lo esperado** por tipo y versión: textos fijos, campos y formatos, contenido del QR y reglas internas y cruzadas. Se arma con ejemplos tachados, sin datos de nadie.
3. **Validación automática.** Procesos fijos y el cerebro (PC 4) leen texto, QR y OCR, comparan con la plantilla y el expediente, y anotan inconsistencias.
4. **Existencia de la CURP.** Se revisa el dígito verificador y luego el QR del acta, validado en gob.mx (por probar si tiene captcha). Las excepciones las consulta en RENAPO una persona, por lote. No hay API pública; el servicio web es por convenio con secretarías estatales de educación. `backend/conectores/renapo.py` devuelve datos simulados y debe reemplazarse.
5. **Autorización manual.** El sistema muestra al administrador qué falta y qué inconsistencias encontró. Solo el administrador dice sí o no (se mantiene ADR-023). Con el sí, el padre recibe un correo positivo. Con el no, el sistema le envía el reporte de inconsistencias y qué corregir, hecho con plantillas fijas y sin copias de documentos.
6. **Datos para análisis.** Los campos extraídos se guardan ordenados y se analizan en cifras agregadas por grupo y ciclo.

| Paso | Qué | Listo cuando |
|---|---|---|
| 1 | Ejemplos tachados de cada documento (varios modelos de INE y actas de distintos estados) | Hay un ejemplo de cada tipo |
| 2 | Una plantilla por tipo y versión | Cada tipo tiene plantilla aprobada |
| 3 | Comparador: reglas fijas, internas y cruzadas; reemplazo del conector simulado | Pruebas con documentos buenos y malos pasan |
| 4 | Cerebro lector en la PC 4 (tipo, texto, QR, OCR), medido con fotos de celular | Se sabe cuánto lee bien y cuánto tarda |
| 5 | Existencia de la CURP: probar la validación del QR del acta; RENAPO por lote para excepciones | Se sabe qué parte es automática |
| 6 | Correos de resultado con plantillas y registro de envíos | Un padre de prueba recibe ambos correos |
| 7 | Plataforma web de padres | Un padre de prueba completa su expediente desde el celular |
| 8 | Pantalla del administrador: lo que falta, inconsistencias y sí o no | Un lote de prueba se autoriza en minutos |
| 9 | Análisis de los datos extraídos | Hay un reporte con datos de prueba |
| 10 | Modelo de visión local, solo si el OCR no alcanza | Decidido con las mediciones |

Nuevo orden: fase A con los pasos 1 a 5 en paralelo; fase B; fase C con los pasos 6 a 8; fase E de copias; la plataforma se abre a familias reales y después el análisis. Urgen el aviso de privacidad (incluido el uso para estadística), quién paga el hospedaje y la cuenta de correo de envío.

## Reglas de trabajo

1. No se escribe un ADR nuevo sin haber probado lo que decide.
2. Una fase a la vez; cada una termina con algo que se enseña a la secretaria.
3. Nada fuera de [VISION.md](VISION.md) hasta después del piloto.
4. La clave de la escuela y los `.exe` con paquete nunca van a Git ni a CI.
