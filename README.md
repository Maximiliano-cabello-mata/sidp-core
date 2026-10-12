# SIDP — Sistema Integral Delfino Pando

Sistema modular de gestión escolar para una primaria, pensado para **tres computadoras modestas en LAN**. Un solo ejecutable (`sidp.exe`) contiene todos los roles. En un equipo nuevo basta con abrirlo: encuentra la plataforma, pide autorización y arranca. Etapa de laboratorio: todavía no está listo para expedientes reales.

| Componente | Responsabilidad |
|---|---|
| `sidp` | Lanzador único: instalación, alta de equipos, supervisor y roles |
| Plataforma (`backend/`) | Autoridad de datos y permisos; monolito modular sobre SQLite WAL |
| Agente (`agente/`) | Ejecuta capacidades autorizadas y guarda resultados antes de enviarlos |
| Cerebro (`cerebro/`) | Coordinador; planes técnicos de un paso y observador durable de eventos |
| `comun/`, `contratos/` | Biblioteca compartida (TLS, descubrimiento, configuración) y mensajes versionados |

## Inicio rápido

```bash
python -m pip install -r requirements-dev.txt && python -m pytest -q
python -m sidp crear-instalacion --nombre "Primaria Delfino Pando"   # servidor, una vez
python -m sidp                                                       # arranca el nodo
python -m sidp identidades aprobar <equipo>-agente                   # autorizar equipos nuevos
```

Equipos adicionales: abrir `sidp.exe` con el paquete de la escuela (incrustado con `despliegue/compilar.py --paquete` o `instalacion.json` al lado del ejecutable).

## Documentación

- [Investigación: modelos, teorías y fuentes primarias](docs/investigacion/fundamentos-distribuidos.md)
- [Comunicación y recursos](docs/arquitectura/comunicacion-y-recursos.md)
- [SQL y operaciones transaccionales](docs/arquitectura/sql-y-procedimientos.md)
- [Esquema SQL generado](database/esquema_actual.sql)


- [Arquitectura](docs/arquitectura.md): documento rector
- [Instalación y alta de equipos](docs/arquitectura/instalacion.md)
- [Contrato de módulos](docs/arquitectura/modulos.md)
- [Contratos v1](docs/arquitectura/contratos.md)
- [Decisiones (ADR)](docs/arquitectura/decisiones.md)
- [Operación y recuperación](docs/arquitectura/operacion.md)
- [Plan y aceptación](docs/PLAN.md)
- [Manual de laboratorio](docs/manual_usuario.md)

[Evidencia y límites de validación](docs/VALIDACION_INFRAESTRUCTURA.md).

## Estado real

**Implementado:**

- ejecutable único con supervisor por equipo;
- paquete de instalación;
- descubrimiento UDP firmado;
- TLS con certificado fijado;
- enrolamiento con aprobación o invitación, y revocación;
- módulos estáticos con migraciones propias en una sola base WAL;
- auditoría transaccional;
- cola durable con idempotencia, reservas de 60 s y tres intentos;
- agente con espera adaptativa y redescubrimiento;
- salud real de base y disco.

**Añadido:** outbox/inbox con cursor, política por equipo con revisión, telemetría, límites de admisión, renovación de reservas, copia SQLite en caliente bajo comando local y exportación SQL.

**Pendiente:** login del personal, interfaz, programación/retención de copias, rotación de secretos, planes multietapa, actualizaciones firmadas, periféricos y sincronización escolar sin conexión. No hay IA ni autoprogramación. Las validaciones documentales están fuera de alcance (la ruta heredada responde 501).

