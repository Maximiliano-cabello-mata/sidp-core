"""Entorno de pruebas: padres suben por la red, el cerebro valida por IP y el .exe guarda y deja decidir."""
import datetime
import json
import threading
import urllib.error
import urllib.request
import uuid
import pytest
from pruebas.pdf_sencillo import pdf_de_texto
from validacion import analisis, aplicacion, cerebro_red
from validacion.ejemplo import generar

pypdf = pytest.importorskip('pypdf')
HOY = datetime.date(2026, 10, 14)
CURP = generar.curp('HERL180314HMCRMSA')


def iniciar(servidor):
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{servidor.server_port}'


@pytest.fixture
def entorno(tmp_path):
    cerebro = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1')
    url_cerebro = iniciar(cerebro)
    app = aplicacion.Aplicacion(tmp_path / 'datos', HOY, puerto=0)
    servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    app.puerto = servidor.server_port
    url = iniciar(servidor)
    assert app.configurar(url_cerebro, 'clave-de-prueba') is None
    yield app, url
    servidor.shutdown()
    cerebro.shutdown()


def pedir(url, ruta, datos=None, cabeceras=None, tipo='application/json'):
    cuerpo = datos if isinstance(datos, bytes) or datos is None else json.dumps(datos).encode()
    solicitud = urllib.request.Request(url + ruta, cuerpo, {'Content-Type': tipo, **(cabeceras or {})})
    try:
        with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def formulario(captura, archivos):
    limite = uuid.uuid4().hex
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="captura"\r\n\r\n{json.dumps(captura)}\r\n'.encode()]
    for campo, nombre, contenido in archivos:
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"; filename="{nombre}"\r\n'
                      f'Content-Type: application/octet-stream\r\n\r\n'.encode() + contenido + b'\r\n')
    return b''.join(partes) + f'--{limite}--\r\n'.encode(), f'multipart/form-data; boundary={limite}'


def expediente_pdf(domicilio_comprobante='C. PINO NO. 5 COL. CENTRO TOLUCA'):
    textos = {
        'acta_alumno': generar.acta('LUIS', 'HERNANDEZ', 'RAMOS', '14/03/2018', 'HOMBRE', CURP, 'JUAN PEREZ LOPEZ', 'MARIA ELENA RAMOS SOTO'),
        'certificado_medico': generar.medico('LUIS HERNANDEZ RAMOS'),
        'ine_tutor': generar.ine('RAMOS', 'SOTO', 'MARIA ELENA', domicilio_comprobante),
        'comprobante': generar.cfe('MARIA ELENA RAMOS SOTO', domicilio_comprobante, '20 SEP 2026'),
    }
    captura = {'alumno': {'nombres': 'Luis', 'primer_apellido': 'Hernández', 'segundo_apellido': 'Ramos', 'curp': CURP},
               'tutor': {'nombres': 'María Elena', 'primer_apellido': 'Ramos', 'segundo_apellido': 'Soto', 'parentesco': 'madre',
                         'domicilio': 'Calle Pino 5, Col. Centro, Toluca'}}
    return captura, [(espacio, f'{espacio}.pdf', pdf_de_texto(texto.splitlines())) for espacio, texto in textos.items()]


def test_un_padre_sube_el_cerebro_valida_y_el_exe_guarda(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    codigo, respuesta = pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    assert codigo == 200 and respuesta == {'expediente': '0001', 'estado': 'listo para autorizar'}
    resultado = app.bandeja.resultados['0001']
    assert resultado['procesado_en'].startswith('cerebro')
    assert resultado['extraidos']['acta_curps'] == [CURP]
    carpeta = app.carpeta / 'expedientes' / '0001'
    assert (carpeta / 'acta_alumno_1.pdf').exists() and (carpeta / 'resultado.json').exists()
    base = app.bandeja.base()
    assert base['alumno'] == 1 and base['archivo'] == 4 and base['documento'] == 4 and base['sugerencia_ia'] == 3  # acta, certificado y el expediente
    # Lo extraído es propuesta: la CURP no se confirma sola.
    db = app.bandeja.registro.db
    assert db.execute('SELECT curp_confirmada FROM alumno').fetchone()[0] == 0
    propuestas = [json.loads(c) for (c,) in db.execute("SELECT contenido FROM sugerencia_ia WHERE objeto_tipo = 'documento'")]
    assert any(p['curp_propuesta'] == CURP for p in propuestas)


def test_otro_domicilio_va_a_revision(entorno):
    _, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf('CALLE PINO 15 COL CENTRO TOLUCA'))
    assert pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)[1]['estado'] == 'revisión manual'


def test_el_panel_pide_el_token_y_rechazar_pide_motivo(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    assert pedir(url, '/api/estado')[0] == 403
    token = {'X-SIDP-Token': app.token}
    assert pedir(url, '/api/estado', cabeceras=token)[1]['medidas']['revisados'] == 1
    assert pedir(url, '/api/decidir', {'id': '0001', 'decision': 'rechazado'}, token)[0] == 400
    codigo, respuesta = pedir(url, '/api/decidir', {'id': '0001', 'decision': 'rechazado', 'motivo': 'INE ilegible'}, token)
    assert codigo == 200 and 'INE ilegible' in respuesta['reporte_para_padre']
    assert app.bandeja.base()['revision_documento'] == 4
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(f'{url}/api/archivo?id=0001&nombre=../captura.json&t={app.token}')


def test_el_cerebro_lee_lo_guardado_con_su_clave(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    assert pedir(url, '/api/cerebro/datos')[0] == 401
    codigo, datos = pedir(url, '/api/cerebro/datos', cabeceras={'X-SIDP-Clave': 'clave-de-prueba'})
    assert codigo == 200 and datos['expedientes'][0]['extraidos']['acta_curps'] == [CURP]


def test_sin_cerebro_los_procesos_corren_en_la_pc_del_administrador(entorno):
    app, url = entorno
    app.bandeja.cerebro = ('http://127.0.0.1:9', 'x')  # El cerebro se apagó.
    cuerpo, tipo = formulario(*expediente_pdf())
    assert pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)[1]['estado'] == 'listo para autorizar'
    assert 'no respondió' in app.bandeja.resultados['0001']['procesado_en']


def test_el_cerebro_pide_su_clave():
    cerebro = cerebro_red.crear_servidor('buena', 0, anfitrion='127.0.0.1')
    url = iniciar(cerebro)
    assert pedir(url, '/salud', cabeceras={'X-SIDP-Clave': 'mala'})[0] == 401
    assert pedir(url, '/opinar', {'tipo': 'nombre', 'a': 'A', 'b': 'B'}, {'X-SIDP-Clave': 'mala'})[0] == 401
    cerebro.shutdown()


def test_el_cerebro_analiza_y_el_informe_se_guarda_en_el_exe(entorno, tmp_path):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    app.bandeja.decidir('0001', 'autorizado')
    clave = tmp_path / 'clave.txt'
    clave.write_text('clave-de-prueba', encoding='utf-8')
    assert analisis.main(['--exe', url, '--clave', str(clave)]) == 0
    informe = next((app.carpeta / 'analisis').glob('*.md')).read_text(encoding='utf-8')
    assert 'coinciden con el sistema: 1' in informe and 'HERNANDEZ' not in informe


def test_la_pagina_publica_solo_lleva_codigo_y_expedientes_inventados(tmp_path):
    from herramientas import armar_pagina
    destino = armar_pagina.armar(tmp_path / 'pagina')
    assert '"modo": "demo"' in (destino / 'index.html').read_text(encoding='utf-8')
    codigo = json.loads((destino / 'codigo.json').read_text(encoding='utf-8'))
    assert 'validacion/servicio.py' in codigo and 'database/diseno_integral.sql' in codigo
    ejemplo = json.loads((destino / 'ejemplo.json').read_text(encoding='utf-8'))
    assert 'expedientes/E01/captura.json' in ejemplo
    assert all(r.endswith(('.txt', '.json', '.csv')) and not r.endswith('resultado.json') for r in ejemplo)


def constancia(curp=CURP, nombre='LUIS HERNANDEZ RAMOS'):
    """Una constancia de la CURP inventada, con las frases que trae la de RENAPO."""
    return pdf_de_texto(['CONSTANCIA DE LA CLAVE UNICA DE REGISTRO DE POBLACION', f'Clave: {curp}', f'Nombre: {nombre}',
                         'Entidad de registro: MEXICO', 'Registro Nacional de Poblacion'])


def subir_constancia(url, app, contenido):
    cabeceras = {'X-SIDP-Token': app.token, 'X-SIDP-Nombre': 'constancia.pdf'}
    return pedir(url, '/api/renapo/constancia', contenido, cabeceras, tipo='application/pdf')


def estado_curp(url, app):
    return pedir(url, '/api/curps', cabeceras={'X-SIDP-Token': app.token})[1]['alumnos']


def test_la_curp_pasa_de_sin_validar_a_validada_con_la_constancia(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    assert [(a['curp'], a['estado']) for a in estado_curp(url, app)] == [(CURP, 'sin_validar')]
    assert pedir(url, '/api/curps')[0] == 403  # Solo el panel.
    codigo, respuesta = subir_constancia(url, app, constancia())
    assert codigo == 200 and respuesta['estado'] == 'validada' and 'Luis' in respuesta['mensaje']
    assert estado_curp(url, app)[0]['estado'] == 'validada'
    db = app.bandeja.registro.db
    assert db.execute('SELECT curp_confirmada FROM alumno').fetchone()[0] == 1
    assert db.execute("SELECT estado, origen FROM documento WHERE tipo = 'curp'").fetchall() == [('validado', 'escaneo')]
    assert db.execute("SELECT count(*) FROM bitacora WHERE accion = 'alumno.renapo_validada'").fetchone()[0] == 1
    assert len(list((app.carpeta / 'renapo').glob('constancia_*.pdf'))) == 1
    # Arrastrarla otra vez no duplica nada.
    assert subir_constancia(url, app, constancia())[1]['mensaje'].endswith('ya estaba validada.')
    assert db.execute("SELECT count(*) FROM documento WHERE tipo = 'curp'").fetchone()[0] == 1


def test_la_constancia_con_otro_nombre_queda_por_revisar(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    codigo, respuesta = subir_constancia(url, app, constancia(nombre='LUIS HERNANDEZ RAMIREZ'))
    assert codigo == 200 and respuesta['estado'] == 'no_coincide' and 'RAMOS' in respuesta['mensaje']
    fila = estado_curp(url, app)[0]
    assert fila['estado'] == 'no_coincide' and 'RAMOS' in fila['detalle']
    assert app.bandeja.registro.db.execute('SELECT curp_confirmada FROM alumno').fetchone()[0] == 0


def test_la_constancia_de_otra_curp_avisa_cual_escribio_el_padre(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    correcta = generar.curp('HERL180314HMCRMSB')
    respuesta = subir_constancia(url, app, constancia(curp=correcta))[1]
    assert respuesta['estado'] == 'no_coincide' and correcta in respuesta['mensaje'] and CURP in respuesta['mensaje']


def test_lo_que_no_es_constancia_no_cambia_nada(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    codigo, respuesta = subir_constancia(url, app, b'no soy un pdf')
    assert codigo == 400 and 'no es un PDF' in respuesta['error']
    codigo, respuesta = subir_constancia(url, app, pdf_de_texto(['RECIBO DE LUZ', CURP]))
    assert codigo == 400 and 'no parece la constancia' in respuesta['error']
    otra = generar.curp('SOTM900101MMCTRRA')
    codigo, respuesta = subir_constancia(url, app, constancia(curp=otra, nombre='MARTA SOTO TORRES'))
    assert codigo == 400 and otra in respuesta['error']
    assert estado_curp(url, app)[0]['estado'] == 'sin_validar'
    assert not (app.carpeta / 'renapo').exists()  # Nada se guardó.


def test_renapo_no_la_encontro_queda_anotado(entorno):
    app, url = entorno
    cuerpo, tipo = formulario(*expediente_pdf())
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    alumno = estado_curp(url, app)[0]['alumno']
    codigo, respuesta = pedir(url, '/api/renapo/no_encontrada', {'alumno': alumno}, {'X-SIDP-Token': app.token})
    assert codigo == 200 and respuesta['alumnos'][0]['estado'] == 'no_encontrada'


def test_el_tutor_queda_vinculado_solo_al_autorizar(entorno):
    app, url = entorno
    db = app.bandeja.registro.db
    token = {'X-SIDP-Token': app.token}
    captura, archivos = expediente_pdf()
    cuerpo, tipo = formulario(captura, archivos)
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    assert db.execute('SELECT count(*) FROM alumno_tutor').fetchone()[0] == 0
    pedir(url, '/api/decidir', {'id': '0001', 'decision': 'autorizado'}, token)
    # Otra persona manda un expediente con la misma CURP: no le quita nada a la madre.
    extrano = {**captura, 'tutor': {'nombres': 'Extraño', 'primer_apellido': 'Pérez', 'parentesco': 'otro', 'domicilio': 'X'}}
    cuerpo, tipo = formulario(extrano, archivos)
    pedir(url, '/api/padres/enviar', cuerpo, tipo=tipo)
    pedir(url, '/api/decidir', {'id': '0002', 'decision': 'rechazado', 'motivo': 'No es su tutor'}, token)
    filas = db.execute('SELECT t.nombres, a.principal, a.puede_recoger FROM alumno_tutor a JOIN tutor t ON t.id = a.tutor_id').fetchall()
    assert filas == [('María Elena', 1, 1)]


def expediente_escaneado():
    """Un solo PDF con varias hojas, como lo deja el escáner: acta, INE y comprobante, sin nada capturado."""
    import io
    domicilio = 'C. PINO NO. 5 COL. CENTRO TOLUCA'
    hojas = [generar.acta('LUIS', 'HERNANDEZ', 'RAMOS', '14/03/2018', 'HOMBRE', CURP, 'JUAN PEREZ LOPEZ', 'MARIA ELENA RAMOS SOTO'),
             generar.ine('RAMOS', 'SOTO', 'MARIA ELENA', domicilio),
             generar.cfe('MARIA ELENA RAMOS SOTO', domicilio, '20 SEP 2026')]
    escritor = pypdf.PdfWriter()
    for texto in hojas:
        escritor.add_page(pypdf.PdfReader(io.BytesIO(pdf_de_texto(texto.splitlines()))).pages[0])
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def escanear(url, app, contenido, nombre='expediente.pdf'):
    limite = uuid.uuid4().hex
    cuerpo = (f'--{limite}\r\nContent-Disposition: form-data; name="archivo"; filename="{nombre}"\r\n'
              f'Content-Type: application/pdf\r\n\r\n'.encode() + contenido + f'\r\n--{limite}--\r\n'.encode())
    return pedir(url, '/api/escaneo/leer', cuerpo, {'X-SIDP-Token': app.token}, tipo=f'multipart/form-data; boundary={limite}')


def test_el_escaneo_propone_los_datos_y_guarda_el_expediente_validado_en_papel(entorno):
    app, url = entorno
    token = {'X-SIDP-Token': app.token}
    assert pedir(url, '/api/escaneo/leer', b'', tipo='multipart/form-data; boundary=x')[0] == 403  # Solo el panel.
    codigo, leido = escanear(url, app, expediente_escaneado())
    assert codigo == 200, leido
    assert [p['tipo'] for p in leido['paginas']] == ['acta_alumno', 'ine_tutor', 'comprobante']
    propuesta = leido['propuesta']
    assert propuesta['alumno']['curp'] == CURP and propuesta['alumno']['nombres'] == 'LUIS'
    assert (propuesta['alumno']['primer_apellido'], propuesta['alumno']['segundo_apellido']) == ('HERNANDEZ', 'RAMOS')
    assert propuesta['tutor']['nombres'] == 'MARIA ELENA' and propuesta['tutor']['parentesco'] == 'madre'
    # La persona revisa, corrige si hace falta y guarda.
    codigo, guardado = pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': propuesta['alumno'],
                                                             'tutor': {**propuesta['tutor'], 'telefono': '7221234567'}}, token)
    assert codigo == 200 and guardado['expediente'] == '0001', guardado
    db = app.bandeja.registro.db
    assert db.execute('SELECT curp, fecha_nacimiento, sexo FROM alumno').fetchall() == [(CURP, '2018-03-14', 'H')]
    assert db.execute('SELECT t.nombres, a.parentesco FROM alumno_tutor a JOIN tutor t ON t.id = a.tutor_id').fetchall() == [('MARIA ELENA', 'madre')]
    estados = db.execute('SELECT tipo, estado, origen FROM documento ORDER BY tipo').fetchall()
    assert estados == [('acta', 'validado', 'escaneo'), ('comprobante_domicilio', 'validado', 'escaneo'), ('ine_tutor', 'validado', 'escaneo')]
    estado = pedir(url, '/api/estado', cabeceras=token)[1]
    assert estado['medidas']['en_papel'] == 1 and estado['medidas']['revision'] == 0
    assert estado['expedientes'][0]['decision']['decision'] == 'autorizado'
    # "Revisar todo" no lo vuelve a revisar, y el escaneo temporal ya se borró.
    pedir(url, '/api/revisar_todo', {}, token)
    assert app.bandeja.resultados['0001']['estado'] == 'validado en papel'
    assert not list((app.carpeta / 'escaneos').iterdir())
    assert sorted(p.name for p in (app.carpeta / 'expedientes' / '0001').glob('*.pdf')) == ['acta_alumno_1.pdf', 'comprobante_1.pdf', 'ine_tutor_1.pdf']


def test_el_escaneo_sin_nombre_no_se_guarda_y_se_puede_descartar(entorno):
    app, url = entorno
    token = {'X-SIDP-Token': app.token}
    leido = escanear(url, app, expediente_escaneado())[1]
    codigo, respuesta = pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': {'nombres': 'Luis'}}, token)
    assert codigo == 400 and 'apellido' in respuesta['error']
    codigo, respuesta = pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': {**leido['propuesta']['alumno'], 'curp': 'ABC'}}, token)
    assert codigo == 400 and 'CURP' in respuesta['error']
    assert pedir(url, '/api/escaneo/descartar', {'lote': leido['lote']}, token)[0] == 200
    assert pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': leido['propuesta']['alumno']}, token)[0] == 400
    assert pedir(url, '/api/escaneo/descartar', {'lote': '../expedientes'}, token)[0] == 400
    assert not app.bandeja.expedientes()
