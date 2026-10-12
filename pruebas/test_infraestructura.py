import json
import sqlite3
import ssl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.base_datos import BaseDatos
from backend.main import crear_app
from backend.modulos.orquestacion.almacen import Almacen, Conflicto, Saturada
from backend.modulos.mensajeria import leer, publicar
from backend.respaldos import crear as respaldar
from cerebro.observador import Observador
from comun.politicas import Cola, Transporte, espera_reintento
from comun import red
from contratos.v1 import NuevaTarea, Resultado
from contratos.infraestructura import CambiarPolitica, PoliticaNodo, Telemetria


def muestra(cpu=1, ram=1024, disco=1024):
    return Telemetria(cpu_porcentaje=cpu, memoria_disponible_mb=ram, disco_libre_mb=disco)


@pytest.fixture
def cola(tmp_path):
    return Almacen(tmp_path / 'cola.db', Cola(pendientes_maximos=2, ejecuciones_maximas=1))


def test_limites_y_reintento_idempotente(cola):
    uno = cola.crear('operador', NuevaTarea(clave='1'))
    cola.crear('operador', NuevaTarea(clave='2'))
    assert cola.crear('operador', NuevaTarea(clave='1'))['id'] == uno['id']
    with pytest.raises(Saturada):
        cola.crear('operador', NuevaTarea(clave='3'))
    for nodo in ('a', 'b'):
        cola.registrar(nodo, ['diagnostico.echo'])
    assert cola.reclamar('a')
    assert cola.reclamar('b') is None


@pytest.mark.parametrize('telemetria', [muestra(cpu=99), muestra(ram=1), muestra(disco=1)])
def test_recursos_y_caducidad(cola, telemetria):
    cola.registrar('a', ['diagnostico.echo'], recursos=True)
    cola.crear('operador', NuevaTarea(clave='1'))
    assert cola.reclamar('a') is None  # Sin muestra no asignar.
    cola.latido('a', telemetria)
    assert cola.reclamar('a') is None
    cola.latido('a', muestra())
    with cola.conexion() as db:
        db.execute('UPDATE telemetria SET recibida=0')
    assert cola.reclamar('a') is None
    cola.latido('a', muestra())
    assert cola.reclamar('a')


def test_configuracion_optimista_y_pausa(cola):
    cola.registrar('a', ['diagnostico.echo'])
    cola.crear('operador', NuevaTarea(clave='1'))
    cambio = CambiarPolitica(revision_esperada=0, politica=PoliticaNodo(pausado=True))
    with ThreadPoolExecutor(2) as pool:
        futuros = [pool.submit(cola.cambiar_politica, 'operador', 'a', cambio) for _ in range(2)]
    assert sum(f.exception() is None for f in futuros) == 1
    assert sum(isinstance(f.exception(), Conflicto) for f in futuros) == 1
    assert cola.reclamar('a') is None


def test_renovacion_con_propietario_y_limite(cola, monkeypatch):
    import backend.modulos.orquestacion.almacen as modulo
    reloj = [1000.0]
    monkeypatch.setattr(modulo.time, 'time', lambda: reloj[0])
    cola.registrar('a', ['diagnostico.echo'])
    cola.crear('operador', NuevaTarea(clave='1'))
    tarea = cola.reclamar('a')
    with pytest.raises(Conflicto):
        cola.renovar('otro', tarea['id'], tarea['reserva'])
    for ahora in range(1050, 1600, 50):
        reloj[0] = ahora
        assert cola.renovar('a', tarea['id'], tarea['reserva'])['vence'] <= 1600
    reloj[0] = 1601
    with pytest.raises(Conflicto):
        cola.renovar('a', tarea['id'], tarea['reserva'])


def test_outbox_atomico_y_consumidor_reiniciable(cola, tmp_path):
    with pytest.raises(RuntimeError):
        with cola.bd.transaccion() as db:
            publicar(db, 'ejemplo', 'x', 'cerebro', {})
            raise RuntimeError('caída antes de commit')
    actor = {'id': 'cerebro', 'rol': 'cerebro'}
    assert leer(cola.bd, actor)['eventos'] == []
    cola.crear('cerebro', NuevaTarea(clave='1'))
    cola.crear('ajeno', NuevaTarea(clave='2'))
    lote = leer(cola.bd, actor)
    assert len(lote['eventos']) == 1
    observador = Observador(tmp_path / 'inbox.db', 'instalacion-identidad')
    observador.incorporar(lote)
    observador = Observador(tmp_path / 'inbox.db', 'instalacion-identidad')
    observador.incorporar(lote)
    assert observador.cursor() == lote['siguiente']
    with sqlite3.connect(observador.ruta) as db:
        assert db.execute('SELECT COUNT(*) FROM recibidos').fetchone()[0] == 1
    assert leer(cola.bd, actor, observador.cursor())['eventos'] == []
    with pytest.raises(ValueError):
        observador.incorporar({'version': 1, 'eventos': [], 'siguiente': 999})


def test_migracion_concurrente_y_rollback(tmp_path):
    bd = BaseDatos(tmp_path / 'db.db')
    migraciones = ('CREATE TABLE demo(id INTEGER PRIMARY KEY);',)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda _: bd.migrar('demo', migraciones), range(2)))
    assert bd.version('demo') == 1
    with pytest.raises(sqlite3.OperationalError):
        bd.migrar('demo', (*migraciones, 'CREATE TABLE temporal(x); INSERT INTO inexistente VALUES(1);'))
    assert bd.version('demo') == 1
    with bd.conexion() as db:
        assert db.execute("SELECT 1 FROM sqlite_master WHERE name='temporal'").fetchone() is None


def test_respaldo_restaura_cola_y_esquema(cola, tmp_path):
    tarea = cola.crear('operador', NuevaTarea(clave='1'))
    destino = tmp_path / 'respaldo.db'
    manifiesto = respaldar(cola.bd, destino)
    restaurada = Almacen(destino)
    assert restaurada.crear('operador', NuevaTarea(clave='1'))['id'] == tarea['id']
    assert manifiesto['esquemas']['orquestacion'] == 3
    assert destino.with_suffix('.db.json').exists()
    with pytest.raises(ValueError):
        respaldar(cola.bd, destino)


def test_tls_sin_raices_del_sistema_y_sin_downgrade(tmp_path):
    from sidp.certificados import generar
    from comun.configuracion import Paquete
    pem = generar(tmp_path / 'tls', 'prueba')
    contexto = red.contexto_tls(pem)
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.get_ca_certs(binary_form=True) == [ssl.PEM_cert_to_DER_cert(pem)]
    with pytest.raises(ValueError, match='HTTP'):
        red.cliente('http://127.0.0.1', paquete=Paquete('1', 'x', 's', certificado=pem))


def test_supervisor_cerebro_y_jitter():
    from sidp.supervisor import comando
    assert comando('cerebro')[-2:] == ['cerebro', '--servicio']
    politica = Transporte()
    for fallos in (0, 1, 10000):
        assert 1 <= espera_reintento(fallos, politica) <= 30


def test_sql_exportado_se_puede_instalar(tmp_path):
    from herramientas.exportar_esquema import generar
    sql = generar()
    with sqlite3.connect(tmp_path / 'nuevo.db') as db:
        db.executescript(sql)
        assert db.execute("SELECT version FROM esquema WHERE modulo='orquestacion'").fetchone()[0] == 3
        assert db.execute('SELECT * FROM resumen_cola').fetchall() == []


def test_api_infraestructura_y_autorizacion(monkeypatch):
    monkeypatch.setenv('SIDP_IDENTIDADES', json.dumps({
        'admin': {'rol': 'admin', 'token': 'admin'}, 'c': {'rol': 'cerebro', 'token': 'c'},
        'a': {'rol': 'agente', 'token': 'a'}}))
    monkeypatch.setenv('SIDP_COLA', '{"pendientes_maximos":1}')
    with TestClient(crear_app()) as cliente:
        cliente.headers['Authorization'] = 'Bearer c'
        assert cliente.post('/api/v1/tareas', json={'clave': '1'}).status_code == 200
        assert cliente.post('/api/v1/tareas', json={'clave': '2'}).status_code == 429
        assert len(cliente.get('/api/v1/eventos').json()['eventos']) == 1
        cliente.headers['Authorization'] = 'Bearer a'
        assert cliente.get('/api/v1/eventos').status_code == 403
        cliente.post('/api/v1/dispositivos/registro', json={'capacidades': ['diagnostico.echo'], 'protocolo_recursos': True})
        assert cliente.post('/api/v1/tareas/reclamar').json() is None
        assert cliente.post('/api/v1/dispositivos/latido', json=muestra().model_dump()).status_code == 200
        tarea = cliente.post('/api/v1/tareas/reclamar').json()
        assert tarea['estado'] == 'ejecutando'
        assert cliente.post(f"/api/v1/tareas/{tarea['id']}/renovar", json={'reserva': tarea['reserva']}).status_code == 200
        cambio = {'revision_esperada': 0, 'politica': {'pausado': True}}
        assert cliente.put('/api/v1/dispositivos/a/politica', json=cambio).status_code == 403
        cliente.headers['Authorization'] = 'Bearer admin'
        assert cliente.put('/api/v1/dispositivos/a/politica', json=cambio).status_code == 200
        assert cliente.put('/api/v1/dispositivos/a/politica', json=cambio).status_code == 409
        assert cliente.get('/api/v1/tareas/resumen').json()['estados'][0]['cantidad'] == 1
        assert len(cliente.get('/api/v1/dispositivos').json()) == 1
