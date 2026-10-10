# SIDP — Sistema Integral Delfino Pando

Base arquitectónica: plataforma independiente, cerebro coordinador y agentes en dispositivos. Etapa de laboratorio, todavía no lista para expedientes reales.

| Componente | Entrada desde la raíz | Responsabilidad |
|---|---|---|
| Plataforma | `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` | Datos escolares y cola de tareas |
| Cerebro | `python -m cerebro --clave diagnostico-001` | Plan técnico de un paso por API |
| Agente | `python -m agente` | Ejecutar echo y persistir resultados pendientes |
| Contratos | `contratos/v1.py` | Entradas v1 y capacidades autorizadas |

## Inicio

Python 3.12. Crear entorno virtual, activarlo e instalar `python -m pip install -r requirements-dev.txt`. Verificar con `python -m pytest -q`. La plataforma necesita SIDP_IDENTIDADES; sin configuración rechaza acceso. [Guía completa](docs/manual_usuario.md).

## Documentación

- [Arquitectura](docs/arquitectura.md)
- [Contratos](docs/arquitectura/contratos.md)
- [Decisiones](docs/arquitectura/decisiones.md)
- [Plan y aceptación](docs/PLAN.md)
- [Operación y recuperación](docs/arquitectura/operacion.md)

## Estado real

Implementados: procesos separados, identidades técnicas, capacidades, cola SQLite transaccional, idempotencia, reservas de 60 segundos, tres intentos máximos, eventos locales y resultados persistentes del agente. API escolar heredada disponible para admin.

Pendientes: login de personal, interfaz, PostgreSQL, sincronización escolar, planes multietapa, actualizaciones firmadas, periféricos, copias automáticas y alta disponibilidad. No hay IA ni autoprogramación. Validaciones documentales fuera de alcance: la ruta heredada responde 501 y no presenta la simulación RENAPO como consulta real.
