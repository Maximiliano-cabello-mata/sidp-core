# Operación y recuperación

## Instalación

La instalación del servidor y el alta de equipos están en [instalacion.md](instalacion.md). Diagnóstico de cualquier equipo: `sidp estado` muestra la carpeta, la instalación, los roles y el estado de cada credencial.

## Prueba de conectividad

`sidp prueba-conexion` en cualquier equipo: descubrimiento, puerto, TLS, reloj y credenciales. En el servidor añade el último contacto de cada agente y una ida y vuelta con cada agente remoto. Sale con código 0 si no hay fallas y guarda `registros/conectividad-*.json`. Abrir el cortafuegos del servidor (Windows, consola de administrador): `sidp cortafuegos`. Guía paso a paso: [PRUEBA_DOS_EQUIPOS.md](../PRUEBA_DOS_EQUIPOS.md).

## Salud

- `GET /api/salud` (cualquier identidad aprobada): comprueba que la base responde y el espacio libre en disco. Devuelve **verde**, o **amarillo** con menos de 200 MB libres. Si la base falla, responde 503: nunca un falso "vivo".
- `GET /api/v1/sistema/latido`: público y sin datos, solo para comprobar la URL.
- Registros: `SIDP_HOME/registros/<rol>.log`, rotación 1 MB × 3. No se registra cada petición HTTP.

## Datos

| Archivo | Equipo | Contenido |
|---|---|---|
| `plataforma/plataforma.db` (+ `-wal`, `-shm`) | servidor | Todos los módulos |
| `plataforma/tls/clave.pem` | servidor | Clave TLS (secreta) |
| `instalacion.json` | todos | Paquete (secreto de instalación) |
| `credenciales/*.json` | todos | Tokens propios |
| `agente/pendientes.db` | con agente | Resultados por entregar |

Migración desde el laboratorio anterior: la cola `datos/orquestacion.db` se adopta tal cual si se copia como `plataforma/plataforma.db`. Los alumnos de `backend/sidp_nodo_local.db` usan el mismo esquema y se copian con:

```sql
ATTACH 'sidp_nodo_local.db' AS viejo;
INSERT INTO alumnos SELECT * FROM viejo.alumnos;
INSERT INTO ciclos_escolares SELECT * FROM viejo.ciclos_escolares;
```

## Copia y restauración manual

1. Detener el nodo del servidor con Ctrl+C, o deteniendo la tarea programada. El supervisor detiene los roles en orden.
2. Copiar **toda** la carpeta `SIDP_HOME` del servidor (base, WAL, TLS, paquete y credenciales) a un medio externo restringido. Registrar la versión (`sidp estado`, `/api/v1/sistema`).
3. Verificar que la copia se lee y anotar la fecha.
4. Restaurar en otra carpeta con `SIDP_HOME` apuntando a ella. Probar en un puerto distinto, sin agentes productivos conectados.
5. Mantener **una sola plataforma** escribiendo. Antes de arrancar el servidor restaurado, apagar el anterior. Los agentes lo encontrarán solos si conserva el paquete.

Copia en caliente: pendiente (`sqlite3 .backup` o `VACUUM INTO` programado). Sin RPO/RTO medidos.

## Cambio de servidor

Copiar `SIDP_HOME` completo al equipo nuevo, apagar el anterior y arrancar el nuevo. El paquete y el certificado viajan con la carpeta, así que los agentes no notan el cambio salvo la IP, que redescubren solos.

## Actualizaciones

1. Respaldar (pasos anteriores).
2. Reemplazar `sidp.exe` primero en un equipo con solo agente y comprobar `sidp estado`.
3. Reemplazarlo en el servidor. Las migraciones se aplican solas al arrancar; si la base es más nueva que el ejecutable, la plataforma se niega a arrancar (volver a la versión nueva o restaurar la copia).
4. Reemplazarlo en los demás equipos. Los contratos v1 son compatibles entre versiones menores.

Pendiente: actualización firmada distribuida por la plataforma, con verificación de hash, salud y reversión.

## Incidentes frecuentes

| Síntoma | Causa probable | Acción |
|---|---|---|
| "No se encontró la plataforma en la red" | Servidor apagado, cortafuegos o difusión bloqueada | Encender el servidor, `sidp cortafuegos` en él, red marcada como Privada, o `sidp unirse --url https://IP:8443`. Diagnóstico: `sidp prueba-conexion` |
| `CERTIFICATE_VERIFY_FAILED` | El paquete no corresponde a este servidor | Usar el `instalacion.json` del servidor actual |
| Agente reinicia cada 60 s, registro "Credencial rechazada" | Identidad pendiente o revocada | `sidp identidades listar` / `aprobar` |
| 409 "La identidad ya existe" con `--equipo` | Reinstalación con nombre fijo | Revocar la identidad anterior y repetir |
| "Reloj del equipo desfasado" | Hora incorrecta | Sincronizar la hora del equipo |
| Salud amarilla | Disco casi lleno | Liberar espacio; revisar registros y copias |

## Observabilidad pendiente

Métricas de cola, pendientes y fallos por capacidad; latido visible por equipo en una interfaz; alertas para el personal; retención de eventos y auditoría.


## Copia en caliente y diario (base ampliada)

`sidp respaldo --destino RUTA_NUEVA.db` crea copia SQL consistente y JSON de hash/versiones; no reemplaza un archivo existente. No incluye archivos escolares ni secretos. Copia sin manifiesto o con comando fallido no se acepta. Ver sql-y-procedimientos.md para restauración.

Al restaurar una copia anterior, detener consumidores y reiniciar sus cursores a cero (`UPDATE cursores SET secuencia=0` en cada cerebro/eventos.db). Conservar recibidos para deduplicar UUID anteriores. No conservar un cursor adelantado respecto del servidor restaurado: ocultaría eventos nuevos hasta alcanzarlo. Reconciliar tareas externas antes de reconectar; actualmente solo echo.

Nuevas variables SIDP_TRANSPORTE y SIDP_COLA se validan al arrancar; ejemplos en comunicacion-y-recursos.md. La política por equipo se administra mediante API con revisión esperada. Un latido viejo bloquea asignación a agentes nuevos; no bloquea entrega de resultados existentes.
