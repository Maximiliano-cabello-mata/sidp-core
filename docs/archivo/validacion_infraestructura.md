# Validación de la base de infraestructura

Base de trabajo: 1f49e4bd12a2c86fbd2e0dd0bdeceb49a5fcfaa1, rama claude/epic-darwin-4nvkur. Entorno local: Python 3.12/Linux. No se modificaron datos de una instalación escolar.

## Evidencia

- `python -m pytest -q`: 34 pruebas aprobadas. Advertencia existente de deprecación Starlette TestClient/httpx; sin fallos.
- Prueba con procesos separados y HTTPS real: plataforma, agente y cerebro --servicio. Una tarea del cerebro completada por agente con telemetría; tres eventos guardados por consumidor durable.
- SQL exportado desde migraciones se instala en base temporal y conserva versiones/vista.
- Copia con Backup API se reabre y mantiene identidad de la tarea al repetir su clave.

## Casos cubiertos

| Garantía | Evidencia automatizada |
|---|---|
| Plataforma sin cerebro | API escolar y cola funcionan sin proceso coordinador |
| Cola limitada | Saturación rechaza nuevas tareas; repetición de una existente funciona |
| Recursos | CPU/RAM/disco insuficientes y muestras antiguas impiden asignación |
| Configuración | Dos escrituras con la misma revisión: una gana y otra recibe conflicto |
| Reservas | Token ajeno/vencido rechazado y renovación acotada por intento |
| Mensajería | Rollback no deja evento; lectura por propietario; inbox deduplica tras reinicio |
| SQL | Migración concurrente se aplica una vez; error revierte DDL y versión |
| Red | TLS real acepta certificado escolar y rechaza otro; contexto no carga CA del sistema |
| Identidad | Aprobación, invitación única y revocación heredadas continúan pasando |
| Procesos | Supervisor usa cerebro --servicio; prueba real mantiene consumidor vivo |

## Alcance de la evidencia

No se ejecutó esta revisión local en Windows ni en las tres computadoras de la escuela; CI conserva matriz Windows/Linux y compilación del .exe para verificarlo en GitHub. No hay benchmark ni garantía de memoria/latencia. No se ensayó corte eléctrico físico ni restauración de archivos escolares externos.

Antes del piloto: medir bloqueo SQL, CPU/RAM, tráfico y tiempo de recuperación; verificar permisos del directorio de secretos en Windows; planear rotación de certificados, retención de eventos y respaldo programado. La telemetría es cooperativa, no un límite duro del sistema operativo.
