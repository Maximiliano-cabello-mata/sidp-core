"""SIDP instalado en el servidor: carpetas de expedientes por alumno, encontrar sola a la PC 4 y apagar. Todo inventado."""
import io
import ipaddress
import json
import urllib.request

import pytest

from pruebas.test_entorno_pruebas import CURP, escanear, expediente_escaneado, iniciar, pedir
from validacion import aplicacion, archivero, cerebro_red, escritorio


def _jpg(color='white'):
    from PIL import Image
    memoria = io.BytesIO()
    Image.new('RGB', (200, 280), color).save(memoria, 'JPEG')
    return memoria.getvalue()


def test_el_archivero_guarda_un_pdf_por_documento_sin_sobrescribir(tmp_path):
    import pypdf
    a = archivero.Archivero(tmp_path / 'Expedientes')
    carpeta, hecho = a.archivar(CURP, 'HERNÁNDEZ RAMOS LUIS', '1° A', {'Acta de nacimiento': [('.jpg', _jpg()), ('.jpg', _jpg('gray'))]})
    assert carpeta == tmp_path / 'Expedientes' / '1° A' / 'HERNÁNDEZ RAMOS LUIS' and hecho == {'Acta de nacimiento': 'nuevo'}
    assert len(pypdf.PdfReader(carpeta / 'Acta de nacimiento.pdf').pages) == 2  # Las dos fotos en un solo PDF.
    assert a.archivar(CURP, 'HERNÁNDEZ RAMOS LUIS', '1° A', {'Acta de nacimiento': [('.jpg', _jpg()), ('.jpg', _jpg('gray'))]})[1] == {'Acta de nacimiento': 'igual'}
    assert a.archivar(CURP, 'HERNÁNDEZ RAMOS LUIS', '1° A', {'Acta de nacimiento': [('.jpg', _jpg('black'))]})[1] == {'Acta de nacimiento': 'cambiado'}
    assert len(list((carpeta / 'anteriores').glob('Acta de nacimiento *.pdf'))) == 1
    # Pasa a 2° A: la carpeta se mueve con todo y sus anteriores.
    nueva, _ = a.archivar(CURP, 'HERNÁNDEZ RAMOS LUIS', '2° A', {})
    assert nueva == tmp_path / 'Expedientes' / '2° A' / 'HERNÁNDEZ RAMOS LUIS' and (nueva / 'anteriores').is_dir() and not carpeta.exists()
    # Otro alumno con el mismo nombre no se mezcla.
    otro, _ = a.archivar('XXXX000000HMCXXX01', 'HERNÁNDEZ RAMOS LUIS', '2° A', {'CURP': [('.jpg', _jpg())]})
    assert otro.name == 'HERNÁNDEZ RAMOS LUIS (XXXX000000)'
    assert archivero.nombre_valido('A/B: C?') == 'A B C'


@pytest.fixture
def cerebro():
    servidor = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1')
    url = iniciar(servidor)
    yield servidor, url
    servidor.shutdown()


def test_se_reconoce_al_cerebro_y_se_encuentra_en_la_red(cerebro):
    servidor, url = cerebro
    assert escritorio.es_cerebro(url)
    assert not escritorio.es_cerebro('http://127.0.0.1:9')
    assert escritorio.buscar_cerebro(url) == [url]
    # La dirección guardada ya no sirve (la red le dio otra IP): se recorre la red y aparece.
    red = ipaddress.ip_network('127.0.0.0/30')
    assert escritorio.buscar_cerebro('http://127.0.0.1:9', servidor.server_port, redes=[red]) == [url]
    assert 'Nadie contesta' in escritorio.diagnostico('http://127.0.0.1:9')
    assert 'contesta' in escritorio.diagnostico(url)


def test_el_servidor_se_reconecta_solo_y_guarda_los_pdf_por_alumno(cerebro, tmp_path):
    servidor_cerebro, url_cerebro = cerebro
    app = aplicacion.Aplicacion(tmp_path / 'sistema', puerto=0, expedientes=tmp_path / 'Expedientes', conectar_al_abrir=False)
    app.configuracion = {'cerebro_url': 'http://127.0.0.1:9', 'cerebro_clave': 'clave-de-prueba'}  # La IP de antes.
    vigia = escritorio.Vigia(app, redes=[ipaddress.ip_network('127.0.0.0/30')], puerto=servidor_cerebro.server_port)
    app.vigia = vigia
    assert vigia.revisar()['conectado'] is True
    assert app.configuracion['cerebro_url'] == url_cerebro and app.bandeja.cerebro
    servidor = aplicacion.crear_servidor(app, '127.0.0.1', clave_apagar='adios')
    app.puerto = servidor.server_port
    url = iniciar(servidor)
    assert json.load(urllib.request.urlopen(url + '/api/hola')) == {'sidp': 'servidor', 'version': '0.0.0'}
    token = {'X-SIDP-Token': app.token}
    assert pedir(url, '/api/configuracion', cabeceras=token)[1]['vigia']['conectado'] is True
    # Un expediente escaneado y guardado aparece como PDF en la carpeta del alumno.
    leido = escanear(url, app, expediente_escaneado())[1]
    codigo, guardado = pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': leido['propuesta']['alumno'],
                                                             'tutor': leido['propuesta']['tutor']}, token)
    assert codigo == 200, guardado
    carpeta = tmp_path / 'Expedientes' / 'Sin grupo' / 'HERNANDEZ RAMOS LUIS'
    assert sorted(p.name for p in carpeta.glob('*.pdf')) == ['Acta de nacimiento del alumno.pdf', 'Comprobante de domicilio.pdf', 'INE del tutor.pdf']
    # Apagar pide la clave que solo conoce esta PC.
    assert pedir(url, '/api/apagar', {}, {'X-SIDP-Apagar': 'otra'})[0] == 403
    assert pedir(url, '/api/apagar', {}, {'X-SIDP-Apagar': 'adios'})[0] == 200
