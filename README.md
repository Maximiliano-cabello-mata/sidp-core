# SIDP — Sistema Integral Delfino Pando

Sistema modular de gestión escolar para una primaria, pensado para **tres computadoras modestas en LAN**, sin servidor dedicado: la plataforma corre en la PC administrativa (ADR-019). El mismo programa se entrega en dos archivos (ADR-029): `SIDP-Servidor.exe` crea la plataforma en el servidor y `SIDP-Equipo.exe` une cualquier otra PC con la clave de escuela.

**Estado:** la base técnica está construida y probada; el producto escolar está diseñado pero aún sin código. Todavía no está listo para expedientes reales.

| Componente | Responsabilidad |
|---|---|
| `sidp` | Lanzador único: instalación, alta de equipos, supervisor, roles y prueba de conectividad |
| Plataforma (`backend/`) | Autoridad de datos y permisos; monolito modular sobre SQLite WAL |
| Agente (`agente/`) | Ejecuta capacidades autorizadas y guarda resultados antes de enviarlos |
| Cerebro (`cerebro/`) | Producto aparte; hoy crea planes de un paso y observa eventos |
| `comun/`, `contratos/` | Biblioteca compartida (TLS, descubrimiento, configuración) y mensajes versionados |

## Inicio rápido

```bash
python -m pip install -r requirements-dev.txt && python -m pytest -q
python -m sidp crear-instalacion --nombre "Primaria Delfino Pando"   # servidor, una vez
python -m sidp                                                       # arranca el nodo
python -m sidp identidades aprobar <equipo>-agente                   # autorizar equipos nuevos
python -m sidp prueba-conexion                                       # diagnóstico de red e ida y vuelta
```

En Windows: `SIDP-Servidor.exe` en el servidor y `SIDP-Equipo.exe` en las demás PCs, con la misma clave de escuela ([guía](docs/PRUEBA_DOS_EQUIPOS.md)). Los dos se descargan del CI (artefacto `sidp-windows`).

## Documentación

**Empezar aquí**
- [Visión y alcance](docs/VISION.md): qué es SIDP, qué hace y qué no
- [Plan y estado](docs/PLAN.md): ruta por fases
- [Propuesta de plan 2026-10-14](docs/PLAN_PROPUESTA.md): borrador, sujeto a cambios mayores
- [Prueba con dos computadoras](docs/PRUEBA_DOS_EQUIPOS.md)
- [Manual de laboratorio](docs/manual_usuario.md)

**Base técnica**
- [Arquitectura](docs/arquitectura.md): documento rector
- [Decisiones (ADR-001 a 029)](docs/arquitectura/decisiones.md): prevalecen sobre cualquier otro documento
- [Instalación y alta de equipos](docs/arquitectura/instalacion.md)
- [Contrato de módulos](docs/arquitectura/modulos.md)
- [Contratos v1](docs/arquitectura/contratos.md)
- [Comunicación y recursos](docs/arquitectura/comunicacion-y-recursos.md)
- [SQL y operaciones transaccionales](docs/arquitectura/sql-y-procedimientos.md) · [esquema generado](database/esquema_actual.sql)
- [Operación y recuperación](docs/arquitectura/operacion.md)
- [Investigación: modelos y fuentes](docs/investigacion/fundamentos-distribuidos.md)
- [Investigación: sistemas escolares en México (SEP, MIGE, SAID)](docs/investigacion/sistemas-escolares-mexico.md)
- [Evidencia y límites de validación](docs/VALIDACION_INFRAESTRUCTURA.md)

**Producto escolar (diseño)**
- [Sistema administrativo](docs/arquitectura/sistema_administrativo.md)
- [Catálogo de módulos y plataformas](docs/arquitectura/catalogo_modulos.md)
- [Base de datos integral](docs/arquitectura/base_de_datos.md) · [esquema de diseño](database/diseno_integral.sql)
- [Módulo de expediente](docs/arquitectura/modulo_expediente.md)
- [Validación documental](docs/arquitectura/validacion_documental.md)
- [Cerebro que aprende](docs/arquitectura/cerebro_aprendizaje.md)
- [Registro de la sesión de diseño 2026-10-11](docs/SESION_2026-10-11.md)

## Estado real

**Implementado:**

- **Instalación y equipos:** ejecutable único con supervisor por equipo y paquete de instalación. Los equipos se dan de alta con aprobación o invitación, y se pueden revocar.
- **Conexión:** descubrimiento UDP firmado y TLS con certificado fijado. `sidp prueba-conexion` comprueba la conexión y hace una ida y vuelta entre equipos; CI la ensaya con el `.exe`.
- **Datos:** módulos estáticos con migraciones propias en una sola base WAL, auditoría transaccional y outbox/inbox de eventos con cursor.
- **Cola de tareas:** idempotencia, tareas dirigidas, reservas renovables y límites por equipo según telemetría y política.
- **Operación:** copia SQLite en caliente bajo comando y exportación SQL.

**Diseñado, sin código:** login del personal, interfaz, expediente, validación documental en cuatro niveles, plataforma docente (PWA), estadística, impresión y cerebro que aprende.

**Pendiente técnico:** respaldo programado, rotación de secretos, actualizaciones firmadas, certificado para navegadores y celulares (ADR-020) y medición en las computadoras de la escuela. La ruta heredada de CURP responde 501 hasta que exista la validación documental (ADR-022).
