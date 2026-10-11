# SQL, operaciones transaccionales y procedimientos

## Decisión

Motor actual: SQLite local al servidor, WAL, claves foráneas y synchronous=FULL. SQL nunca viaja desde los agentes. Cada módulo posee tablas y publica servicios; las API invocan operaciones de dominio con permisos.

SQLite no admite procedimientos almacenados CREATE PROCEDURE. Las rutinas de abajo son servicios Python transaccionales, no SQL/PL ni funciones remotas arbitrarias. PostgreSQL se estudió como alternativa, no se implementó un segundo motor sin necesidad medida. Ver fuentes y comparativa en la investigación.

## Modelo físico añadido

| Objeto | Clave / restricción | Propósito |
|---|---|---|
| salida_eventos | id único, secuencia creciente, versión=1, JSON válido | Outbox durable |
| politicas_nodo | dispositivo FK, revisión positiva | Configuración con concurrencia optimista |
| telemetria | dispositivo FK, última recepción del servidor | Muestra actual, sin historial creciente |
| tareas.iniciada | Inicio por intento | Tope de renovación |
| dispositivos.recursos | Booleano | Exigir muestra vigente a agentes nuevos |
| tarea_unica_por_agente | Índice único parcial de tareas ejecutando | Invariante de concurrencia |
| tarea_terminal_inmutable | Trigger | Impedir regresar una tarea terminal a ejecución |
| resumen_cola | Vista SQL por estado | Observación operativa |

Las migraciones anteriores no se modifican. Orquestación agrega migración 3; mensajería comienza en 1. Migraciones y versión se confirman bajo el mismo bloqueo de escritura. Si fallan, se revierte todo el módulo pendiente; dos arranques concurrentes no aplican dos veces un ALTER.

## Operaciones del servidor

| Servicio | Transacción y garantías |
|---|---|
| crear | Consultar actor+clave, comprobar cupo, insertar tarea y evento; repetición idéntica recupera tarea |
| reclamar | Recuperar reservas vencidas, validar cupo/capacidad/recursos, asignar token e inicio, publicar evento |
| renovar | Verificar actor/token/estado/vigencia; extender hasta el máximo del intento |
| completar | Validar reserva y resultado; terminal y evento atómicos; repetición idéntica no duplica |
| cambiar_politica | Revisar versión esperada; escribir nueva revisión y evento dentro del bloqueo |
| publicar | Usar la conexión/transacción del cambio; nunca abrir una segunda conexión |

El trigger es una defensa de integridad, no el motor de procesos. No meter HTTP, IA, esperas, llamadas a periféricos ni lógica externa dentro de una transacción SQL.

## Esquema revisable

`python -m herramientas.exportar_esquema` genera `database/esquema_actual.sql` desde una base temporal creada con migraciones reales. Incluye tablas, índices, vistas, trigger y versiones. Solo sirve para inspección o base nueva; no ejecutarlo sobre una base existente. No contiene usuarios, tokens ni expedientes.

## Relación con futuros procedimientos PostgreSQL

Si aparecen muchos escritores, bloqueo sostenido o requisitos de réplica, medir y comparar PostgreSQL. Un adaptador podría encapsular reclamar/confirmar en funciones o procedimientos; SELECT FOR UPDATE SKIP LOCKED es una opción para colas. No cambiar nombres/semántica de API ni hacer que agentes se conecten al motor. Repetir las pruebas de idempotencia, rollback, vencimiento, duplicados y permisos antes de cambiar.

No hay procedimiento PostgreSQL ejecutado en esta entrega. El código SQL incorporado es compatible con el motor activo y está probado.

## Copia verificable

`python -m sidp respaldo --destino RUTA_NUEVA.db` en el servidor usa Backup API y genera un manifiesto JSON con hash y versiones. Permite copiar durante operación sin copiar manualmente un WAL activo. Si el comando falla o falta el manifiesto, no considerar completada la copia. Un hash detecta cambios accidentales, no autentica una copia frente a un adversario.

Ensayo: detener plataforma antes de sustituir su archivo; verificar hash, quick_check y foreign_key_check en la copia; restaurar en SIDP_HOME de prueba, con claves/configuración compatibles; comparar datos y arrancar un único servidor. El respaldo no incluye secretos ni futuros archivos externos. No reemplazar el servidor activo sin una ventana y copia previa.
