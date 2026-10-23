"""La biblioteca y el motor de documentos en la base de la PC 4. Todo es inventado.

Necesita SIDP_PRUEBA_BASE (como test_base_cerebro.py); las pruebas sin base corren siempre.
"""
import base64
import io
import os

import pytest

from validacion import biblioteca


def test_el_isbn_se_revisa_y_el_lector_de_codigo_de_barras_lo_encuentra():
    assert biblioteca.isbn13('978-607-01-0789-4') == '9786070107894'
    assert biblioteca.isbn13('9786070107896') is None  # Dígito verificador mal.
    assert biblioteca.isbn13('968-16-0153-x') == '9789681601539'  # ISBN-10 de antes: se pasa a 13.
    zxingcpp = pytest.importorskip('zxingcpp')
    cv2 = pytest.importorskip('cv2')
    import numpy
    imagen = numpy.array(zxingcpp.create_barcode('9786070107894', zxingcpp.BarcodeFormat.EAN13).to_image(scale=4))
    imagen = cv2.copyMakeBorder(imagen, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    assert biblioteca.codigos_de_barras(cv2.imencode('.png', imagen)[1].tobytes()) == ['9786070107894']


if os.environ.get('SIDP_PRUEBA_BASE'):
    pytest.importorskip('pg8000')
    from pruebas.test_base_cerebro import CURP_JUAN, alumnos
    from pruebas.test_entorno_pruebas import iniciar, pedir
    from validacion import base_cerebro, cerebro_red
con_base = pytest.mark.skipif(not os.environ.get('SIDP_PRUEBA_BASE'), reason='sin PostgreSQL de prueba (SIDP_PRUEBA_BASE)')


@pytest.fixture
def cerebro(monkeypatch):
    monkeypatch.setenv('SIDP_SIN_INTERNET', '1')
    base = base_cerebro.BaseCerebro(os.environ['SIDP_PRUEBA_BASE']).borrar_todo()
    base.cargar('2026-2027', alumnos(), 'lista_oficial', 'lista oficial')
    servidor = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1', base=base)
    url = iniciar(servidor)
    yield base, url, {'X-SIDP-Clave': 'clave-de-prueba'}
    servidor.shutdown()


@con_base
def test_registrar_prestar_y_devolver_libros(cerebro, monkeypatch):
    base, url, clave = cerebro
    from validacion import vision
    monkeypatch.setattr(vision, 'elegir', lambda url=None, pedido=None: 'modelo-de-prueba')
    monkeypatch.setattr(vision, 'preguntar', lambda *a, **k: ({'titulo': 'El libro de los cuentos', 'autor': 'Ana Ruiz', 'editorial': 'SEP',
                                                              'anio': '2010', 'isbn': '', 'serie': 'pasos de luna'}, 30.0))
    foto = {'nombre': 'portada.jpg', 'contenido': base64.b64encode(b'no es una imagen de verdad').decode()}
    codigo, visto = pedir(url, '/biblioteca/identificar', {'fotos': [foto]}, clave)
    assert codigo == 200, visto
    assert visto['metodo'] == 'visto' and visto['existente'] is None and visto['propuesta']['serie'] == 'Pasos de luna'
    codigo, alta = pedir(url, '/biblioteca/alta', {**visto['propuesta'], 'cuantos': 2, 'ubicacion': 'Estante 2', 'origen': 'visto', 'actor': 'Bibliotecaria'}, clave)
    assert codigo == 200, alta
    assert alta['codigos'] == ['LIB-000001', 'LIB-000002'] and alta['ejemplares'] == 2
    # Otra foto del mismo libro: se reconoce por el parecido del título y solo se suma un ejemplar.
    codigo, otra = pedir(url, '/biblioteca/identificar', {'fotos': [foto]}, clave)
    assert otra['existente']['titulo'] == 'El libro de los cuentos' and otra['parecidos'][0]['parecido'] >= biblioteca.MUY_PARECIDO
    assert pedir(url, '/biblioteca/alta', {'titulo_id': otra['existente']['id'], 'cuantos': 1, 'actor': 'Bibliotecaria'}, clave)[1]['ejemplares'] == 3
    # Con ISBN: el código de barras lo encuentra en los que ya hay.
    codigo, diccionario = pedir(url, '/biblioteca/alta', {'titulo': 'Diccionario escolar', 'isbn': '978-607-01-0789-4', 'tipo': 'consulta',
                                                          'actor': 'Bibliotecaria'}, clave)
    assert codigo == 200 and diccionario['codigos'] == ['LIB-000004']
    assert biblioteca._por_isbn(base, ['9786070107894'])['titulo'] == 'Diccionario escolar'
    # Prestar con el lector (teclado latinoamericano: el guion llega como apóstrofo) y devolver.
    codigo, prestado = pedir(url, '/biblioteca/prestar', {'codigo': "lib'000001", 'curp': CURP_JUAN, 'actor': 'Bibliotecaria'}, clave)
    assert codigo == 200, prestado
    assert prestado['titulo'] == 'El libro de los cuentos' and prestado['biblioteca']['resumen']['prestados'] == 1
    assert prestado['biblioteca']['prestamos'][0]['curp'] == CURP_JUAN and prestado['biblioteca']['prestamos'][0]['grupo'] == '1° A'
    assert prestado['biblioteca']['lectores'][0]['grupo'] == '1° A' and len(prestado['biblioteca']['lectores'][0]['alumnos']) == 3
    codigo, r = pedir(url, '/biblioteca/prestar', {'codigo': 'LIB-000001', 'curp': CURP_JUAN, 'actor': 'Bibliotecaria'}, clave)
    assert codigo == 400 and 'no está en el estante' in r['error']
    codigo, r = pedir(url, '/biblioteca/prestar', {'codigo': 'LIB-000004', 'curp': CURP_JUAN, 'actor': 'Bibliotecaria'}, clave)
    assert codigo == 400 and 'consulta' in r['error']  # El diccionario no sale de la biblioteca.
    pedir(url, '/biblioteca/prestar', {'codigo': 'LIB-000002', 'curp': CURP_JUAN, 'actor': 'Bibliotecaria'}, clave)
    codigo, r = pedir(url, '/biblioteca/prestar', {'codigo': 'LIB-000003', 'curp': CURP_JUAN, 'actor': 'Bibliotecaria'}, clave)
    assert codigo == 400 and 'el máximo es 2' in r['error']
    codigo, devuelto = pedir(url, '/biblioteca/devolver', {'codigo': 'LIB-000001', 'estado': 'malo', 'actor': 'Bibliotecaria'}, clave)
    assert codigo == 200 and devuelto['atraso'] == 0 and devuelto['lector'] == 'JUAN GARCIA'
    assert base._uno("SELECT situacion FROM sidp.biblio_ejemplar WHERE codigo = 'LIB-000001'") == 'en_reparacion'
    codigo, etiquetas = pedir(url, '/biblioteca/etiquetas?codigos=LIB-000001,LIB-000004', cabeceras=clave)
    assert [e['nombre'] for e in etiquetas['etiquetas']] == ['El libro de los cuentos', 'Diccionario escolar']
    with pytest.raises(Exception):
        base._consulta('DELETE FROM sidp.biblio_ejemplar')  # En la base no se borra nada.
    # Borrar a un alumno no borra la historia de los libros.
    base.borrar_alumno(CURP_JUAN, 'Se cargó dos veces', 'directora')
    assert base._uno('SELECT lector FROM sidp.biblio_prestamo WHERE alumno_id IS NULL LIMIT 1') == 'Alumno borrado'


@con_base
def test_la_pc_4_arma_los_documentos_y_guarda_lo_del_911_de_un_grupo(cerebro):
    base, url, clave = cerebro
    import openpyxl
    codigo, lista = pedir(url, '/documentos', cabeceras=clave)
    assert codigo == 200 and lista['alumnos'] == 3 and {f['clave'] for f in lista['faltan']} >= {'repite', 'beca'}
    codigo, grupo = pedir(url, '/registros?grado=1&letra=A', cabeceras=clave)
    assert [c['clave'] for c in grupo['columnas']] == ['repite', 'procedencia', 'beca', 'lengua_indigena', 'lengua', 'afro']
    assert len(grupo['alumnos']) == 3 and grupo['alumnos'][0]['repite'] is None
    datos = [{'curp': a['curp'], 'categoria': 'escolar', 'campo': 'repite_grado', 'valor': 'No'} for a in grupo['alumnos']]
    datos.append({'curp': CURP_JUAN, 'categoria': 'escolar', 'campo': 'beca', 'valor': 'federal'})
    codigo, r = pedir(url, '/dato/varios', {'datos': datos, 'persona': 'Secretaria'}, clave)
    assert codigo == 200 and r['hecho'] == {'guardados': 4}
    codigo, r = pedir(url, '/dato/varios', {'datos': [{'curp': CURP_JUAN, 'categoria': 'escolar', 'campo': 'beca', 'valor': 'mucha'}]}, clave)
    assert codigo == 409 and 'no es una de las opciones' in r['error']
    assert 'repite' not in {f['clave'] for f in pedir(url, '/documentos', cabeceras=clave)[1]['faltan']}
    codigo, hecho = pedir(url, '/documento', {'clave': '911', 'formato': 'xlsx', 'escuela': {'nombre': 'Escuela de prueba', 'cct': '15EPR0000X'}},
                          clave)
    assert codigo == 200 and hecho['nombre'] == '911_inicio_2026-2027.xlsx'
    libro = openpyxl.load_workbook(io.BytesIO(base64.b64decode(hecho['contenido'])))
    repetidores = [[c.value for c in fila] for fila in libro['Repetidores'].iter_rows(min_row=5, max_row=5)][0]
    assert repetidores == ['1°', 2, 1, 3, 0, 0, 0, 3, 0]  # Inscritos de 1.°: 2 hombres y 1 mujer; ninguno repite.
    assert libro['Escuela']['B6'].value == '15EPR0000X'
    codigo, r = pedir(url, '/documento', {'clave': 'lista', 'formato': 'xlsx', 'grado': 4, 'letra': 'A'}, clave)
    assert codigo == 400 and 'No hay alumnos' in r['error']


@con_base
def test_quien_atiende_la_biblioteca_presta_desde_otra_pc_sin_ver_los_grupos(cerebro, tmp_path):
    from pruebas.test_entorno_pruebas import HOY
    from validacion import aplicacion
    base, url_cerebro, clave = cerebro
    app = aplicacion.Aplicacion(tmp_path / 'datos', HOY, puerto=0)
    servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    url = iniciar(servidor)
    try:
        assert app.configurar(url_cerebro, 'clave-de-prueba') is None
        app.cuentas.crear({'nombres': 'Luz', 'primer_apellido': 'Paz', 'rol': 'apoyo', 'usuario': 'luz', 'contrasena': 'secreta123'})
        codigo, entrada = pedir(url, '/api/entrar', {'usuario': 'luz', 'contrasena': 'secreta123'})
        assert codigo == 200 and 'biblioteca' in entrada['usuario']['permisos'] and 'grupos' not in entrada['usuario']['permisos']
        sesion = {'X-SIDP-Token': entrada['token']}
        assert pedir(url, '/api/grupos', cabeceras=sesion)[0] == 403
        codigo, alta = pedir(url, '/api/biblioteca/alta', {'titulo': 'Cuentos de la selva', 'cuantos': 1}, sesion)
        assert codigo == 200 and alta['codigos'] == ['LIB-000001'] and alta['biblioteca']['lectores'][0]['grupo'] == '1° A'
        assert base._uno('SELECT actor FROM sidp.biblio_titulo') == 'Luz Paz'  # Queda quién lo registró.
        codigo, prestado = pedir(url, '/api/biblioteca/prestar', {'codigo': 'LIB-000001', 'curp': CURP_JUAN}, sesion)
        assert codigo == 200, prestado
        import urllib.request
        with urllib.request.urlopen(f'{url}/api/biblioteca/etiquetas?codigos=LIB-000001&t={entrada["token"]}', timeout=30) as respuesta:
            pagina = respuesta.read().decode()
        assert 'Cuentos de la selva' in pagina and '<svg' in pagina and 'contraportada' in pagina
        assert pedir(url, '/api/yo', cabeceras={'X-SIDP-Token': app.token})[1]['nombre'] == 'Esta computadora'
        assert pedir(url, '/api/escuela', cabeceras=sesion)[0] == 200  # El nombre de la escuela, sí; cambiarlo, no.
        assert pedir(url, '/api/escuela/guardar', {'nombre': 'Otra'}, sesion)[0] == 403
        # SIDP-Biblioteca.exe: la ventana de la biblioteca pasa por esta misma computadora hasta el servidor.
        from validacion import biblioteca_pc
        puente = biblioteca_pc.crear_puente(url, 0)
        por_puente = iniciar(puente)
        try:
            codigo, resumen = pedir(por_puente, '/api/biblioteca', cabeceras=sesion)
            assert codigo == 200 and resumen['prestamos'][0]['codigo'] == 'LIB-000001'
            assert pedir(por_puente, '/api/grupos', cabeceras=sesion)[0] == 403
        finally:
            puente.shutdown()
    finally:
        servidor.shutdown()


def test_la_computadora_de_la_biblioteca_encuentra_el_servidor_y_avisa_si_no_contesta(tmp_path):
    import urllib.error
    import urllib.request

    from pruebas.test_entorno_pruebas import HOY, iniciar
    from validacion import aplicacion, biblioteca_pc
    servidor = aplicacion.crear_servidor(aplicacion.Aplicacion(tmp_path / 'datos', HOY, puerto=0), '127.0.0.1')
    url = iniciar(servidor)
    puente = biblioteca_pc.crear_puente(url, 0)
    por_puente = iniciar(puente)
    try:
        assert biblioteca_pc.es_servidor(url) and biblioteca_pc.buscar_servidor(url) == url
        assert biblioteca_pc.buscar_servidor('http://127.0.0.1:9', redes=[]) is None
        with urllib.request.urlopen(por_puente + '/', timeout=30) as respuesta:  # La pantalla viene del servidor.
            assert 'text/html' in respuesta.headers['Content-Type'] and b'biblioteca' in respuesta.read()
        servidor.shutdown()
        servidor.server_close()
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(por_puente + '/api/biblioteca', timeout=30)
        assert error.value.code == 502 and 'No contesta el servidor' in error.value.read().decode()
    finally:
        puente.shutdown()
