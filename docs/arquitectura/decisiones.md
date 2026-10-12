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

## ADR-008 - Nube como autoridad de datos (reemplaza parcialmente ADR-003 y ADR-004)

Aceptada 2026-10-11. No hay servidor escolar: las PCs no son confiables como servidor. La autoridad de escritura es una plataforma en la nube con PostgreSQL administrado, HTTPS y respaldos. PCs (.exe) y celulares (PWA) son clientes con cache de lectura y cola de cambios pendientes. Agentes siguen iniciando conexiones salientes. Respaldo mensual exportable a disco escolar para no depender de un proveedor. Privacidad de menores: roles por grupo, auditoria y cifrado son requisito previo a datos reales.

## ADR-009 - Nucleo consolidado y modulos de automatizacion

Aceptada 2026-10-11. El nucleo ofrece identidad, roles, sincronizacion, documentos, auditoria, cola de tareas y dispositivos. Cada funcion escolar (calificaciones, reportes, planes, anuncios, impresion) es un modulo con contrato propio que usa solo interfaces del nucleo. Prioridad: automatizar trabajo manual repetitivo (boletas, reportes, avisos) sobre una base estable. La IA es modulo opcional, fuera de la ruta critica y sin datos de alumnos por defecto.

## ADR-010 - Replicas locales y cuenta Microsoft institucional como transporte y respaldo (ajusta ADR-008)

Aceptada 2026-10-11, pendiente de validar permisos con el administrador de la cuenta. No hay presupuesto para base de datos ni servidor en la nube; se dispone de una cuenta Microsoft institucional con 100 GB. Se conservan ADR-001, 002, 005, 006, 007 y 009. De ADR-008 se mantiene: sin servidor escolar, clientes con cola offline, privacidad de menores como requisito. Cambia: no hay autoridad central; cada dispositivo guarda su replica en SQLite y OneDrive/SharePoint transporta cambios y respalda.

Reglas:
1. Nunca sincronizar el archivo SQLite con OneDrive (se corrompe). Se sincronizan archivos de diario inmutables.
2. Cada dispositivo escribe solo su propio diario (append-only, por segmentos); los demas lo leen y lo aplican. Sin escritores concurrentes sobre un mismo archivo.
3. Cada dato tiene un dueno escritor (docente sobre sus calificaciones). Conflictos restantes se muestran, no se resuelven por reloj del dispositivo; se usa reloj logico hibrido y version esperada.
4. Un nodo de respaldo (PC del cerebro, cuando este encendida) compacta diarios y genera instantaneas; la nube guarda copias, no es autoridad.
5. Documentos grandes viven en SharePoint/OneDrive con metadatos y hash en la replica; cada equipo cachea lo que usa. Cuota de 100 GB vigilada con alerta.
6. Anuncios y foro pueden apoyarse en Teams/SharePoint de la institucion en lugar de construirse, si el administrador lo permite.
7. Los datos en transito/reposo se cifran con clave de la escuela antes de subir; la cuenta Microsoft no ve expedientes en claro si se puede evitar.

## ADR-011 - Expediente documental como modulo principal (sustituye ADR-007)

Aceptada 2026-10-11. Por indicacion del usuario, el foro/anuncios queda fuera de alcance y los documentos del alumno (CURP, acta, certificado medico, calificaciones anteriores, carta responsiva y otros) pasan a ser un modulo central. ADR-007 queda sustituido. Validacion en dos niveles: comprobaciones automaticas locales y cotejo humano, que es el unico que marca un documento como validado. Consulta oficial en linea (por ejemplo CURP) es opcion futura por confirmar; la ruta heredada con simulacion RENAPO sigue devolviendo 501.

## ADR-012 - Dos plataformas sobre un nucleo; el cerebro es un producto aparte

Aceptada 2026-10-11. Plataforma de docentes (evaluaciones, asistencia, reportes, contacto con padres) y plataforma de administrativos (expediente, documentos, estadistica, impresion) sobre un mismo nucleo. El sistema administrativo es completo y opera sin el cerebro. El cerebro es un producto distinto, desarrollado en la rama `cerebro`, que en el futuro se conecta como un cliente mas de la API publica del sistema con identidad y permisos propios. El sistema administrativo no importa codigo del cerebro, no lo necesita para arrancar y solo expone puntos de integracion (API, auditoria, tareas). Ajusta ADR-006.
