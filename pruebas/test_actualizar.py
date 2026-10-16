"""SIDP se actualiza solo desde la PC 4, sin depender del repositorio, y regresa a la anterior si la nueva no arranca."""
import json
import os
import types
import urllib.error
import urllib.request

import pytest

from pruebas.test_entorno_pruebas import iniciar
from validacion import actualizar, aplicacion, cerebro_red, escritorio

VIEJO = b'MZ' + b'version vieja ' * 100
NUEVO = b'MZ' + b'version nueva ' * 100


def test_la_pc_4_guarda_cada_version_sin_sobrescribir(tmp_path):
    assert actualizar.disponible(tmp_path) is None
    with pytest.raises(actualizar.ErrorActualizacion):
        actualizar.publicar(tmp_path, NUEVO, 'nueva')
    with pytest.raises(actualizar.ErrorActualizacion):
        actualizar.publicar(tmp_path, b'no es un programa' * 100, '1.0.5')
    assert actualizar.publicar(tmp_path, VIEJO, '1.0.5')['version'] == '1.0.5'
    assert actualizar.publicar(tmp_path, NUEVO, '1.0.4')['version'] == '1.0.5'  # Una menor no reemplaza a la que hay.
    datos = actualizar.publicar(tmp_path, NUEVO, '1.0.10')
    assert datos['version'] == '1.0.10' and datos['sha256'] == actualizar.huella(NUEVO) and datos['tamano'] == len(NUEVO)
    assert sorted(p.name for p in tmp_path.glob('*.exe')) == ['SIDP-1.0.10.exe', 'SIDP-1.0.5.exe']
    # Para regresar a una anterior hay que pedirlo; un archivo distinto con la misma versión nunca se sobrescribe.
    assert actualizar.publicar(tmp_path, VIEJO, '1.0.5', forzar=True)['version'] == '1.0.5'
    with pytest.raises(actualizar.ErrorActualizacion):
        actualizar.publicar(tmp_path, NUEVO, '1.0.5', forzar=True)
    assert actualizar.mayor('1.0.10', '1.0.9') and not actualizar.mayor('1.0.9', '1.0.10') and not actualizar.mayor(None, '1.0.0')


def test_la_pc_4_baja_la_version_publicada_en_github_y_revisa_su_huella(tmp_path, monkeypatch):
    lanzamiento = {'tag_name': 'v1.0.7', 'assets': [{'name': 'SIDP-Instalador.exe', 'browser_download_url': 'https://x/instalador'},
                                                    {'name': 'SIDP.exe', 'browser_download_url': 'https://x/sidp',
                                                     'digest': 'sha256:' + actualizar.huella(NUEVO)}]}
    pedidos = []

    def bajar(url, espera, cabeceras=None):
        pedidos.append(url)
        return json.dumps(lanzamiento).encode() if 'api.github.com' in url else NUEVO

    monkeypatch.setattr(actualizar, '_bajar', bajar)
    assert actualizar.de_github(tmp_path) == '1.0.7'
    assert actualizar.disponible(tmp_path)['origen'] == 'GitHub v1.0.7'
    assert actualizar.de_github(tmp_path) is None and pedidos[-1].startswith('https://api.github.com')  # Ya la tiene.
    lanzamiento['tag_name'] = 'v1.0.8'
    lanzamiento['assets'][1]['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(actualizar.ErrorActualizacion):
        actualizar.de_github(tmp_path)
    assert actualizar.disponible(tmp_path)['version'] == '1.0.7'


@pytest.fixture
def cerebro(tmp_path):
    carpeta = tmp_path / 'actualizaciones'
    servidor = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1',
                                          actualizaciones=carpeta)
    url = iniciar(servidor)
    yield url, carpeta
    servidor.shutdown()


def test_el_cerebro_entrega_la_version_solo_con_la_clave(cerebro):
    url, carpeta = cerebro
    assert cerebro_red.pedir_a_cerebro(url, 'clave-de-prueba', '/actualizacion') == {'version': None}
    actualizar.publicar(carpeta, NUEVO, '1.0.7')
    assert cerebro_red.pedir_a_cerebro(url, 'clave-de-prueba', '/actualizacion')['version'] == '1.0.7'
    assert cerebro_red.bajar_de_cerebro(url, 'clave-de-prueba', '/actualizacion/programa') == NUEVO
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(url + '/actualizacion/programa')
    assert error.value.code == 401


def preparar_servidor(tmp_path, cerebro):
    url, carpeta = cerebro
    instalado = tmp_path / 'Program Files' / 'SIDP'
    instalado.mkdir(parents=True)
    (instalado / 'SIDP.exe').write_bytes(VIEJO)
    app = types.SimpleNamespace(carpeta=tmp_path / 'SIDP' / 'sistema', puerto=8770, ultimo_cambio=0)
    app.carpeta.mkdir(parents=True)
    arrancados = []
    actualizador = actualizar.Actualizador(app, instalado / 'SIDP.exe', '1.0.5', iniciar=lambda p, a: arrancados.append((p.read_bytes(), a)) or
                                           types.SimpleNamespace(pid=0, kill=lambda: None), contesta=lambda v, e, p: True)
    actualizar.publicar(carpeta, NUEVO, '1.0.7')
    return url, instalado, app, actualizador, arrancados


def test_el_servidor_toma_la_version_nueva_cuando_nadie_lo_usa(tmp_path, cerebro):
    url, instalado, app, actualizador, arrancados = preparar_servidor(tmp_path, cerebro)
    assert actualizador.revisar(url, 'clave-equivocada')['problema']
    actualizador.ultima_revision = 0
    estado = actualizador.revisar(url, 'clave-de-prueba')
    assert estado['lista'] == '1.0.7' and (instalado / 'SIDP.nuevo.exe').read_bytes() == NUEVO
    app.ultimo_cambio = 10_000
    assert not actualizador.quieto_ahora(ahora=10_100)  # Alguien acaba de guardar algo: se espera.
    apagado = []
    assert actualizador.aplicar(lambda: apagado.append(True)) == 'puesta'
    assert apagado and (instalado / 'SIDP.exe').read_bytes() == NUEVO and (instalado / 'SIDP.anterior.exe').read_bytes() == VIEJO
    assert arrancados == [(NUEVO, ['--segundo-plano', '--carpeta', str(tmp_path / 'SIDP'), '--puerto', '8770'])]
    assert json.loads((app.carpeta / 'actualizacion.json').read_text())['puesta'] == '1.0.7'


def test_si_la_version_nueva_no_arranca_regresa_sola_a_la_anterior(tmp_path, cerebro):
    url, instalado, app, actualizador, arrancados = preparar_servidor(tmp_path, cerebro)
    actualizador.contesta = lambda v, e, p: False
    actualizador.revisar(url, 'clave-de-prueba')
    assert actualizador.aplicar(lambda: None) == 'regresada'
    assert (instalado / 'SIDP.exe').read_bytes() == VIEJO and (instalado / 'SIDP.fallido.exe').read_bytes() == NUEVO
    assert [contenido for contenido, _ in arrancados] == [NUEVO, VIEJO]
    # Esa versión ya no se reintenta, ni después de reiniciar.
    otra_vez = actualizar.Actualizador(app, instalado / 'SIDP.exe', '1.0.5')
    assert otra_vez.revisar(url, 'clave-de-prueba')['lista'] is None and otra_vez.estado['fallida'] == '1.0.7'
    assert not (instalado / 'SIDP.nuevo.exe').exists()


def test_el_vigia_pone_la_version_y_termina_el_proceso_viejo(tmp_path, cerebro, monkeypatch):
    url, instalado, _, actualizador, arrancados = preparar_servidor(tmp_path, cerebro)
    app = aplicacion.Aplicacion(tmp_path / 'SIDP' / 'sistema', puerto=0, expedientes=tmp_path / 'SIDP' / 'Expedientes', conectar_al_abrir=False)
    app.ultimo_cambio = 0
    app.servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    app.puerto = app.servidor.server_port
    iniciar(app.servidor)
    actualizador.app = app
    app.actualizador = actualizador
    salidas = []
    monkeypatch.setattr(os, '_exit', salidas.append)
    escritorio.Vigia(app).actualizar(url, 'clave-de-prueba')
    assert salidas == [0] and (instalado / 'SIDP.exe').read_bytes() == NUEVO
    with pytest.raises(OSError):  # El servidor viejo ya soltó el puerto para el nuevo.
        urllib.request.urlopen(f'http://127.0.0.1:{app.puerto}/api/hola', timeout=2)
    assert app.estado_configuracion()['actualizacion']['lista'] == '1.0.7'
