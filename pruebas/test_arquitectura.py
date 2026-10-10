import ast
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.tareas import Almacen, Conflicto
from contratos.v1 import NuevaTarea, Resultado


@pytest.fixture
def almacen(tmp_path):
    return Almacen(tmp_path / 'cola.db')


def test_persistencia_e_idempotencia(almacen):
    tarea = almacen.crear('admin', NuevaTarea(clave='uno'))
    reiniciado = Almacen(almacen.ruta)
    assert reiniciado.crear('admin', NuevaTarea(clave='uno'))['id'] == tarea['id']
    with pytest.raises(Conflicto):
        reiniciado.crear('admin', NuevaTarea(clave='uno', mensaje='otro'))


def test_reserva_exclusiva_concurrente(almacen):
    almacen.crear('admin', NuevaTarea(clave='uno'))
    for nombre in ['a', 'b']:
        almacen.registrar(nombre, ['diagnostico.echo'])
    with ThreadPoolExecutor(2) as pool:
        resultados = list(pool.map(almacen.reclamar, ['a', 'b']))
    assert sum(r is not None for r in resultados) == 1


def test_reserva_vencida_y_resultado_duplicado(almacen):
    almacen.crear('admin', NuevaTarea(clave='uno'))
    almacen.registrar('a', ['diagnostico.echo'])
    viejo = almacen.reclamar('a')
    with almacen.conexion() as db:
        db.execute('UPDATE tareas SET vence=0')
    nuevo = almacen.reclamar('a')
    with pytest.raises(Conflicto):
        almacen.completar('a', viejo['id'], Resultado(reserva=viejo['reserva'], mensaje=viejo['mensaje']))
    resultado = Resultado(reserva=nuevo['reserva'], mensaje=nuevo['mensaje'])
    assert almacen.completar('a', nuevo['id'], resultado)['estado'] == 'completada'
    assert almacen.completar('a', nuevo['id'], resultado)['estado'] == 'completada'
    with almacen.conexion() as db:
        assert db.execute("SELECT COUNT(*) FROM eventos WHERE tipo='tarea.completada'").fetchone()[0] == 1


def test_limite_de_reintentos(almacen):
    almacen.crear('admin', NuevaTarea(clave='uno'))
    almacen.registrar('a', ['diagnostico.echo'])
    for _ in range(3):
        assert almacen.reclamar('a')
        with almacen.conexion() as db:
            db.execute('UPDATE tareas SET vence=0')
    assert almacen.reclamar('a') is None
    assert almacen.listar({'id': 'admin', 'rol': 'admin'})[0]['estado'] == 'fallida'


def test_fronteras_de_importacion():
    for carpeta, prohibidas in [('backend', {'cerebro', 'agente'}), ('cerebro', {'backend', 'agente'}), ('agente', {'backend', 'cerebro'})]:
        for archivo in Path(carpeta).rglob('*.py'):
            for nodo in ast.walk(ast.parse(archivo.read_text())):
                if isinstance(nodo, ast.Import):
                    assert not {a.name.split('.')[0] for a in nodo.names} & prohibidas
                if isinstance(nodo, ast.ImportFrom):
                    assert (nodo.module or '').split('.')[0] not in prohibidas


def test_api_sin_cerebro_y_agente_persistente(tmp_path, monkeypatch):
    monkeypatch.setenv('SIDP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('SIDP_IDENTIDADES', json.dumps({
        'operador': {'rol': 'admin', 'token': 'test-admin'},
        'nodo': {'rol': 'agente', 'token': 'test-agente'},
        'cerebro': {'rol': 'cerebro', 'token': 'test-cerebro'}
    }))
    from backend.main import app
    from backend.api.orquestacion import almacen as proveedor
    from agente.__main__ import ciclo
    proveedor.cache_clear()
    with TestClient(app) as cliente:
        assert cliente.get('/api/salud').status_code == 401
        cliente.headers['Authorization'] = 'Bearer test-admin'
        assert cliente.get('/api/salud').status_code == 200
        alumno = cliente.post('/api/alumnos', json={'nombre': 'Prueba', 'apellido_paterno': 'Local'})
        assert alumno.status_code == 200
        assert cliente.get('/api/alumnos').json()[0]['nombre'] == 'Prueba'
        assert cliente.get('/api/validar-curp/PRUEBA').status_code == 501
        assert cliente.post('/api/v1/tareas', json={'clave': 'manual'}).status_code == 200
        assert cliente.post('/api/v1/tareas', json={'clave': 'no', 'operacion': 'shell'}).status_code == 422
        cliente.headers['Authorization'] = 'Bearer test-cerebro'
        assert cliente.get('/api/alumnos').status_code == 403
        assert cliente.post('/api/v1/tareas', json={'clave': 'plan'}).status_code == 200
        cliente.headers['Authorization'] = 'Bearer test-agente'
        assert cliente.post('/api/v1/tareas', json={'clave': 'ilegal'}).status_code == 403
        ruta = tmp_path / 'agente.db'
        with sqlite3.connect(ruta) as db:
            db.execute('CREATE TABLE pendientes(id TEXT PRIMARY KEY,reserva TEXT,mensaje TEXT)')
            ciclo(cliente, db)
            assert db.execute('SELECT COUNT(*) FROM pendientes').fetchone()[0] == 1
        # Simula reinicio del proceso tras ejecutar y antes de enviar resultado.
        with sqlite3.connect(ruta) as db:
            ciclo(cliente, db)
            ciclo(cliente, db)
        cliente.headers['Authorization'] = 'Bearer test-admin'
        assert all(t['estado'] == 'completada' for t in cliente.get('/api/v1/tareas').json())
        monkeypatch.setenv('SIDP_IDENTIDADES', '{}')
        assert cliente.get('/api/v1/tareas').status_code == 503
    proveedor.cache_clear()
