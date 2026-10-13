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
| 3f2 Dos ejecutables | Implementada | `SIDP-Servidor.exe` y `SIDP-Equipo.exe` (ADR-029): el equipo nunca se vuelve servidor, el servidor se niega si ya hay otro, la clave se confirma y cada `.exe` muestra su fecha; ensayo en CI con los dos |
| 3g Copias automáticas | Siguiente | La base y cada archivo se copian a otra PC unida y cada noche a un disco externo; una PC nueva recibe su copia solo con instalar el `.exe` (ADR-027). Incluye cambio de clave de escuela y arranque con Windows sin ventana |

## B. Producto escolar

Ruta acordada el 2026-10-13. Alcance cerrado en [VISION.md](VISION.md); tablas y defensas de cada fase en [base_de_datos.md](arquitectura/base_de_datos.md). Cada fase deja algo usable y no se empieza la siguiente hasta que la anterior funciona en la escuela.

| Fase | Estado | Entregable | Lista cuando |
|---|---|---|---|
| 4 Cuentas del personal | Pendiente | Módulo `personal`: usuarios, roles (dirección, secretaría, docente, administrativo), sesiones con expiración, límite de intentos, bitácora de cambios | Cada persona entra con su usuario |
| 5 Pantallas y operación | Pendiente | Interfaz web desde `backend/static`: inicio de sesión, equipos, pantalla de salud, respaldo diario programado y su prueba de restauración | Se usa desde el navegador sin consola |
| 6 Expedientes | Pendiente | Alumno y tutor con UUID y versión, ciclos, documentos, fotos y PDF, búsqueda, faltantes, carga inicial desde Excel, exportar todo ([módulo](arquitectura/modulo_expediente.md)) | Secretaría arma el expediente de un grupo |
| 7 Docentes y dirección | Pendiente | Decisión de certificado (ADR-020), PWA: asistencia de alumnos, calificaciones, exámenes diagnósticos; asistencia de profesores e inventario | Un grupo los usa un mes |
| 8 Formatos y documentos | Pendiente | Catálogo de formatos llenados con datos de la escuela, boletas y constancias, PDF básico, escaneo a carpeta, impresión por tarea dirigida, estadística | Una constancia sale con un clic |
| 9 Piloto | Pendiente | Escuela completa con datos de prueba; cierre de ciclo; medir recursos, bloqueos y recuperación | Una semana sin perder datos ni detener el trabajo |

## C. Buzón de padres (ADR-028)

Después del piloto. Página en internet para crear cuenta, subir documentos y ver su estado; el servidor descarga lo nuevo. Requiere aviso de privacidad y confirmar quién paga el hosting.

## D. Cerebro (producto aparte, PC 4)

Empieza cuando existan expedientes reales. Hoy solo existe el observador de eventos (`sidp cerebro --servicio`). Orden: validación documental en cuatro niveles ([validación](arquitectura/validacion_documental.md)), propuesta de campos de formatos, redacción con plantillas, análisis. Fases de memoria y propuestas en [cerebro_aprendizaje.md](arquitectura/cerebro_aprendizaje.md).

## Próximo incremento

1. Prueba en la red de la escuela con `SIDP-Servidor.exe` y `SIDP-Equipo.exe` (3e). Al mismo tiempo, reunir una copia de cada formato que usan los administrativos (sin código).
2. Copias automáticas, cambio de clave y arranque con Windows (3g).
3. Cuentas del personal (fase 4).
4. Migrar `alumnos` a UUID y versión antes de cargar datos reales.

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
