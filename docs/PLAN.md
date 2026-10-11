# Plan de construcción

| Fase | Estado | Entregable / aceptación |
|---|---|---|
| 0 Arquitectura | Documentada | Límites, ADR, protocolos, recursos y recuperación |
| 1 Separación | Implementada | Entradas independientes, fronteras de importación verificadas |
| 2 Flujo técnico | Implementada | Crear, reclamar y completar echo; identidad técnica y capacidades |
| 3 Resiliencia mínima | Implementada | Persistencia, duplicados, concurrencia, reserva vencida y límite |
| 3b Base de instalación | **Implementada** | Ejecutable único, paquete, descubrimiento firmado, TLS fijado, enrolamiento con aprobación e invitación, revocación, supervisor, módulos y una base WAL con migraciones por módulo |
| 4 Identidad escolar | Pendiente | Login del personal, sesiones, roles escolares por ámbito y aprobaciones |
| 5 Persistencia producción | Pendiente | Copia en caliente programada, archivos escolares con manifiesto, restauración ensayada |
| 6 Cerebro ampliado | Pendiente | Supervisor continuo, plan multietapa persistente, políticas y explicación |
| 7 Agentes ampliados | Pendiente | Manifiestos y límites por capacidad, renovación de reservas, actualización firmada del ejecutable |
| 8 Sincronización | Pendiente | Diario de captura escolar sin conexión y conflictos explícitos |
| 9 Interfaz/operación | Pendiente | Panel del personal, equipos y tareas, salud y alertas |
| 10 Piloto | Pendiente | Medir recuperación en los tres equipos reales con datos de prueba |

## Próximo incremento

1. Rotación de secreto y certificado de la instalación, y expiración de tokens.
2. Copia en caliente (`VACUUM INTO`) programada desde el supervisor del servidor.
3. Login del personal (fase 4) como módulo `personal`, sobre el contrato de módulos.
4. Interfaz mínima servida desde `backend/static`: estado de equipos, aprobaciones y tareas.

Las funciones escolares nuevas esperan a cerrar la fase 4.

## Aceptación objetivo

- [x] Sin cerebro, el operador consulta, registra y crea tareas.
- [x] Los reinicios conservan tareas y resultados confirmados.
- [x] Dos agentes nunca comparten una reserva vigente.
- [x] Una reserva antigua no modifica una tarea reasignada.
- [x] Un token revocado deja de operar (el agente sale con código 3).
- [x] Un equipo nuevo se une abriendo el ejecutable y con la aprobación del administrador.
- [x] Un impostor sin el secreto no responde al descubrimiento ni puede enrolarse; un certificado distinto se rechaza.
- [x] Sin LAN no se afirma confirmación central.
- [ ] Ediciones escolares concurrentes producen un conflicto visible.
- [ ] Un respaldo restaura datos y archivos del mismo punto.

Las pruebas automáticas (`pruebas/`) cubren lo marcado, incluido un servidor TLS real y descubrimiento UDP en loopback. No equivalen a un ensayo de apagón físico con los tres equipos.

## Decisiones del piloto

Confirmar sistemas operativos, servidor, energía/UPS, LAN (difusión permitida o IP fija), periféricos y acceso externo. Propuesta a validar: copia diaria externa y recuperación en una jornada; no es una garantía medida. No prometer años sin mantenimiento.
