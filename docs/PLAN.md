# Plan de construcción

Plan único del proyecto. Las fases de [sistema administrativo](arquitectura/sistema_administrativo.md#fases) y de [cerebro](arquitectura/cerebro_aprendizaje.md#fases) detallan el contenido de cada producto, pero el orden y el estado se llevan aquí.

## A. Base técnica

| Fase | Estado | Entregable |
|---|---|---|
| 0 Arquitectura | Documentada | Límites, ADR, protocolos, recursos y recuperación |
| 1 Separación | Implementada | Entradas independientes, fronteras de importación verificadas |
| 2 Flujo técnico | Implementada | Crear, reclamar y completar echo; identidad técnica y capacidades |
| 3 Resiliencia mínima | Implementada | Persistencia, duplicados, concurrencia, reserva vencida y límite |
| 3b Base de instalación | Implementada | Ejecutable único, paquete, descubrimiento firmado, TLS fijado, alta con aprobación o invitación, revocación, supervisor, módulos, base WAL |
| 3c Infraestructura investigada | Implementada | Outbox/inbox, telemetría y políticas, cupos, renovación, `sidp respaldo`, exportación SQL |
| 3d Conectividad | Implementada | Tareas dirigidas, `sidp prueba-conexion`, `sidp cortafuegos`, ensayo de dos equipos en CI con el `.exe` real |
| 3e Prueba con equipos reales | En curso | Dos PCs reales en una red Wi-Fi de casa: 11/11 OK ([SESIÓN 2026-10-12](SESION_2026-10-12.md)). Falta repetirla en la red de la escuela ([guía](PRUEBA_DOS_EQUIPOS.md)) |
| 3f Recursos compartidos | Implementada | Un solo `sidp.exe` con clave de escuela (ADR-025), búsqueda por cada red, reparto de tareas entre equipos y `sidp equipos` (ADR-026); ensayo de 3 equipos en CI |
| 3g Almacenamiento repartido | Siguiente | Cada documento en dos equipos distintos; el disco de todas las PCs suma, y una PC caída no pierde datos |

## B. Producto escolar (sistema administrativo)

| Fase | Estado | Entregable |
|---|---|---|
| 4 Identidad del personal | Pendiente | Módulo `personal`: usuarios, roles escolares por ámbito, sesiones con expiración, límite de intentos y auditoría |
| 5 Interfaz y operación | Pendiente | Interfaz web desde `backend/static`: inicio de sesión, equipos, aprobaciones, tareas y salud; respaldo diario programado |
| 6 Expediente | Pendiente | Alumnos con UUID y versión, ciclo, catálogo de documentos, requisitos, recepción y faltantes ([módulo](arquitectura/modulo_expediente.md)) |
| 7 Validación documental | Pendiente | Niveles 1 a 4 en ese orden ([validación](arquitectura/validacion_documental.md)) |
| 8 Docentes | Pendiente | Decisión de certificado (ADR-020), PWA: asistencia, evaluaciones, reportes; acceso remoto |
| 9 Estadística e impresión | Pendiente | Gráficas, estudios de población, impresión por tarea dirigida |
| 10 Piloto | Pendiente | Datos de prueba en los tres equipos; medir recursos, bloqueo SQL y recuperación |

## C. Cerebro (producto aparte)

Empieza después de la fase 6, cuando existan eventos escolares que observar. Hoy solo existe el observador de eventos (`sidp cerebro --servicio`). Fases de memoria, propuestas y autonomía en su documento.

## Próximo incremento

1. Prueba en la red de la escuela con el `sidp.exe` nuevo (3e).
2. Almacenamiento repartido entre los equipos (3g), base para los documentos que subirán los padres.
3. Login del personal (fase 4) como módulo, sobre el contrato de módulos.
4. Migrar `alumnos` a UUID y versión antes de cargar datos reales.
5. Rotación de secreto y certificado, expiración de tokens y respaldo programado.

## Aceptación objetivo

- [x] Sin cerebro, el operador consulta, registra y crea tareas.
- [x] Los reinicios conservan tareas y resultados confirmados.
- [x] Dos agentes nunca comparten una reserva vigente.
- [x] Una reserva antigua no modifica una tarea reasignada.
- [x] Un token revocado deja de operar (el agente sale con código 3).
- [x] Un equipo nuevo se une abriendo el ejecutable y con la aprobación del administrador.
- [x] Un impostor sin el secreto no responde al descubrimiento ni puede enrolarse; un certificado distinto se rechaza.
- [x] Sin LAN no se afirma confirmación central.
- [x] Una tarea creada en un equipo la ejecuta otro y se confirma de vuelta (ensayo con el `.exe` en CI).
- [x] Lo mismo, entre dos computadoras reales en una red de casa (2026-10-12, 11/11 OK).
- [ ] Lo mismo, en la red de la escuela.
- [x] El trabajo se reparte entre tres o más equipos (ensayo en CI).
- [ ] Ediciones escolares concurrentes producen un conflicto visible.
- [ ] Un respaldo restaura datos y archivos del mismo punto.

Las pruebas automáticas (`pruebas/`) y el ensayo de CI cubren lo marcado. No equivalen a un ensayo de apagón físico ni a mediciones en los equipos de la escuela.

## Decisiones del piloto

Confirmar sistemas operativos, energía/UPS de la PC administrativa, LAN (difusión permitida o IP fija), periféricos y acceso externo. Propuesta a validar: copia diaria externa y recuperación en una jornada; no es una garantía medida. No prometer años sin mantenimiento.
