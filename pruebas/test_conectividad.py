"""Tareas dirigidas y prueba de conectividad entre dos equipos sobre HTTPS real."""
import sqlite3
import threading
import time
import pytest
import uvicorn
from agente.__main__ import ciclo, registrar
from backend.main import crear_app, preparar
from backend.modulos.identidad import servicio
from backend.modulos.orquestacion.almacen import Almacen, Conflicto
from comun import firma, red
from contratos.v1 import NuevaTarea
from sidp import conectividad, instalacion
from pruebas.test_instalacion import puerto_libre


def test_tarea_dirigida_solo_la_toma_su_destino(tmp_path):
    cola = Almacen(tmp_path / 'cola.db')
    tarea = cola.crear('operador', NuevaTarea(clave='uno', destino='b'))
    for nodo in ('a', 'b'):
        cola.registrar(nodo, ['diagnostico.echo'])
    assert cola.reclamar('a') is None
    assert cola.reclamar('b')['id'] == tarea['id']
    with pytest.raises(Conflicto):
        cola.crear('operador', NuevaTarea(clave='uno', destino='a'))
    assert cola.consultar({'id': 'operador', 'rol': 'admin'}, tarea['id'])['destino'] == 'b'
    with pytest.raises(Conflicto):
        cola.consultar({'id': 'otro', 'rol': 'cerebro'}, tarea['id'])


@pytest.fixture
def servidor_tls(hogar_aislado):
    resultado = instalacion.crear('Escuela dos equipos', puerto=puerto_libre(), equipo='pc1')
    paquete = resultado['paquete']
    tls = hogar_aislado / 'plataforma' / 'tls'
    servidor = uvicorn.Server(uvicorn.Config(crear_app(), host='127.0.0.1', port=paquete.puerto, log_config=None,
                                             ssl_certfile=str(tls / 'certificado.pem'), ssl_keyfile=str(tls / 'clave.pem')))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.05)
    yield paquete, f'https://127.0.0.1:{paquete.puerto}'
    servidor.should_exit = True
    hilo.join(5)


def test_prueba_de_conexion_con_agente_remoto(servidor_tls, tmp_path):
    paquete, url = servidor_tls
    # "PC2": identidad propia y su propio almacén de pendientes, como en otro equipo.
    token = firma.nuevo_token()
    servicio.crear_directa(preparar(paquete=paquete).bd, 'pc2', 'agente', token)
    alto = threading.Event()

    def agente_remoto():
        with red.cliente(url, token, paquete) as cliente, sqlite3.connect(tmp_path / 'pc2.db') as db:
            registrar(cliente)
            while not alto.is_set():
                ciclo(cliente, db)
                time.sleep(0.2)

    hilo = threading.Thread(target=agente_remoto, daemon=True)
    hilo.start()
    try:
        time.sleep(0.5)
        lineas = []
        informe = conectividad.ejecutar(url=url, espera=20, aviso=lineas.append)
        estados = {p['prueba']: p['estado'] for p in informe.pruebas}
        assert informe.pasa, lineas
        assert estados['HTTPS con certificado fijado'] == 'ok'
        assert estados['Credencial admin'] == 'ok'
        assert estados['Ida y vuelta pc2-agente'] == 'ok'
        fantasma = conectividad.ejecutar(url=url, equipos=['fantasma-agente'], espera=2, aviso=lambda _: None)
        assert not fantasma.pasa
        assert fantasma.cerrar() == 1
    finally:
        alto.set()
        hilo.join(5)


def test_prueba_de_conexion_sin_servidor(hogar_aislado):
    instalacion.crear('Escuela apagada', puerto=puerto_libre(), equipo='pc1')
    informe = conectividad.ejecutar(aviso=lambda _: None)
    assert not informe.pasa
    assert informe.pruebas[-1]['prueba'] == 'Puerto TCP'
