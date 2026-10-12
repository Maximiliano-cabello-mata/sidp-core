# Protocolo común de comunicación y recursos

## Canales

Descubrimiento UDP firmado localiza al servidor; no transporta tareas ni expedientes. HTTPS con credencial identifica cada petición. API síncrona confirma cambios cortos. Cola de tareas coordina ejecución diferida. GET de eventos permite observar cambios desde un cursor durable. No se abren puertos de escucha en agentes.

## Nuevas rutas

| Ruta bajo /api/v1 | Rol | Contrato |
|---|---|---|
| POST /dispositivos/latido | agente | Telemetria: CPU 0..100, RAM/disco disponibles en MB |
| GET /dispositivos/politica | agente | Política propia y revisión |
| GET /dispositivos | admin | Equipos y políticas actuales |
| PUT /dispositivos/{id}/politica | admin | CambiarPolitica con revision_esperada |
| POST /tareas/{id}/renovar | agente | Renovacion con token de reserva |
| GET /tareas/resumen | admin | Vista por estado y límites actuales |
| GET /eventos?despues=0&limite=100 | admin/cerebro | LoteEventos v1 y siguiente cursor; máximo 200 |

El cerebro ve solo eventos de tareas que creó y de operaciones cuyo propietario coincide con su identidad. No tiene autorización global sobre la escuela. Admin puede revisar todo el diario. La API no admite publicar cualquier evento desde clientes: los servicios de plataforma producen eventos.

## Política por equipo

Ejemplo para un dispositivo registrado `aula-agente`:

```json
{"version":1,"revision_esperada":0,"politica":{"version":1,"pausado":false,"cpu_maxima":85,"memoria_minima_mb":256,"disco_minimo_mb":200}}
```

PUT devuelve nueva revisión; una revisión antigua responde 409. Pausar impide nueva asignación, pero no descarta ni cancela resultados ya ejecutados. Los campos son límites de admisión, no cuotas duras de cgroups/Job Objects. El agente conserva la capacidad echo; no puede descargar ni ejecutar código remoto.

## Parámetros locales acotados

SIDP_COLA (JSON en servidor): pendientes_maximos=1000, ejecuciones_maximas=2, reserva_s=60, duracion_maxima_s=600, telemetria_vigente_s=90. Cambios requieren reiniciar servidor. Una tarea por agente es invariante SQL y no configurable todavía. Cola llena responde 429 con Retry-After=10; reintentar la misma clave, no inventar otra.

SIDP_TRANSPORTE (JSON por proceso): conexion_s=3, lectura_s=10, conexiones=4, espera_minima_s=2, espera_maxima_s=30. Son configuración técnica, no comandos remotos. Valores fuera de rangos se rechazan al cargar. Sondeo ocioso aumenta espera; fallos usan backoff con jitter. No se agrega reintento genérico de POST en httpx. El agente repite su protocolo idempotente.

Ejemplo Bash:

```bash
export SIDP_COLA='{"pendientes_maximos":100,"ejecuciones_maximas":2}'
export SIDP_TRANSPORTE='{"conexion_s":3,"lectura_s":10,"conexiones":4}'
```

PowerShell usa `$env:SIDP_COLA='...'`. En agentes actuales, el primer latido habilita permanentemente la exigencia de telemetría vigente. Agentes v1 sin telemetría conservan compatibilidad limitada para echo y respetan pausa/cupo; actualizar todos antes de tareas costosas. La muestra es declarada por el agente autorizado, no una prueba contra un equipo comprometido.

## Reservas

Renovación solo antes del vencimiento y con el mismo actor/token. Límite total por intento. Un executor futuro de larga duración debe renovar antes de un tercio del plazo restante y detenerse/reconciliar si pierde reserva. El echo actual es inmediato y no necesita hilo de renovación. No se habilitan efectos externos mientras no exista reconciliación.

## Diario y consumidor

Cada evento contiene UUID, versión, secuencia del servidor, tipo, correlación, propietario, fecha y metadatos sin mensaje del alumno. El cliente pide desde su último cursor. UUID deduplica; secuencia ordena dentro de una instalación. No ordenar por reloj del equipo. No hay orden global entre instalaciones.

Cerebro `--servicio` almacena inbox y cursor en SIDP_HOME/cerebro/eventos.db. Una caída antes del commit provoca repetición segura. No dispara todavía nuevas acciones administrativas. `--clave` sigue creando un diagnóstico puntual. El supervisor arranca el modo servicio, evitando repetir un comando incompleto.

## Extender un proceso

1. Definir entrada/salida y versión en contratos.
2. Declarar permisos, idempotencia y política de efecto incierto.
3. Implementar servicio transaccional en módulo y publicar evento con su mismo db.
4. Añadir capacidad incorporada si requiere otra computadora.
5. Definir requisitos/renovación y pruebas de saturación, caída y repetición.
6. Registrar módulo y actualizar diagrama/contratos.

No existe un motor que paralelice automáticamente cualquier proceso. Esta base ofrece canales y garantías para incorporar cada proceso sin reinventar comunicación.

## Límites presentes

Un servidor sigue siendo punto de fallo. Sin conexión no hay nuevas confirmaciones; solo pendientes locales. No hay captura escolar offline, broker MQTT, streaming, réplica automática, retención/purga de eventos ni límites duros del SO. Los lotes limitan cada lectura, no el tamaño total del diario: medir disco y añadir retención coordinada con cursores antes de operación prolongada.

La outbox comienza con los eventos producidos después de esta migración. No reconstruye automáticamente el historial de la tabla eventos del prototipo. Para tareas anteriores consultar su estado actual; no asumir que un consumidor recibirá su creación histórica.
