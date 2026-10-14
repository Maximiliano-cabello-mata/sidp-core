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
3. **Validacion automatica.** Procesos fijos y el cerebro (PC 4) leen texto, QR y OCR, comparan con la plantilla y el expediente, y anotan inconsistencias. Es la revision superficial de los niveles 1 a 3.
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
