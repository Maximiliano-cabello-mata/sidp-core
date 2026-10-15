"""La base de datos del cerebro (PostgreSQL de la PC 4): el padrón y la comparación de lo leído contra él.

Necesita un PostgreSQL de prueba: SIDP_PRUEBA_BASE=postgresql://usuario:contraseña@127.0.0.1:5432/base
(en CI lo levanta el trabajo "base_cerebro"). Sin él, estas pruebas se saltan. Todo es inventado.
"""
import json
import os
import urllib.error
import urllib.request

import pytest

from pruebas.test_entorno_pruebas import HOY, escanear, iniciar, pedir
from pruebas.test_lista_oficial import PRIMERO, pdf_de_hojas
from validacion import aplicacion, base_cerebro, cerebro_red
from validacion.ejemplo import generar

pytest.importorskip('pg8000')
pytest.importorskip('pypdf')
if not os.environ.get('SIDP_PRUEBA_BASE'):
    pytest.skip('sin PostgreSQL de prueba (SIDP_PRUEBA_BASE)', allow_module_level=True)

CURP_JUAN = generar.curp('GAHJ200512HMCRRNA')


@pytest.fixture
def base():
    base = base_cerebro.BaseCerebro(os.environ['SIDP_PRUEBA_BASE']).preparar()
    base._consulta('TRUNCATE padron_alumno, lectura')  # Solo en la base de prueba.
    base.preparar()  # Correrlo dos veces no rompe nada.
    return base


def alumnos():
    return [{'curp': generar.curp(c), 'primer_apellido': p, 'segundo_apellido': s, 'nombres': n, 'grado': 1, 'letra': 'A'}
            for p, s, n, c in PRIMERO]


def test_el_padron_se_carga_y_el_que_sale_de_la_lista_se_apaga(base):
    assert base.cargar('2026-2027', alumnos()) == 3
    assert base.resumen()['alumnos'] == 3 and base.resumen()['motor'].startswith('PostgreSQL')
    assert base.cargar('2026-2027', alumnos()[:2]) == 2
    assert base.resumen()['alumnos'] == 2
    assert base._consulta('SELECT count(*) FROM padron_alumno')[0][0] == 3  # No se borra: queda apagado.


def test_una_curp_con_una_letra_mal_leida_encuentra_al_alumno(base):
    base.cargar('2026-2027', alumnos())
    leida = CURP_JUAN[:13] + ('P' if CURP_JUAN[13] != 'P' else 'T') + CURP_JUAN[14:]
    sugerencias = base.sugerir(f'CURP: {leida}')
    assert [(s['por'], s['curp'], s['distancia'], s['nombres']) for s in sugerencias] == [('curp', CURP_JUAN, 1, 'JUAN')]
    assert base.sugerir('CURP: ' + generar.curp('XEXX010101HNEXXXA')) == []  # Nadie se le parece.


def test_el_nombre_mal_escrito_o_en_otro_orden_encuentra_al_alumno(base):
    base.cargar('2026-2027', alumnos())
    for texto in ('Nombre: JUAN GARCIA HERNANDES', 'HERNÁNDEZ GARCÍA JUAN', 'Registrado:\nLopez Martinez Ana Sofia'):
        primero = base.sugerir(texto)[0]
        assert primero['por'] == 'nombre' and primero['parecido'] >= base_cerebro.NOMBRE_MINIMO, texto
    assert base.sugerir('PEDRO RAMIREZ OCHOA') == []


def test_el_exe_manda_el_padron_y_el_escaneo_se_corrige_con_el(base, tmp_path):
    cerebro = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1', base=base)
    url_cerebro = iniciar(cerebro)
    app = aplicacion.Aplicacion(tmp_path / 'datos', HOY, puerto=0)
    servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    url = iniciar(servidor)
    try:
        assert app.configurar(url_cerebro, 'clave-de-prueba') is None
        token = {'X-SIDP-Token': app.token}
        filas = [{k: a[k] for k in ('curp', 'primer_apellido', 'segundo_apellido', 'nombres')} for a in alumnos()]
        guardado = pedir(url, '/api/listas/guardar', {'grado': 1, 'letra': 'A', 'filas': filas}, token)[1]
        assert '3 alumnos' in guardado['padron'], guardado['padron']
        solicitud = urllib.request.Request(url_cerebro + '/salud', headers={'X-SIDP-Clave': 'clave-de-prueba'})
        assert json.load(urllib.request.urlopen(solicitud))['base']['alumnos'] == 3
        # El acta escaneada trae la CURP con una letra mal leída: el cerebro propone la del padrón.
        leida = CURP_JUAN[:13] + ('P' if CURP_JUAN[13] != 'P' else 'T') + CURP_JUAN[14:]
        acta = generar.acta('JUAN', 'GARCIA', 'HERNANDEZ', '12/05/2020', 'HOMBRE', leida, 'PEDRO GARCIA RUIZ', 'ROSA HERNANDEZ DIAZ')
        codigo, leido = escanear(url, app, pdf_de_hojas([acta.splitlines()]))
        assert codigo == 200, leido
        propuesta = leido['propuesta']
        assert propuesta['alumno']['curp'] == CURP_JUAN, propuesta
        assert 'compárala con el acta' in propuesta['avisos'][0]
        assert leido['parecidos'] and leido['parecidos'][0]['curp'] == CURP_JUAN  # Y se liga al alumno de la lista.
        assert base.resumen()['lecturas'] == 1
    finally:
        servidor.shutdown()
        cerebro.shutdown()


def test_sin_base_el_cerebro_responde_503_al_padron():
    cerebro = cerebro_red.crear_servidor('clave', 0, anfitrion='127.0.0.1')
    url = iniciar(cerebro)
    try:
        solicitud = urllib.request.Request(url + '/padron', b'{"ciclo": "x", "alumnos": []}', {'X-SIDP-Clave': 'clave'})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(solicitud)
        assert error.value.code == 503
    finally:
        cerebro.shutdown()
