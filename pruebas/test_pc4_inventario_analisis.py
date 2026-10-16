"""La PC 4 como inventario, análisis de datos y respaldo del servidor. Todo es inventado.

Las pruebas con base de datos necesitan SIDP_PRUEBA_BASE (como test_base_cerebro.py); las demás corren siempre.
"""
import os

import pytest

from pruebas.test_base_cerebro import CURP_JUAN, alumnos, id_de
from pruebas.test_entorno_pruebas import HOY, iniciar, pedir
from validacion import aplicacion, base_cerebro, cerebro_red, respaldo

if not os.environ.get('SIDP_PRUEBA_BASE'):
    pytest.skip('sin PostgreSQL de prueba (SIDP_PRUEBA_BASE)', allow_module_level=True)
pytest.importorskip('pandas')


@pytest.fixture
def base():
    base = base_cerebro.BaseCerebro(os.environ['SIDP_PRUEBA_BASE'])
    return base.borrar_todo()


@pytest.fixture
def entorno(base, tmp_path):
    almacen = respaldo.Almacen(tmp_path / 'pc4' / 'respaldo')
    cerebro = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1', base=base,
                                         almacen=almacen, carpeta_respaldos=tmp_path / 'pc4' / 'respaldos')
    url_cerebro = iniciar(cerebro)
    app = aplicacion.Aplicacion(tmp_path / 'datos', HOY, puerto=0)
    servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    url = iniciar(servidor)
    assert app.configurar(url_cerebro, 'clave-de-prueba') is None
    yield app, url, {'X-SIDP-Token': app.token}, almacen
    servidor.shutdown()
    cerebro.shutdown()


def test_cada_pieza_tiene_su_codigo_y_nada_se_borra(base):
    mesas = base.inventario_alta('mobiliario', 'mesa binaria', {}, 4, 'Salón 1° A', [], 'Maestra Ana')
    computadoras = base.inventario_alta('computo', 'computadora de escritorio', {'Procesador': 'Ryzen 5', 'Memoria RAM': '16 GB'}, 2,
                                        'Dirección', ['SERIE-1', 'SERIE-2'], 'Maestra Ana')
    assert mesas['codigos'] == ['MOB-000001', 'MOB-000002', 'MOB-000003', 'MOB-000004']
    assert computadoras['codigos'] == ['COM-000005', 'COM-000006']
    piezas = {p['codigo']: p for p in base.inventario()['piezas']}
    assert piezas['COM-000006']['numero_serie'] == 'SERIE-2' and piezas['COM-000006']['caracteristicas']['Procesador'] == 'Ryzen 5'
    with pytest.raises(Exception, match='motivo'):
        base.inventario_cambiar('MOB-000002', 'baja', '', '', 'Maestra Ana')  # Una baja pide motivo.
    base.inventario_cambiar('mob-000002', 'baja', '', 'Se rompió una pata', 'Maestra Ana')
    assert {p['codigo']: p['estado'] for p in base.inventario()['piezas']}['MOB-000002'] == 'baja'
    with pytest.raises(Exception, match='no se borra'):
        base._consulta('DELETE FROM sidp.inventario_pieza')
    assert base._uno("SELECT count(*) FROM sidp.bitacora WHERE tabla = 'inventario_pieza'") == 7  # 6 altas y 1 cambio.
    with pytest.raises(base_cerebro.ErrorBase):
        base.inventario_alta('mobiliario', 'silla', {}, 0, '', [], 'Maestra Ana')


def test_el_panel_da_de_alta_e_imprime_etiquetas(entorno):
    app, url, token, _ = entorno
    codigo, r = pedir(url, '/api/inventario/alta', {'categoria': 'computo', 'nombre': 'Laptop', 'cantidad': 2, 'ubicacion': 'Biblioteca',
                                                      'caracteristicas': {'Marca': 'Lenovo'}, 'series': ['A1'], 'actor': 'Director'}, token)
    assert codigo == 200, r
    assert r['hecho']['codigos'] == ['COM-000001', 'COM-000002'] and len(r['piezas']) == 2
    codigo, r = pedir(url, '/api/inventario/cambiar', {'codigo': 'COM-000002', 'estado': 'regular', 'actor': 'Director'}, token)
    assert codigo == 200 and r['piezas'][1]['estado'] == 'regular'
    codigo, r = pedir(url, '/api/inventario/cambiar', {'codigo': 'COM-999999', 'estado': 'malo', 'actor': 'Director'}, token)
    assert codigo == 400 and 'No existe la pieza' in r['error']
    import urllib.request
    pagina = urllib.request.urlopen(f'{url}/api/etiquetas?codigos=COM-000001,COM-000002&t={app.token}').read().decode()
    assert pagina.count('<svg') == 2 and 'COM-000002' in pagina and 'LAPTOP' in pagina


def test_el_analisis_sale_de_la_pc4_con_pandas(entorno, base):
    app, url, token, _ = entorno
    base.cargar('2026-2027', alumnos(), 'lista_oficial', 'lista oficial')
    documento = base._uno("SELECT sidp.registrar_documento(%s, 'acta_nacimiento', %s, 'escaneo')", (id_de(base, CURP_JUAN), 'a' * 64))
    base._consulta("SELECT sidp.revisar_documento(%s, 'validado', 'Secretaria')", (documento,))
    codigo, r = pedir(url, '/api/analisis_pc4', None, token)
    assert codigo == 200, r
    assert r['kpis']['alumnos'] == 3 and r['kpis']['documentos_validados'] == 1
    assert r['matricula']['filas'][-1] == ['Total', 2, 1, 3]
    assert r['avance_por_grupo'][0]['validados'] == 1
    assert any('3 alumnos' in h for h in r['hallazgos'])
    assert 'ia' not in r
    codigo, r = pedir(url, '/api/analisis_pc4?ia=1', None, token)  # Sin Ollama, el análisis sale igual y lo dice.
    assert codigo == 200 and r['ia']['texto'] is None and 'no respondió' in r['ia']['problema']


def test_la_pc4_guarda_la_copia_del_servidor_sin_sobrescribir(entorno, tmp_path):
    app, url, token, almacen = entorno
    expediente = app.carpeta / 'expedientes' / 'E01'
    expediente.mkdir(parents=True)
    (expediente / 'acta.pdf').write_bytes(b'%PDF-1.4 version uno')
    codigo, r = pedir(url, '/api/respaldo', {}, token)
    assert codigo == 200, r
    copia = almacen.carpeta / 'actual'
    assert (copia / 'expedientes' / 'E01' / 'acta.pdf').read_bytes() == b'%PDF-1.4 version uno'
    assert (copia / 'plataforma_prueba.db').is_file() and not (copia / 'configuracion.json').exists()  # La clave no viaja.
    primera = r['enviados']
    codigo, r = pedir(url, '/api/respaldo', {}, token)
    assert r['enviados'] == 0 < primera  # Sin cambios, no viaja nada.
    (expediente / 'acta.pdf').write_bytes(b'%PDF-1.4 version dos')
    codigo, r = pedir(url, '/api/respaldo', {}, token)
    assert r['enviados'] == 1
    assert (copia / 'expedientes' / 'E01' / 'acta.pdf').read_bytes() == b'%PDF-1.4 version dos'
    anteriores = list((almacen.carpeta / 'versiones' / 'expedientes' / 'E01').glob('acta.pdf.*'))
    assert [a.read_bytes() for a in anteriores] == [b'%PDF-1.4 version uno']
    with pytest.raises(ValueError):
        almacen.guardar('../fuera.txt', b'x', respaldo._huella(b'x'))

