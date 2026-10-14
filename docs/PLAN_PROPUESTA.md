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

Después: docentes, formatos, piloto, buzón de padres y modelo de IA.

## Validación de documentos: empezar por el inicio del ciclo de vida

Amplía [validacion_documental.md](arquitectura/validacion_documental.md) (ADR-022) con la lista de documentos de la escuela:

- **Alumno:** CURP, acta de nacimiento, certificado médico, boletas de los grados cursados.
- **Tutor:** INE, acta de nacimiento (prueba el parentesco con el acta del alumno), CURP, comprobante de domicilio.
- **Formatos:** ficha de inscripción y ficha de autorización. SIDP las llena con datos validados, el tutor firma y se escanean.

Faltan en `tipo_documento`: acta y CURP del tutor, ficha de inscripción y autorización.

Tres niveles antes de la decisión humana: reglas fijas (dígito verificador de la CURP, fechas, vigencias), cruce entre documentos y verificación oficial asistida (QR del acta y de la INE, cédula del médico, consulta de CURP en gob.mx con constancia). RENAPO no ofrece API pública; su servicio web es por convenio con secretarías estatales de educación. Falta preguntar si el Estado de México lo tiene. No se usan APIs de terceros. `backend/conectores/renapo.py` devuelve datos simulados y debe reemplazarse.

El cerebro solo lee (texto del PDF, QR, OCR con Tesseract en la PC 4) y escribe propuestas en `sugerencia_ia`; sin él, la secretaria captura los campos. Los documentos no salen a la nube.

| Paso | Qué | Lista cuando |
|---|---|---|
| 1 | Juntar un ejemplo tachado de cada documento y formato; confirmar la lista con la escuela | Hay un ejemplo de cada tipo |
| 2 | Preguntar a la supervisión por el convenio con RENAPO y si el MIGE valida la CURP | Hay respuesta |
| 3 | Reglas fijas y reemplazo del conector simulado (en paralelo con la fase A) | Pruebas con CURP buenas y malas pasan |
| 4 | Cruce entre documentos con campos capturados a mano | Un expediente de prueba muestra qué coincide |
| 5 | Pantalla de revisión con decisión y motivo (fase C) | La secretaria valida un expediente de prueba |
| 6 | Cerebro: texto, QR y OCR; medir con 20 documentos tachados | Hay mediciones en la PC 4 |
| 7 | Verificación oficial asistida con constancia | Una CURP queda con su constancia |
| 8 | Modelo de visión local, solo si el OCR no alcanza | Decidido con las mediciones |

## Reglas de trabajo

1. No se escribe un ADR nuevo sin haber probado lo que decide.
2. Una fase a la vez; cada una termina con algo que se enseña a la secretaria.
3. Nada fuera de [VISION.md](VISION.md) hasta después del piloto.
4. La clave de la escuela y los `.exe` con paquete nunca van a Git ni a CI.
