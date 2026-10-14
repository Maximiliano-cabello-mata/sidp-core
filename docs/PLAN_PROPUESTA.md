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

El buzón y el cerebro ya no van al final: ver la sección de validación. Después: docentes, formatos y piloto.

## Validación de documentos: los padres suben, el cerebro valida

Corregido el 2026-10-14 con la idea de Maximiliano. Amplía [validacion_documental.md](arquitectura/validacion_documental.md) (ADR-022).

Documentos:

- **Alumno:** CURP, acta de nacimiento, certificado médico, boletas de los grados cursados.
- **Tutor:** INE, acta de nacimiento (prueba el parentesco con el acta del alumno), CURP, comprobante de domicilio.
- **Formatos:** ficha de inscripción y ficha de autorización. SIDP las llena con datos validados y el tutor las firma.

Faltan en `tipo_documento`: acta y CURP del tutor, ficha de inscripción y autorización.

Cómo funciona:

1. **Los padres suben todo por el buzón** (ADR-028). La ventanilla con escáner queda como respaldo.
2. **Cada tipo y versión de documento tiene una plantilla de lo esperado**: textos fijos para reconocerlo, campos y formatos, qué debe decir su QR y reglas internas y cruzadas. Se arma con ejemplos tachados y no contiene datos de nadie.
3. **El cerebro (PC 4) valida contra la plantilla**: reconoce el tipo, lee texto, QR y OCR, compara y marca inconsistencias. Por ejemplo, que el QR del acta no diga lo impreso o que la fecha de la INE no sea la de su CURP. Deja el resultado en `sugerencia_ia`.
4. **RENAPO lo consulta una persona**, porque gob.mx/curp tiene captcha. El cerebro lee el PDF descargado y lo cruza con el acta y la INE. No hay API pública; el servicio web es por convenio con secretarías estatales de educación. No se usan APIs de terceros. `backend/conectores/renapo.py` devuelve datos simulados y debe reemplazarse.
5. **La secretaría confirma, corrige o rechaza con motivo**, y el padre ve el resultado en el buzón.

| Paso | Qué | Listo cuando |
|---|---|---|
| 1 | Juntar ejemplos tachados de cada documento (varios modelos de INE y actas de distintos estados) | Hay un ejemplo de cada tipo |
| 2 | Una plantilla por tipo y versión | Cada tipo tiene plantilla aprobada |
| 3 | Comparador: reglas fijas, internas y cruzadas; reemplazo del conector simulado | Pruebas con documentos buenos y malos pasan |
| 4 | Cerebro lector en la PC 4 (tipo, texto, QR, OCR), medido con fotos de celular | Se sabe cuánto lee bien y cuánto tarda |
| 5 | RENAPO con persona y lectura del PDF por el cerebro | Una CURP queda verificada con su PDF |
| 6 | Pantalla de revisión de la secretaría (fase C) | Un expediente de prueba se revisa en minutos |
| 7 | Buzón de padres | Un padre de prueba sube su expediente desde el celular |
| 8 | Modelo de visión local, solo si el OCR no alcanza | Decidido con las mediciones |

Nuevo orden: fase A con los pasos 1 a 4 en paralelo; fase B; fase C con la validación (pasos 5 y 6); fase E de copias; buzón (paso 7), porque con él entran documentos reales. La búsqueda (fase D) puede ir después. Se vuelven urgentes quién paga el buzón y el aviso de privacidad.

## Reglas de trabajo

1. No se escribe un ADR nuevo sin haber probado lo que decide.
2. Una fase a la vez; cada una termina con algo que se enseña a la secretaria.
3. Nada fuera de [VISION.md](VISION.md) hasta después del piloto.
4. La clave de la escuela y los `.exe` con paquete nunca van a Git ni a CI.
