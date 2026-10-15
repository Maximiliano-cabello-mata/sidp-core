# Plan de construcción

> **Plan vigente desde el 2026-10-14, sujeto a cambios mayores.** Junta la ruta anterior con la propuesta del 2026-10-14 ([bitácora](bitacoras/2026-10-14.md)). El alcance está cerrado en [VISION.md](VISION.md).

Documentos completos (Claude Docs):

- [SIDP: análisis y plan claro](https://claude.ai/code/artifact/885ebf90-7ec1-4528-9e65-57a22650d7cc): qué está mal, qué tenemos, diagramas y fases.
- [SIDP: cómo validar los documentos de inscripción](https://claude.ai/code/artifact/f40f536e-91ff-4ca8-8188-0207fa57928b): documentos, niveles de validación, CURP y RENAPO, cerebro y pasos.

## Diagnóstico

La conectividad funciona: dos PCs reales se unieron con la clave el 2026-10-13 ([bitácora](bitacoras/2026-10-13.md)). Pero la escuela todavía no puede usar nada: no hay cuentas del personal, expedientes ni pantallas, y la [base de datos integral](arquitectura/base_de_datos.md) de 39 tablas está diseñada sin usarse. En seis días se hicieron 40 commits y 29 ADR, casi todo de red.

## Paso 0: red congelada

No se agregan funciones de conexión. Solo se corrigen errores que salgan en la prueba de la escuela (3e). El reparto de tareas (ADR-026) se deja como está.

Base técnica ya construida ([detalle](arquitectura/base_tecnica.md)):

| Fase | Estado | Entregable |
|---|---|---|
| 0 a 3d | Implementadas | Arquitectura, separación de procesos, cola de tareas, resiliencia, instalación, conexión cifrada, tareas dirigidas y ensayo en CI con el `.exe` |
| 3f Recursos compartidos | Implementada | Clave de escuela (ADR-025), reparto de tareas y `sidp equipos` (ADR-026) |
| 3f2 Dos ejecutables | Implementada | `SIDP-Servidor.exe` y `SIDP-Equipo.exe` (ADR-029) |
| 3e Prueba con equipos reales | En curso | En casa: 11/11 OK ([2026-10-12](bitacoras/2026-10-12.md)) y PC2 unida con los dos `.exe` ([2026-10-13](bitacoras/2026-10-13.md)). Falta en la red de la escuela ([guía](guias/PRUEBA_DOS_EQUIPOS.md)) |
| 3g Copias automáticas | Pasa a la fase E | Ver abajo |

## Fases del producto escolar

Cada fase usa las tablas de [diseno_integral.sql](../database/diseno_integral.sql) y termina con algo que la secretaria usa desde el navegador. El backend hace tablas, reglas y API; la pantalla de cada fase se hace en la rama de diseño (`mi-nueva-rama`) sobre esa API, siguiendo las interfaces que Paola diseña en esa rama.

| Fase | Estado | Backend | Lista cuando |
|---|---|---|---|
| A. Cuentas | Siguiente | Usuarios del personal, roles (dirección, secretaría, docente, administrativo), sesión con vencimiento, límite de intentos, bitácora | Cada persona entra con su usuario y ve solo lo de su rol |
| B. Alumnos, tutores y grupos | Pendiente | Alumnos y tutores en las tablas nuevas (reemplazan `alumnos` del módulo `escolar`), ciclo y grupos, carga desde Excel | Un grupo real se carga desde Excel y un dato se corrige sin perder el anterior |
| C. Expediente | Pendiente | Recibir documentos, guardarlos sin sobrescribir, revisión con motivo, folio de recibido, correos de resultado y pantalla del administrador (pasos 6 a 8) | Secretaría arma el expediente de un grupo y ve qué falta |
| D. Búsqueda y faltantes | Pendiente | Búsqueda por nombre, CURP, grupo o tipo; faltantes por grupo; exportar todo | Cualquier alumno aparece en segundos |
| E. Copias (antes 3g) | Pendiente | Copia a otra PC unida y cada noche al disco externo; prueba de restauración; cambio de clave y arranque con Windows sin ventana (ADR-027) | Se apaga el servidor y no se pierde nada |

Después de E: docentes y dirección (asistencia, calificaciones, exámenes diagnósticos, inventario; decisión de certificado ADR-020), catálogo de formatos y piloto de una semana con la escuela completa.

## Validación de documentos y plataforma web de padres

Ya no va al final: avanza en paralelo desde la fase A. La validación funciona con procesos fijos y no depende de la IA (decisión del 2026-10-14): si la PC 4 está apagada, nada se detiene. El diseño está en [validación documental](arquitectura/validacion_documental.md#plataforma-web-de-padres-2026-10-14).

| Paso | Qué | Listo cuando |
|---|---|---|
| 1 | Ejemplos tachados de cada documento (varios modelos de INE y actas de distintos estados) | Hay un ejemplo de cada tipo |
| 2 | Una plantilla de lo esperado por tipo y versión | Cada tipo tiene plantilla aprobada |
| 3 | Comparador: reglas fijas, internas y cruzadas; reemplazo del conector simulado `backend/conectores/renapo.py` | Pruebas con documentos buenos y malos pasan |
| 4 | Lector con procesos fijos, sin IA: tipo por los textos de la plantilla, texto del PDF, QR, OCR clásico (Tesseract) y revisión de la foto; medido con fotos de celular | Se sabe cuánto lee bien y cuánto tarda; lo que no se lee pasa al administrador |
| 5 | Existencia de la CURP: probar la validación del QR del acta; RENAPO por lote para excepciones | Se sabe qué parte es automática |
| 6 | Correos de resultado con plantillas y registro de envíos | Un padre de prueba recibe ambos correos |
| 7 | Plataforma web de padres | Un padre de prueba completa su expediente desde el celular |
| 8 | Pantalla del administrador: lo que falta, inconsistencias y sí o no | Un lote de prueba se autoriza en minutos |
| 9 | Análisis de los datos extraídos | Hay un reporte con datos de prueba |
| 10 | Cerebro (`llama3.1` en la PC 4) que solo opina en la zona gris (nombres o domicilios parecidos); se mide en el [laboratorio](../cerebro/laboratorio/LEEME.md) | Se sabe si sus opiniones ayudan al administrador |

Avance del 2026-10-15:

- Hay una primera versión de los pasos 3 y 4 en [`validacion/`](../validacion/). Revisa un expediente completo: busca lo que el padre capturó dentro del texto de cada documento.
- La prueba oficial con documentos reales y falsos corre solo en la PC 4 ([guía](guias/PRUEBA_VALIDACION.md)).
- La base sigue siendo SQLite (decisión de Maximiliano). Sus procedimientos almacenados se traducen a funciones de Python en `database/procedimientos.py`.

## Orden de trabajo

1. Fase A, y en paralelo los pasos 1 a 5.
2. Fase B.
3. Fase C, con los pasos 6 a 8.
4. Fase E de copias, antes de cualquier dato real.
5. La plataforma se abre a familias reales (paso 7) y después el análisis (paso 9).
6. Fase D, docentes, formatos y piloto.

Urgen, antes del paso 7: el aviso de privacidad (incluido el uso para estadística), quién paga el hospedaje (ADR-028) y la cuenta de correo de envío.

## Reglas de trabajo

1. No se escribe un ADR nuevo sin haber probado lo que decide.
2. Una fase a la vez; cada una termina con algo que se enseña a la secretaria.
3. Nada fuera de [VISION.md](VISION.md) hasta después del piloto.
4. La clave de la escuela y los `.exe` con paquete nunca van a Git ni a CI.
5. Las bitácoras van en [bitacoras/](bitacoras/) con la fecha como nombre; lo que ya no rige va a [archivo/](archivo/).

## Aceptación objetivo

- [x] Sin cerebro, el operador consulta, registra y crea tareas.
- [x] Los reinicios conservan tareas y resultados confirmados.
- [x] Dos agentes nunca comparten una reserva vigente.
- [x] Una reserva antigua no modifica una tarea reasignada.
- [x] Un token revocado deja de operar (el agente sale con código 3).
- [x] Un equipo nuevo se une abriendo el ejecutable y con la aprobación del administrador.
- [x] Un impostor sin el secreto no responde al descubrimiento ni puede enrolarse; un certificado distinto se rechaza.
- [x] Sin LAN no se afirma confirmación central.
- [x] Una tarea creada en un equipo la ejecuta otro y se confirma de vuelta (ensayo con el `.exe` en CI).
- [x] Lo mismo, entre dos computadoras reales en una red de casa (2026-10-12, 11/11 OK).
- [ ] Lo mismo, en la red de la escuela.
- [x] El trabajo se reparte entre tres o más equipos (ensayo en CI).
- [ ] Cada persona entra con su usuario y ve solo lo de su rol (fase A).
- [ ] Ediciones escolares concurrentes producen un conflicto visible.
- [ ] Un padre de prueba recibe el correo positivo y el de inconsistencias.
- [ ] Un respaldo restaura datos y archivos del mismo punto.

Las pruebas automáticas (`pruebas/`) y el ensayo de CI cubren lo marcado. No equivalen a un ensayo de apagón físico ni a mediciones en los equipos de la escuela.

## Decisiones del piloto

Confirmar sistemas operativos, energía/UPS de la PC administrativa, LAN (difusión permitida o IP fija), periféricos y acceso externo. Propuesta a validar: copia diaria externa y recuperación en una jornada; no es una garantía medida. No prometer años sin mantenimiento.
