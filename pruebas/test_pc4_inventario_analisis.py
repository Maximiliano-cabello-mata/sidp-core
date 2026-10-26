"""La PC 4 como inventario, análisis de datos y respaldo del servidor. Todo es inventado.

Las pruebas con base de datos necesitan SIDP_PRUEBA_BASE (como test_base_cerebro.py); las demás corren siempre.
"""
import os

import pytest

from pruebas.test_base_cerebro import CURP_JUAN, alumnos
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


def _datos_inventados(base):
    """Salud, domicilio y boletas inventados para los alumnos de prueba (los de 1.° y 2.° de test_lista_oficial)."""
    from pruebas.test_lista_oficial import SEGUNDO
    from validacion.ejemplo import generar
    base.cargar('2026-2027', alumnos() + alumnos(SEGUNDO, 2), 'lista_oficial', 'lista oficial')
    juan, regina, diego = CURP_JUAN, generar.curp(SEGUNDO[0][3]), generar.curp(SEGUNDO[1][3])
    for curp, campo, valor in [
            (juan, 'alergia', 'Penicilina'), (juan, 'padecimiento', 'Asma'), (juan, 'medicamento', 'Salbutamol'),
            (regina, 'alergia', 'Negadas'), (regina, 'discapacidad', 'Hipoacusia leve'), (diego, 'padecimiento', 'Ninguno'),
            (diego, 'alergia', 'Polvo')]:
        base.agregar_dato(curp, 'salud', campo, valor, 'Secretaria')
    # Lo del 911 que pone la escuela.
    base.agregar_dato(regina, 'escolar', 'repite_grado', 'sí', 'Secretaria')
    base.agregar_dato(diego, 'escolar', 'repite_grado', 'no', 'Secretaria')
    base.agregar_dato(juan, 'escolar', 'beca', 'federal', 'Secretaria')
    for curp, municipio, colonia in [(juan, 'Chalco', 'San Martín'), (regina, 'CHALCO, EDO. MEX.', 'Col. San Martin'),
                                     (diego, 'Valle de Chalco Solidaridad', 'Darío Martínez')]:
        base.agregar_dato(curp, 'domicilio', 'municipio', municipio, 'Secretaria')
        base.agregar_dato(curp, 'domicilio', 'colonia', colonia, 'Secretaria')
    for curp, promedio in [(regina, '9.4'), (diego, '6.5')]:
        base.agregar_dato(curp, 'escolar', 'promedio_1', promedio, 'Secretaria')
        base.agregar_dato(curp, 'escolar', 'lenguajes_1', str(float(promedio) - 0.5), 'Secretaria')
    return juan, regina, diego


def test_el_analisis_es_de_los_alumnos_no_de_los_documentos(entorno, base):
    app, url, token, _ = entorno
    _datos_inventados(base)
    codigo, r = pedir(url, '/api/analisis_pc4', None, token)
    assert codigo == 200, r
    assert r['kpis']['alumnos'] == 7 and r['matricula']['filas'][-1] == ['Total', 4, 3, 7]
    assert not {'avance_por_grupo', 'faltan_por_documento', 'documentos_por_estado', 'recibidos_14_dias', 'lecturas'} & set(r)
    # Salud: solo lo necesario; "Negadas" no es una alergia.
    assert set(r['salud']) == {'alergias', 'padecimientos', 'medicamentos'} and 'medidos' not in r['kpis']
    assert sorted(r['salud']['alergias']) == [['PENICILINA', 1], ['POLVO', 1]] and r['kpis']['con_alergias'] == 2
    assert r['salud']['padecimientos'] == [['ASMA', 1]] and r['kpis']['con_medicamento'] == 1
    assert ['Hipoacusia', 1, 1] in [f[:1] + f[-2:] for f in r['discapacidad_911']['filas']]
    assert any('toman medicamento' in h for h in r['hallazgos']) and not any('dentista' in h or 'peso' in h for h in r['hallazgos'])
    # Lo del 911 que pone la escuela: cuántos ya lo tienen y cuántos faltan.
    repite = next(x for x in r['para_911'] if x['dato'] == 'Repiten el grado')
    assert (repite['con'], repite['si'], repite['de']) == (2, 1, 7) and r['becas'] == [['federal', 1]]
    assert any('Para el 911 faltan datos' in h and '5 sin el dato de «repiten el grado»' in h for h in r['hallazgos'])
    # Dónde viven: "CHALCO, EDO. MEX." y "Chalco" son el mismo municipio.
    assert r['domicilio']['municipios'][0] == ['Chalco', 2] and r['domicilio']['colonias'][0] == ['San Martin', 2]
    assert any('La mayoría vive en Chalco' in h for h in r['hallazgos'])
    # Boletas: la de 1.° de los de 2.°; un promedio bajo.
    assert r['escolar']['por_grado_cursado'] == [['1°', 8.0, 2]] and r['escolar']['bajos'] == 1
    # 911: edad al 1 de septiembre; los de la tabla suman la matrícula.
    total = r['f911']['filas'][-1]
    assert total[0] == 'Total' and total[-1] == 7 and sum(total[2:-1]) == 7
    assert r['cobertura'][0]['con'] == 3 and r['suficiente'] is False
    assert 'ia' not in r and r['estudio'] is None
    codigo, r = pedir(url, '/api/analisis_pc4?ia=1', None, token)  # Sin Ollama, el análisis sale igual y lo dice.
    assert codigo == 200 and r['ia']['texto'] is None and 'no respondió' in r['ia']['problema']


def test_el_estudio_de_la_ia_se_rehace_solo_cuando_hay_datos_nuevos(base, tmp_path):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from validacion import analisis_datos
    pedidos = []

    class Ollama(BaseHTTPRequestHandler):
        def do_POST(self):
            pedidos.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            cuerpo = json.dumps({'message': {'content': 'Salud: estudio inventado.'}}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *args):
            pass

    falsa = ThreadingHTTPServer(('127.0.0.1', 0), Ollama)
    threading.Thread(target=falsa.serve_forever, daemon=True).start()
    ocupado = [True]
    estudio = analisis_datos.Estudio(base, f'http://127.0.0.1:{falsa.server_port}/api/chat', tmp_path / 'estudio.json',
                                     ocupado=lambda: ocupado[0], minimo=5)
    try:
        juan, regina, diego = _datos_inventados(base)
        assert estudio.una_vez() is None  # La PC 4 está leyendo escaneos: espera.
        ocupado[0] = False
        assert estudio.una_vez() is None and not pedidos  # Datos de menos de la mitad: todavía no.
        from pruebas.test_lista_oficial import PRIMERO, SEGUNDO
        from validacion.ejemplo import generar
        for _, _, _, c in PRIMERO[1:] + SEGUNDO[2:]:  # Ya la mayoría tiene datos de salud.
            base.agregar_dato(generar.curp(c), 'salud', 'alergia', 'Polen', 'Secretaria')
        assert estudio.una_vez()['texto'] == 'Salud: estudio inventado.'
        guardado = estudio.guardado()
        assert guardado['al_dia'] and guardado['alumnos'] == 7 and guardado['texto'].startswith('Salud')
        pedido = pedidos[0]['messages'][0]['content']
        assert 'director y el subdirector' in pedido and 'GARCIA' not in pedido and juan not in pedido  # Sin nombres ni CURP.
        assert estudio.una_vez() is None and len(pedidos) == 1  # Sin datos nuevos no se repite.
    finally:
        falsa.shutdown()


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

