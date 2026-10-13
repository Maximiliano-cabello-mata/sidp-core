# Modulos, plataformas y nucleo

Fecha: 2026-10-11, revisado 2026-10-13. Desarrolla ADR-021 y ADR-023. Las reglas tecnicas para escribir un modulo estan en `modulos.md`. El cerebro no forma parte de este catalogo: es un producto aparte (`cerebro_aprendizaje.md`). Foro y anuncios quedan fuera de alcance. El alcance cerrado del producto, con los módulos añadidos el 2026-10-13 (asistencia de profesores, exámenes diagnósticos, inventario, catálogo de formatos, escaneo y buzón de padres), está en [VISION.md](../VISION.md).

## Dos plataformas sobre un mismo nucleo

| Plataforma | Usuarios | Dispositivos | Funciones |
|---|---|---|---|
| Docentes | Profesores | Celular (PWA) y PC | Subir evaluaciones de examen, registrar asistencia, crear reportes de alumno, contactar padres |
| Administrativos | Direccion, administrativos, contabilidad | PC (.exe) | Inscripcion y expediente documental, validar documentos, estadistica, estudios de poblacion, comunicacion con padres, impresion |

Ambas usan la misma plataforma: alumnos, grupos, ciclo escolar, identidad y documentos. Los modulos no comparten codigo entre si.

## Nucleo (se construye primero)

| Pieza | Responsabilidad |
|---|---|
| Identidad | Usuarios, roles (direccion, subdireccion, docente, administrativo, contabilidad, admin tecnico), sesiones, alcance por grupo |
| Dispositivos | Enrolamiento con aprobacion o invitacion, revocacion, telemetria y politica por equipo (implementado) |
| Concurrencia | UUID, version esperada y conflictos explicitos al guardar |
| Documentos | Archivos, metadatos, hash, versiones |
| Auditoria | Quien cambio que y cuando |
| Tareas | Cola con capacidades, tareas dirigidas, renovacion de reserva (implementado); estado incierto para efectos externos (pendiente) |
| Comunicacion | Mensajes a padres con plantillas, aprobacion y registro de entrega |
| Integracion | API versionada y diario de eventos con cursor (implementado) que un cliente externo, como el cerebro, usa con su propia identidad |

## Modulos (cada uno con contrato propio)

| Modulo | Plataforma | Automatiza |
|---|---|---|
| Alumnos y grupos | Ambas | Consulta y datos base |
| Inscripcion y expediente | Administrativos | Requisitos por alumno y ciclo, validacion, prorrogas (ver modulo_expediente.md) |
| Evaluaciones | Docentes | Captura de examenes, concentrados y boletas |
| Asistencia | Docentes | Registro diario, alertas por faltas |
| Reportes de alumno | Docentes y administrativos | Registro y seguimiento |
| Contacto con padres | Ambas | Aviso desde el celular con plantilla, aprobacion cuando aplique y constancia |
| Documentos PDF | Administrativos | Generar, combinar, imprimir; conversion a editable por herramienta determinista |
| Estadistica y poblacion | Administrativos | Graficas de resultados y estudios de poblacion de alumnos y padres |
| Impresion | Administrativos | Trabajos a impresoras WiFi via agente en una PC; sin doble impresion |

## Reglas

1. Un modulo no importa a otro; se comunican por el nucleo.
2. Un solo escritor por dato (docente dueno de sus evaluaciones y asistencia) para minimizar conflictos.
3. Un cliente sin conexion con la plataforma puede consultar lo ya cargado, pero no afirma que un cambio quedo guardado hasta que la plataforma lo confirma.
4. Todo modulo declara permisos, eventos y migraciones propios.
5. Mensajes a padres y acciones con efecto externo registran estado incierto hasta confirmar entrega; no se reintentan a ciegas.
6. Estadisticas que salgan de la plataforma usan datos agregados o anonimizados.
7. Todo el sistema opera sin el cerebro; nada del sistema administrativo importa codigo del cerebro.

## Conexion y respaldo (ADR-019, ADR-020)

| Necesidad | Solucion sin costo |
|---|---|
| Almacenar datos | Una base SQLite en la PC administrativa (plataforma) |
| Compartir datos | Los demas equipos y celulares se conectan a la plataforma por la LAN |
| Repartir trabajo | Cola de tareas: agentes en otras PC (impresion, OCR, PDF) |
| Respaldo | Copia diaria cifrada en la cuenta institucional y copia externa mensual |
| Celulares | PWA contra la plataforma; certificado por decidir (ADR-020) |
| Fuera de la escuela | Tunel saliente con login del personal (ADR-020, pendiente) |
| Aviso a padres | Requiere Internet; sin conexion queda pendiente de envio, no como enviado |
| Impresion | Tarea dirigida al agente de la PC que tiene acceso a la impresora |

Limites asumidos: si la PC administrativa esta apagada no hay escrituras; la cuenta Microsoft no es autoridad de datos. Las replicas por dispositivo con sincronizacion por OneDrive quedan como mejora futura (ADR-019). El canal para contactar padres (correo, WhatsApp, SMS) esta por definir.
