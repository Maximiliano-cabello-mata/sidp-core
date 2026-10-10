# Laboratorio de arquitectura

Python 3.12, ejecutar desde raíz, con datos ficticios. Instalar requirements-dev.txt. En Windows activar entorno con .venv/Scripts/Activate.ps1; en Linux source .venv/bin/activate.

## Identidades y plataforma

Generar tres tokens distintos con `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Guardarlos fuera de Git. Reemplazar marcadores en:

```bash
export SIDP_IDENTIDADES='{"operador":{"rol":"admin","token":"REEMPLAZAR_ADMIN"},"cerebro":{"rol":"cerebro","token":"REEMPLAZAR_CEREBRO"},"pc-01":{"rol":"agente","token":"REEMPLAZAR_AGENTE"}}'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

PowerShell: `$env:SIDP_IDENTIDADES='...'`. Sin configuración, acceso denegado. No existe login gráfico todavía.

Base escolar heredada en backend/sidp_nodo_local.db. Cola en datos/orquestacion.db. SIDP_DATA_DIR cambia ubicación de ambas pero no copia datos automáticamente; consultar operación antes de cambiarlo.

## Agente, otra terminal

```bash
export SIDP_TOKEN='TOKEN_DEL_AGENTE'
export SIDP_URL='http://127.0.0.1:8000'
python -m agente
```

PowerShell: `$env:SIDP_TOKEN='TOKEN_DEL_AGENTE'`. SIDP_AGENTE_DIR fija directorio de pendientes.db. No compartir identidad/directorio; mantener SIDP_URL para no enviar pendientes a otra instalación.

## Cerebro, otra terminal

```bash
export SIDP_TOKEN='TOKEN_DEL_CEREBRO'
python -m cerebro --clave diagnostico-001
```

Termina al crear el plan técnico de un paso; no es supervisor permanente. Repetir clave no duplica. Una clave diferente representa nuevo diagnóstico.

## Trabajo sin cerebro

No arrancar cerebro. Con el agente conectado:

```bash
curl -H "Authorization: Bearer TOKEN_ADMIN" -H "Content-Type: application/json" -d '{"clave":"manual-001"}' http://127.0.0.1:8000/api/v1/tareas
curl -H "Authorization: Bearer TOKEN_ADMIN" http://127.0.0.1:8000/api/v1/tareas
```

Debe llegar a completada. Si cae agente tras reservar, vence en 60 segundos y siguiente reclamo recupera. Tres intentos vencidos: fallida. No hay reinicio de tarea fallida; diagnosticar y crear nueva clave.

## Pruebas

`python -m pytest -q`. Datos y directorios temporales. Detener con Ctrl+C; pendientes ya guardados permanecen.
