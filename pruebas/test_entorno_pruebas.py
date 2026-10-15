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
