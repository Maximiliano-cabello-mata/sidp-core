# Plan de construcción

| Fase | Estado | Entregable / aceptación |
|---|---|---|
| 0 Arquitectura | Documentada | Límites, ADR, protocolos y recuperación |
| 1 Separación | Implementada | Entradas independientes, sin imports cruzados |
| 2 Flujo técnico | Implementada | Crear/reclamar/completar echo, identidad técnica y capacidades |
| 3 Resiliencia mínima | Implementada | Persistencia, duplicados, concurrencia, reserva vencida y límite |
| 4 Identidad escolar | Pendiente | Login, sesiones, ámbito, aprobación y revocación de equipo |
| 5 Persistencia producción | Pendiente | PostgreSQL, migraciones escolares, archivos y restauración |
| 6 Cerebro ampliado | Pendiente | Plan multietapa persistente, políticas, supervisión y explicación |
| 7 Agentes ampliados | Pendiente | Manifiestos, límites, renovación y actualización firmada |
| 8 Sincronización | Pendiente | Diario de captura escolar y conflictos explícitos |
| 9 Interfaz/operación | Pendiente | Panel de personal, equipos/tareas, salud real y alertas |
| 10 Piloto | Pendiente | Medir recuperación en equipos reales con datos de prueba |

## Próximo incremento

Login y permisos escolares; separar rutas de alumnos; migraciones escolares en lugar de create_all; salud de disco/base. Después planes multietapa y agentes ampliados. No funciones documentales hasta cerrar contratos de módulos.

## Aceptación objetivo

- Sin cerebro, operador consulta/registra y crea tareas.
- Reinicios conservan tareas y resultados confirmados.
- Dos agentes nunca comparten reserva vigente.
- Reserva antigua no modifica tarea reasignada.
- Token revocado deja de operar.
- Sin LAN no se afirma confirmación central.
- Ediciones escolares concurrentes producen conflicto visible.
- Respaldo restaura datos y archivos del mismo punto.

Últimas tres condiciones necesitan componentes pendientes. Las pruebas iniciales verifican API sin cerebro, reinicio del almacén/diario, permisos, concurrencia y reintentos; no equivalen a ensayo de apagón físico.

## Decisiones del piloto

Confirmar sistemas operativos, servidor, energía/UPS, LAN, periféricos y acceso externo. Propuesta a validar: copia diaria externa y recuperación en una jornada; no garantía medida. No prometer años sin mantenimiento.
