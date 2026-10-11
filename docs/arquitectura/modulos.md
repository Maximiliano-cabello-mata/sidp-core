# Contrato de módulos

Un módulo es la unidad de crecimiento de SIDP. Cada función escolar futura entra como módulo de plataforma y, si necesita ejecutar algo en un equipo, como capacidad de agente.

## Módulo de plataforma

Vive en `backend/modulos/<nombre>/__init__.py` y expone `MODULO`:

```python
MODULO = Modulo(
    nombre="asistencia",          # único, minúsculas; prefijo de sus tablas si hay ambigüedad
    version="1.0",                # versión funcional, informativa
    descripcion="Pase de lista",
    migraciones=(SQL_001, SQL_002),  # tupla ordenada; nunca editar una ya publicada
    rutas=router,                 # APIRouter con sus dependencias de seguridad
    depende=("sistema", "escolar"),
    al_iniciar=iniciar,           # opcional: (app, contexto) -> None
)
```

Después se agrega a `registrados()` en `backend/modulos/__init__.py`, respetando el orden de dependencias. `ordenar()` valida que no haya nombres duplicados ni dependencias faltantes antes de arrancar.

### Reglas

1. **Datos.** Cada módulo solo escribe en sus tablas. Para leer datos de otro módulo usa su servicio o su vista pública, nunca su SQL interno.
2. **Migraciones.** Son aditivas y se aplican una sola vez cada una dentro de `BEGIN IMMEDIATE`. Para corregir, se agrega una migración nueva. Una base más nueva que el código impide arrancar.
3. **Transacciones.** Se usa `ctx.bd.transaccion()` y se escribe la auditoría (`backend.auditoria.anotar`) dentro de la misma transacción.
4. **Seguridad.** Toda ruta declara `Depends(requiere(...))` o `administrador`. Una ruta pública, como `latido` o la solicitud de ingreso, debe justificarse en un comentario.
5. **Contexto.** Se obtiene con `Depends(contexto)`. Nada de variables globales ni de leer configuración al importar.
6. **Lógica reutilizable.** Va en `servicio.py`, separada de las rutas, para que la línea de comandos y las pruebas la usen sin HTTP (ejemplo: `identidad/servicio.py`).
7. **Importaciones.** Solo `backend.*`, `comun`, `contratos` y bibliotecas declaradas en `requirements.txt`. Una dependencia nueva debe justificar su peso en el ejecutable.
8. **Pruebas.** Cada módulo nuevo agrega pruebas de migración, permisos y del caso feliz.

## Capacidad de agente

Una capacidad es una función incorporada y repetible que el agente ejecuta cuando reclama una tarea.

1. Declararla en `contratos/v1.py::Capacidad`. Es un cambio de contrato: la plataforma rechaza operaciones fuera del catálogo con 422.
2. Implementarla en `agente/capacidades.py` y registrarla en `CAPACIDADES`. Recibe la tarea y devuelve el resultado.
3. Debe ser **idempotente**: una reserva vencida provoca que se ejecute otra vez.
4. Una capacidad con efectos externos (imprimir, escribir archivos, servicios) no se habilita hasta definir su reconciliación (ADR-005).
5. Nunca debe ejecutar texto recibido como código o comando.

## Ciclo de vida de un módulo

Diseño (ADR si cambia fronteras) → contrato en `contratos/` → migraciones → servicio → rutas → pruebas → registro → documentación en `docs/arquitectura.md` (tabla de módulos).


## Publicar eventos de un nuevo módulo

Declarar dependencia de mensajeria. En la misma transacción que el cambio llamar `backend.modulos.mensajeria.publicar(db, tipo, correlacion, propietario, datos)`. No pasar expedientes completos en datos: incluir identificadores/metadatos autorizados. Un fallo revierte cambio y evento. El propietario controla visibilidad del consumidor; no se publica por HTTP arbitrario.

El canal común no hace idempotente un nuevo efecto automáticamente. Definir su clave y prueba de repetición. Los handlers largos deben usar renovación de reserva y reconciliación: echo es aún la única capacidad habilitada.
