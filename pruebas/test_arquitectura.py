import ast
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.base_datos import BaseDatos
from backend.modulos import Modulo, ordenar
from backend.modulos.orquestacion.almacen import MIGRACIONES, Almacen, Conflicto
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


def importaciones(carpeta):
    for archivo in Path(carpeta).rglob('*.py'):
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding='utf-8'))):
            if isinstance(nodo, ast.Import):
                yield from (a.name.split('.')[0] for a in nodo.names)
            if isinstance(nodo, ast.ImportFrom) and nodo.level == 0:
                yield (nodo.module or '').split('.')[0]


@pytest.mark.parametrize('carpeta,prohibidas', [
    ('backend', {'cerebro', 'agente', 'sidp'}),
    ('cerebro', {'backend', 'agente', 'sidp'}),
    ('agente', {'backend', 'cerebro', 'sidp'}),
    ('comun', {'backend', 'cerebro', 'agente', 'sidp', 'fastapi'}),
    ('contratos', {'backend', 'cerebro', 'agente', 'sidp', 'comun'}),
])
def test_fronteras_de_importacion(carpeta, prohibidas):
    assert not set(importaciones(carpeta)) & prohibidas


def test_migraciones_por_modulo(tmp_path):
    ruta = tmp_path / 'b.db'
    BaseDatos(ruta, [Modulo('demo', '1', 'x', ('CREATE TABLE a(x);', 'CREATE TABLE b(x);'))])
    bd = BaseDatos(ruta)
    assert bd.version('demo') == 2
    with pytest.raises(RuntimeError, match='más nueva'):
        bd.migrar('demo', ('CREATE TABLE a(x);',))
    with pytest.raises(RuntimeError, match='requiere'):
        ordenar([Modulo('b', '1', 'x', depende=('a',))])


def test_adopta_cola_de_laboratorio(tmp_path):
    ruta = tmp_path / 'orquestacion.db'
    with sqlite3.connect(ruta) as db:
        db.executescript("CREATE TABLE dispositivos(id TEXT PRIMARY KEY, capacidades TEXT NOT NULL, ultimo REAL NOT NULL);"
                         "CREATE TABLE tareas(id TEXT PRIMARY KEY, actor TEXT NOT NULL, clave TEXT NOT NULL, "
                         "operacion TEXT NOT NULL, mensaje TEXT NOT NULL, estado TEXT NOT NULL, dispositivo TEXT, "
                         "reserva TEXT, vence REAL, intentos INTEGER NOT NULL DEFAULT 0, resultado TEXT, "
                         "creada REAL NOT NULL, UNIQUE(actor, clave));"
                         "CREATE TABLE eventos(secuencia INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, tarea TEXT, "
                         "actor TEXT, fecha REAL); PRAGMA user_version=1;")
    assert Almacen(ruta).bd.version("orquestacion") == len(MIGRACIONES)


def test_api_sin_cerebro_y_agente_persistente(tmp_path, monkeypatch):
    monkeypatch.setenv('SIDP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('SIDP_IDENTIDADES', json.dumps({
        'operador': {'rol': 'admin', 'token': 'test-admin'},
        'nodo': {'rol': 'agente', 'token': 'test-agente'},
        'cerebro': {'rol': 'cerebro', 'token': 'test-cerebro'}
    }))
    from backend.main import app
    from agente.__main__ import ciclo
    with TestClient(app) as cliente:
        assert cliente.get('/api/salud').status_code == 401
        assert cliente.get('/api/v1/sistema/latido').json()['sidp'] is True
        cliente.headers['Authorization'] = 'Bearer test-admin'
        assert cliente.get('/api/salud').json()['modo_supervivencia'] in ('verde', 'amarillo')
        assert cliente.get('/api/v1/sistema').json()['modo'] == 'laboratorio'
        alumno = cliente.post('/api/alumnos', json={'nombre': 'Prueba', 'apellido_paterno': 'Local', 'curp': 'X1'})
        assert alumno.status_code == 200
        assert cliente.post('/api/alumnos', json={'nombre': 'Otro', 'apellido_paterno': 'L', 'curp': 'X1'}).status_code == 400
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
            assert ciclo(cliente, db) is True
            assert db.execute('SELECT COUNT(*) FROM pendientes').fetchone()[0] == 1
        # Simula reinicio del proceso tras ejecutar y antes de enviar resultado.
        with sqlite3.connect(ruta) as db:
            ciclo(cliente, db)
            ciclo(cliente, db)
        cliente.headers['Authorization'] = 'Bearer test-admin'
        assert all(t['estado'] == 'completada' for t in cliente.get('/api/v1/tareas').json())
        with sqlite3.connect(tmp_path / 'plataforma.db') as db:
            assert db.execute("SELECT COUNT(*) FROM auditoria WHERE accion='alumno.registrado'").fetchone()[0] == 1
        monkeypatch.setenv('SIDP_IDENTIDADES', '{}')
        assert cliente.get('/api/v1/tareas').status_code == 503

