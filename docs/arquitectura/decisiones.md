# Decisiones de arquitectura

## ADR-001 — Dos productos y un agente, un monorepo

Aceptada. Entradas independientes y contratos compartidos; sin imports cruzados de implementación. Facilita desarrollo individual sin acoplar arranques.

## ADR-002 — Monolito modular, ejecución distribuida

Aceptada. No un microservicio por función escolar. Menos despliegues y una autoridad consistente, con trabajadores independientes.

## ADR-003 — Servidor escolar local

Objetivo aceptado; instalación pendiente. La LAN funciona sin Internet. Acceso remoto requiere HTTPS y permisos; nube opcional para respaldo/servicios.

## ADR-004 — SQLite transitorio

Mantener datos existentes y cola separada durante arquitectura. No compartir archivos por SMB. PostgreSQL y migración de datos pendientes antes del despliegue escolar. No hay transacción entre las dos bases actuales.

## ADR-005 — Repetición tolerable, efectos protegidos

Idempotencia de creación, reserva exclusiva y confirmación deduplicada. No prometer ejecución exactamente una vez. Acciones externas necesitan reconciliación previa al reintento.

## ADR-006 — Autonomía mediante políticas

Cerebro coordina, plataforma autoriza. Sin shell genérico ni autoprogramación. IA opcional. Mantenimiento automático solo mediante procedimientos aprobados y reversibles.

## ADR-007 — Documentos fuera de alcance

Por solicitud del usuario, no implementar CURP, actas ni OCR. Conservar simulación histórica sin exponerla como servicio real; ruta devuelve 501.
