# Manual de laboratorio y desarrollo

Requiere Python 3.12 y ejecutar los comandos desde la raíz del repositorio. Usar solo datos ficticios.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Instalación completa en un solo equipo (recomendada)

Simula tres computadoras con tres carpetas `SIDP_HOME` (en PowerShell: `$env:SIDP_HOME='...'`).

```bash
# Servidor
export SIDP_HOME=/tmp/sidp/servidor
python -m sidp crear-instalacion --nombre "Escuela de prueba" --puerto 18443
python -m sidp                                  # deja corriendo plataforma + agente

# Estación (otra terminal)
export SIDP_HOME=/tmp/sidp/aula
mkdir -p $SIDP_HOME && cp /tmp/sidp/servidor/instalacion.json $SIDP_HOME/
python -m sidp unirse --equipo aula-2 --no-esperar
SIDP_HOME=/tmp/sidp/servidor python -m sidp identidades aprobar aula-2-agente
python -m sidp                                  # agente del aula

# Dirección con invitación (otra terminal)
CODIGO=$(SIDP_HOME=/tmp/sidp/servidor python -m sidp invitacion --rol cerebro | head -1 | awk '{print $NF}')
export SIDP_HOME=/tmp/sidp/direccion
mkdir -p $SIDP_HOME && cp /tmp/sidp/servidor/instalacion.json $SIDP_HOME/
python -m sidp unirse --equipo direccion --roles cerebro --invitacion $CODIGO
python -m sidp cerebro --clave diagnostico-001
```

La tarea pasa a `completada` en cualquiera de los agentes. Consultar como operador:

```bash
TOKEN=$(python -c "import json;print(json.load(open('/tmp/sidp/servidor/credenciales/admin.json'))['token'])")
curl --cacert /tmp/sidp/servidor/plataforma/tls/certificado.pem -k -H "Authorization: Bearer $TOKEN" https://127.0.0.1:18443/api/v1/tareas
```

Revocar: `SIDP_HOME=/tmp/sidp/servidor python -m sidp identidades revocar aula-2-agente`. El agente del aula sale con código 3 y su supervisor espera 60 s antes de reintentar.

## Modo laboratorio mínimo (sin instalación)

Sin paquete, la plataforma escucha en `127.0.0.1:8000` por HTTP y acepta identidades de `SIDP_IDENTIDADES`:

```bash
export SIDP_IDENTIDADES='{"operador":{"rol":"admin","token":"REEMPLAZAR_ADMIN"},"cerebro":{"rol":"cerebro","token":"REEMPLAZAR_CEREBRO"},"pc-01":{"rol":"agente","token":"REEMPLAZAR_AGENTE"}}'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
SIDP_TOKEN=REEMPLAZAR_AGENTE python -m agente
SIDP_TOKEN=REEMPLAZAR_CEREBRO python -m cerebro --clave diagnostico-001
```

Generar tokens con `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Sin ninguna identidad configurada, el acceso queda cerrado (503).

## Compilar el ejecutable

```bash
python -m pip install -r requirements-build.txt
python despliegue/compilar.py                                   # genérico
python despliegue/compilar.py --paquete /tmp/sidp/servidor/instalacion.json   # preconfigurado
```


## Base de comunicaciones ampliada

Ver [comunicación y recursos](arquitectura/comunicacion-y-recursos.md). El perfil coordinador ahora arranca `cerebro --servicio` para observar sus eventos. Crear una tarea con `sidp cerebro --clave prueba-001` sigue siendo una orden separada. Una CPU/RAM/disco insuficiente retrasa tareas nuevas; un nodo pausado aún entrega pendientes.

En servidor: `sidp respaldo --destino RUTA_NUEVA.db`. Es copia de base, no de secretos ni documentos externos. Consultar operación para restauración y cursores.
