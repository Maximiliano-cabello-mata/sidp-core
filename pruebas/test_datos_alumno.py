"""Sacar los datos de cada campo de lo escaneado y guardarlos en el expediente del alumno (PC 4).

Las primeras pruebas no necesitan nada. Las de la base necesitan el PostgreSQL de prueba (SIDP_PRUEBA_BASE).
El modelo que ve se reemplaza por respuestas fijas: aquí se prueba qué se hace con lo que lee, no el modelo.
Todo es inventado.
"""
import base64
import os
import urllib.request

import pytest

from pruebas.test_entorno_pruebas import HOY, escanear, iniciar, pedir
from pruebas.test_lista_oficial import pdf_de_hojas
from validacion import aplicacion, campos, cerebro_red, taller, vision
from validacion.ejemplo import generar

pytest.importorskip('pypdf')


# ---------------------------------------------------------------- Reglas de cada tipo de campo (sin base)

def test_cada_tipo_de_campo_se_limpia_a_un_valor_util():
    assert campos.fecha('14/03/2018') == campos.fecha('14 de marzo del 2018') == campos.fecha('2018-03-14') == '2018-03-14'
    assert campos.fecha('14-III-2018') == '2018-03-14' and campos.fecha('31/02/2018') is None and campos.fecha('14-XIV-2018') is None
    assert campos.fecha('02 SEP 26', HOY) == '2026-09-02'
    assert campos.telefono('722 123 45 67') == campos.telefono('+52 722-123-4567') == campos.telefono('722 l23 4S67') == '7221234567'
    assert campos.telefono('7221 23') is None
    assert campos.correo('Mama.Luis @gmial.con') == 'mama.luis@gmail.com' and campos.correo('sin correo') is None
    assert campos.sangre('O positivo') == campos.sangre('0 +') == 'O+' and campos.sangre('AB RH negativo') == 'AB-'
    assert campos.si_no('Sí') == campos.si_no('clínicamente sano') == 'sí' and campos.si_no('No apto') == 'no'
    assert campos.si_no('Se desconoce') is None
    assert campos.lista('Penicilina y polvo; mariscos') == ['PENICILINA', 'POLVO', 'MARISCOS']
    assert campos.lista('Ninguna') == [] and campos.lista('negadas') == []
    texto, partes = campos.domicilio('C. Pino No. 5 Col. Centro, Toluca, C.P. 50000')
    assert texto.startswith('C. PINO') and partes == {'cp': '50000', 'colonia': 'CENTRO', 'calle': 'C. PINO', 'numero': '5'}
    assert campos.limpiar('nombre', 'rosa  hernández 2')[0] == 'ROSA HERNÁNDEZ'
    assert campos.limpiar('curp', 'gahj 2005 12hm crrn a')[0] is None  # Le falta un carácter.


def test_una_plantilla_nueva_propone_a_donde_va_cada_campo():
    telefono = campos.proponer('Teléfono de la mamá')
    assert (telefono['tipo'], telefono['categoria'], telefono['campo'], telefono['de']) == ('telefono', 'contacto', 'telefono', 'madre')
    assert campos.proponer('Nombre del padre')['categoria'] == 'padre'
    assert campos.proponer('Alergias')['categoria'] == 'salud' and campos.proponer('Alergias')['tipo'] == 'lista'
    emergencia = campos.proponer('Nombre de contacto de emergencia')
    assert (emergencia['categoria'], emergencia['campo']) == ('contacto', 'nombre_emergencia')
    assert campos.proponer('Talla de uniforme')['categoria'] == 'salud'  # Se propone; la persona lo cambia si no.
    revisados = campos.revisar_campos([{'etiqueta': 'Teléfono'}, {'etiqueta': 'Teléfono', 'categoria': 'nada', 'tipo': 'raro'}, {'etiqueta': ' '}])
    assert [c['clave'] for c in revisados] == ['telefono', 'telefono_1'] and revisados[1]['categoria'] == 'contacto'
    with pytest.raises(ValueError):
        campos.revisar_campos([{'etiqueta': f'Dato {i}'} for i in range(61)])
    # Lo que se le pide al modelo que ve: todos los campos, con su tipo.
    esquema = campos.esquema(revisados)
    assert esquema['required'] == ['telefono', 'telefono_1'] and 'Teléfono' in campos.pregunta('Ficha', revisados)


def test_en_una_hoja_impresa_el_valor_se_toma_junto_a_su_etiqueta():
    ficha = ['FICHA DE INSCRIPCION', 'Teléfono de la madre: 722 123 4567', 'Correo electrónico:', 'mama.luis@gmail.com',
             'Tipo de sangre: O+', 'Fecha de nacimiento 14/03/2018']
    lista = campos.revisar_campos([{'etiqueta': e} for e in ('Teléfono de la madre', 'Correo electrónico', 'Tipo de sangre',
                                                               'Fecha de nacimiento', 'Alergias')])
    leidos = campos.de_texto('\n'.join(ficha), lista, HOY)
    assert leidos == {'telefono_de_la_madre': '722 123 4567', 'correo_electronico': 'mama.luis@gmail.com', 'tipo_de_sangre': 'O+',
                      'fecha_de_nacimiento': '14/03/2018'}


def test_dos_lecturas_iguales_dan_confianza_alta_y_distintas_quedan_por_confirmar():
    lista = campos.FABRICA['acta_alumno']
    identidad = {'curp': 'GAHJ200512HMCRRNA1', 'nombres': 'JUAN', 'nombre': 'JUAN GARCIA HERNANDEZ'}
    procesos = {'curp': ('GAHJ200512HMCRRNA1', 'texto'), 'nombre_madre': ('ROSA HERNANDEZ DIAZ', 'texto'),
                'nombre_padre': ('PEDRO GARCIA RUIZ', 'texto')}
    vistos = {'nombre_madre': {'valor': 'Rosa Hernández Díaz', 'seguro': True}, 'nombre_padre': {'valor': 'PEDRO GARCIA RUIS', 'seguro': True},
              'lugar_nacimiento': {'valor': 'Toluca, Méx.', 'seguro': False}, 'curp_madre': {'valor': '', 'seguro': True}}
    salida = {r['clave']: r for r in taller.combinar(lista, procesos, vistos, identidad, HOY)}
    assert salida['curp']['confirma_lista']  # Ya está en la lista oficial: no se guarda otra vez.
    assert (salida['nombre_madre']['confianza'], salida['nombre_madre']['metodo']) == ('alta', 'texto+vision')
    assert salida['nombre_padre']['confianza'] == 'baja' and salida['nombre_padre']['detalle']['otra_lectura'] == 'PEDRO GARCIA RUIS'
    assert salida['lugar_nacimiento']['confianza'] == 'baja'  # El modelo no estaba seguro.
    assert 'curp_madre' not in salida
    # Lo que no coincide con la lista oficial no la cambia: queda por confirmar con lo que dice la lista.
    otra = {r['clave']: r for r in taller.combinar(lista, {'nombres': ('JUANA', 'texto')}, {}, identidad, HOY)}
    assert otra['nombres']['confianza'] == 'baja' and otra['nombres']['detalle']['en_lista'] == 'JUAN'


def test_los_procesos_fijos_leen_el_acta_la_ine_y_el_certificado():
    curp = generar.curp('GAHJ200512HMCRRNA')
    acta = generar.acta('JUAN', 'GARCIA', 'HERNANDEZ', '12/05/2020', 'HOMBRE', curp, 'PEDRO GARCIA RUIZ', 'ROSA HERNANDEZ DIAZ')
    leidos = taller.de_procesos('acta_alumno', acta, [], HOY)
    assert leidos['curp'][0] == curp and leidos['nombre_madre'][0] == 'ROSA HERNANDEZ DIAZ' and leidos['nombre_padre'][0] == 'PEDRO GARCIA RUIZ'
    ine = taller.de_procesos('ine_tutor', generar.ine('RAMOS', 'SOTO', 'MARIA ELENA', 'C. PINO NO. 5 COL. CENTRO TOLUCA'), [], HOY)
    assert ine == {'nombre_tutor': ('MARIA ELENA RAMOS SOTO', 'texto'), 'domicilio_ine': ('C. PINO NO. 5 COL. CENTRO TOLUCA', 'texto'),
                   'vigencia_ine': ('2024-2034', 'texto')}
    medico = taller.de_procesos('certificado_medico', generar.medico('JUAN GARCIA HERNANDEZ'), [], HOY)
    assert medico == {'apto': ('sí', 'texto'), 'fecha_certificado': ('2026-09-02', 'texto')}


# ---------------------------------------------------------------- En la base de la PC 4

if os.environ.get('SIDP_PRUEBA_BASE'):
    pytest.importorskip('pg8000')
    from pruebas.test_base_cerebro import CURP_JUAN, alumnos, base, id_de  # noqa: F401  (base es un fixture)
else:
    CURP_JUAN = generar.curp('GAHJ200512HMCRRNA')

    @pytest.fixture
    def base():
        pytest.skip('sin PostgreSQL de prueba (SIDP_PRUEBA_BASE)')
con_base = pytest.mark.skipif(not os.environ.get('SIDP_PRUEBA_BASE'), reason='sin PostgreSQL de prueba (SIDP_PRUEBA_BASE)')

ACTA = generar.acta('JUAN', 'GARCIA', 'HERNANDEZ', '12/05/2020', 'HOMBRE', CURP_JUAN, 'PEDRO GARCIA RUIZ', 'ROSA HERNANDEZ DIAZ')
# Lo que "ve" el modelo en cada documento (con letra a mano: un apellido mal leído, un peso dudoso).
VISTO = {
    'Acta de nacimiento': {'lugar_nacimiento': ('Toluca, México', True), 'nombre_madre': ('Rosa Hernández Díaz', True),
                           'nombre_padre': ('PEDRO GARCIA RUIS', True)},
    'Certificado médico': {'tipo_sangre': ('O positivo', True), 'alergias': ('Penicilina y polvo', True), 'padecimientos': ('ninguno', True),
                           'peso': ('22,5 kg', False), 'apto': ('Sí', True)},
}


@pytest.fixture
def modelo_que_ve(monkeypatch):
    preguntas = []

    def preguntar(hojas, pregunta, esquema=None, nombre_modelo=None, url=None, espera=900):
        preguntas.append(pregunta)
        if pregunta == campos.PROPONER:
            return {'campos': ['Nombre del alumno', 'Teléfono de la madre', 'Alergias', 'Teléfono de la madre']}, 2.0
        documento = next(v for k, v in VISTO.items() if k in pregunta)
        return {c: {'valor': documento.get(c, ('', True))[0], 'seguro': documento.get(c, ('', True))[1]} for c in esquema['properties']}, 1.5

    monkeypatch.setattr(vision, 'elegir', lambda url=None, pedido=None: 'modelo-de-prueba')
    monkeypatch.setattr(vision, 'paginas', lambda contenido, nombre='': [b'hoja'])
    monkeypatch.setattr(vision, 'preguntar', preguntar)
    return preguntas


def pedido_de_juan():
    return {'curp': CURP_JUAN, 'expediente': '0001', 'documentos': [
        {'archivo': 'acta_alumno_1.pdf', 'tipo': 'acta_alumno', 'nombre': 'Acta de nacimiento del alumno',
         'contenido': base64.b64encode(pdf_de_hojas([ACTA.splitlines()])).decode()},
        {'archivo': 'certificado_medico_1.pdf', 'tipo': 'certificado_medico', 'nombre': 'Certificado médico',
         'contenido': base64.b64encode(pdf_de_hojas([generar.medico('JUAN GARCIA HERNANDEZ').splitlines()])).decode()},
    ]}


def datos_de(base, curp=CURP_JUAN):
    return {(categoria, f['campo'], f['valor']): (f['confianza'], f['estado'])
            for categoria, fs in base.expediente_alumno(curp)['datos'].items() for f in fs}


@con_base
def test_el_taller_saca_los_datos_y_los_guarda_por_categoria(base, modelo_que_ve, tmp_path):
    from validacion import base_cerebro
    base.cargar(base_cerebro.ciclo_de(HOY), alumnos())
    trabajos = taller.Taller(base, tmp_path / 'trabajos', hoy=HOY)
    with pytest.raises(LookupError):
        trabajos.encargar({**pedido_de_juan(), 'curp': generar.curp('XEXX010101HNEXXXA')})
    trabajo = trabajos.encargar(pedido_de_juan())
    assert sorted(p.name for p in (tmp_path / 'trabajos' / str(trabajo)).iterdir()) == ['acta_alumno_1.pdf', 'certificado_medico_1.pdf']
    cuenta = trabajos.una_vez()
    assert {k: cuenta[k] for k in ('esperados', 'alta', 'media', 'baja', 'vacios', 'utiles')} == \
        {'esperados': 21, 'alta': 7, 'media': 5, 'baja': 2, 'vacios': 7, 'utiles': 57}
    assert not (tmp_path / 'trabajos' / str(trabajo)).exists()  # Los archivos del trabajo ya no hacen falta.
    assert trabajos.una_vez() is None
    assert datos_de(base) == {
        ('alumno', 'lugar_nacimiento', 'TOLUCA, MÉXICO'): ('media', 'vigente'),
        ('madre', 'nombre', 'ROSA HERNANDEZ DIAZ'): ('alta', 'vigente'),
        ('padre', 'nombre', 'PEDRO GARCIA RUIZ'): ('baja', 'por_confirmar'),
        ('salud', 'tipo_sangre', 'O+'): ('media', 'vigente'),
        ('salud', 'alergia', 'PENICILINA'): ('media', 'vigente'),
        ('salud', 'alergia', 'POLVO'): ('media', 'vigente'),
        ('salud', 'peso', '22.5'): ('baja', 'por_confirmar'),
        ('salud', 'apto', 'sí'): ('alta', 'vigente'),
        ('salud', 'fecha_certificado', '2026-09-02'): ('media', 'vigente'),
    }
    # El nombre, la CURP y la fecha ya estaban en la lista oficial: el acta los confirma y no se repiten.
    assert not any(c == 'alumno' and k in ('curp', 'nombres', 'fecha_nacimiento') for c, k, _ in datos_de(base))
    estado = trabajos.estado()
    assert estado['trabajos'] == {'hecho': 1} and estado['porcentaje_util'] == 57 and estado['por_confirmar'] == 2
    # Solo números en el resumen (nada de nombres).
    assert set(base._uno('SELECT resumen FROM sidp.trabajo WHERE id = %s', (trabajo,))) == \
        {'esperados', 'alta', 'media', 'baja', 'vacios', 'segundos_vision', 'modelo', 'utiles'}


@con_base
def test_una_persona_confirma_corrige_o_agrega_y_la_lectura_no_pisa_lo_confirmado(base, modelo_que_ve, tmp_path):
    from validacion import base_cerebro
    base.cargar(base_cerebro.ciclo_de(HOY), alumnos())
    trabajos = taller.Taller(base, tmp_path / 'trabajos', hoy=HOY)
    trabajos.encargar(pedido_de_juan())
    trabajos.una_vez()
    dudosos = {d['campo']: d for d in base.por_confirmar()}
    assert set(dudosos) == {'nombre', 'peso'} and dudosos['nombre']['curp'] == CURP_JUAN and dudosos['nombre']['grado'] == 1
    base.confirmar_dato(dudosos['nombre']['id'], '', 'secretaria')  # Estaba bien.
    base.confirmar_dato(dudosos['peso']['id'], '23.5', 'secretaria')  # Lo corrige viendo la hoja.
    base.agregar_dato(CURP_JUAN, 'contacto', 'Teléfono', '7221234567', 'secretaria', {'de': 'madre'})
    base.agregar_dato(CURP_JUAN, 'contacto', 'telefono', '7227654321', 'secretaria', {'de': 'padre'})
    datos = datos_de(base)
    assert datos[('padre', 'nombre', 'PEDRO GARCIA RUIZ')] == ('confirmado', 'vigente')
    assert datos[('salud', 'peso', '23.5')] == ('confirmado', 'vigente') and ('salud', 'peso', '22.5') not in datos
    assert datos[('contacto', 'telefono', '7221234567')] == datos[('contacto', 'telefono', '7227654321')] == ('confirmado', 'vigente')
    assert not base.por_confirmar()
    # Se vuelve a escanear: lo confirmado no cambia y la lectura distinta queda por confirmar.
    VISTO['Certificado médico']['tipo_sangre'] = ('A positivo', True)
    base.confirmar_dato(base._uno("SELECT id FROM sidp.dato WHERE campo = 'tipo_sangre' AND estado = 'vigente'"), '', 'secretaria')
    try:
        trabajos.encargar(pedido_de_juan())
        trabajos.una_vez()
    finally:
        VISTO['Certificado médico']['tipo_sangre'] = ('O positivo', True)
    datos = datos_de(base)
    assert datos[('salud', 'tipo_sangre', 'O+')] == ('confirmado', 'vigente')
    assert datos[('salud', 'tipo_sangre', 'A+')] == ('media', 'por_confirmar')
    assert datos[('salud', 'peso', '23.5')] == ('confirmado', 'vigente')
    assert ('salud', 'peso', '22.5') not in datos  # Ya se corrigió una vez: no se vuelve a preguntar.
    with pytest.raises(Exception):
        base._consulta('DELETE FROM sidp.dato')  # En la base no se borra nada a mano.


@con_base
def test_baja_y_borrado_de_un_alumno(base):
    from validacion import base_cerebro
    base.cargar(base_cerebro.ciclo_de(HOY), alumnos())
    otro = alumnos()[1]['curp']
    base.agregar_dato(otro, 'salud', 'alergia', 'POLVO', 'secretaria')
    with pytest.raises(base_cerebro.ErrorBase):
        base.dar_baja_alumno(otro, ' ', 'secretaria')
    base.dar_baja_alumno(otro, 'Cambio de domicilio', 'secretaria')
    assert base._uno('SELECT estado FROM sidp.alumno WHERE curp = %s', (otro,)) == 'baja'
    assert otro not in {a['curp'] for g in base.alumnos()['grupos'] for a in g['filas']}
    assert datos_de(base, otro)  # Su expediente se queda.
    # Borrar: se quita de todas las tablas y la bitácora dice quién, cuándo y por qué.
    with pytest.raises(Exception):
        base.borrar_alumno(CURP_JUAN, '', 'directora')
    base.agregar_dato(CURP_JUAN, 'contacto', 'telefono', '7221234567', 'secretaria')
    alumno = id_de(base, CURP_JUAN)
    base.borrar_alumno(CURP_JUAN, 'Se cargó dos veces', 'directora')
    assert base._uno('SELECT count(*) FROM sidp.alumno WHERE curp = %s', (CURP_JUAN,)) == 0
    assert base._uno('SELECT count(*) FROM sidp.dato WHERE alumno_id = %s', (alumno,)) == 0
    assert base._consulta("SELECT actor, despues->>'motivo' FROM sidp.bitacora WHERE accion = 'borrar'") == [['directora', 'Se cargó dos veces']]
    with pytest.raises(base_cerebro.ErrorBase):
        base.expediente_alumno(CURP_JUAN)
    with pytest.raises(Exception):  # Fuera de borrar_alumno sigue sin poderse borrar nada.
        base._consulta('DELETE FROM sidp.alumno WHERE curp = %s', (otro,))


@con_base
def test_del_escaneo_al_expediente_del_alumno_en_el_panel(base, modelo_que_ve, tmp_path):
    """El servidor guarda los PDF por alumno, la PC 4 saca los datos y el panel muestra todo junto."""
    trabajos = taller.Taller(base, tmp_path / 'trabajos', hoy=HOY)
    cerebro = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1', base=base,
                                         taller=trabajos)
    url_cerebro = iniciar(cerebro)
    app = aplicacion.Aplicacion(tmp_path / 'sistema', HOY, puerto=0, expedientes=tmp_path / 'Expedientes')
    servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    url = iniciar(servidor)
    try:
        assert app.configurar(url_cerebro, 'clave-de-prueba') is None
        token = {'X-SIDP-Token': app.token}
        filas = [{k: a[k] for k in ('curp', 'primer_apellido', 'segundo_apellido', 'nombres')} for a in alumnos()]
        assert pedir(url, '/api/listas/guardar', {'grado': 1, 'letra': 'A', 'filas': filas}, token)[0] == 200
        leido = escanear(url, app, pdf_de_hojas([ACTA.splitlines(), generar.medico('JUAN GARCIA HERNANDEZ').splitlines()]))[1]
        paginas = {p['archivo']: p['tipo'] for p in leido['paginas']}
        assert sorted(paginas.values()) == ['acta_alumno', 'certificado_medico']
        codigo, guardado = pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': leido['propuesta']['alumno']}, token)
        assert codigo == 200, guardado
        # El servidor ya le encargó el expediente a la PC 4: no quedó nada pendiente de mandar.
        estado = pedir(url, '/api/trabajos', cabeceras=token)[1]
        assert estado['trabajos'] == {'pendiente': 1} and estado['pendientes_de_enviar'] == 0, estado
        assert trabajos.una_vez()['esperados'] == 21
        estado = pedir(url, '/api/trabajos', cabeceras=token)[1]
        assert estado['trabajos'] == {'hecho': 1} and estado['porcentaje_util'] == 57
        codigo, expediente = pedir(url, f'/api/alumno?curp={CURP_JUAN}', cabeceras=token)
        assert codigo == 200, expediente
        assert expediente['alumno']['nombres'] == 'JUAN' and expediente['alumno']['grado'] == 1
        assert [d['valor'] for d in expediente['datos']['madre']] == ['ROSA HERNANDEZ DIAZ']
        assert {d['valor'] for d in expediente['datos']['salud'] if d['campo'] == 'alergia'} == {'PENICILINA', 'POLVO'}
        assert sorted(p['nombre'] for p in expediente['pdf']) == ['Acta de nacimiento del alumno', 'Certificado médico']
        # El PDF se abre en la ventana; nada fuera de la carpeta de expedientes.
        ruta = expediente['pdf'][0]['ruta']
        solicitud = urllib.request.Request(f'{url}/api/pdf?ruta={urllib.request.quote(ruta)}', headers=token)
        with urllib.request.urlopen(solicitud) as respuesta:
            assert respuesta.headers['Content-Type'] == 'application/pdf' and respuesta.read().startswith(b'%PDF')
        assert pedir(url, '/api/pdf?ruta=../sistema/plataforma_prueba.db', cabeceras=token)[0] == 400
        # Lo dudoso se confirma desde el panel.
        dudosos = pedir(url, '/api/por_confirmar', cabeceras=token)[1]['datos']
        assert {d['campo'] for d in dudosos} == {'nombre', 'peso'}
        assert pedir(url, '/api/dato/confirmar', {'id': dudosos[0]['id'], 'valor': ''}, token)[0] == 200
        assert pedir(url, '/api/dato/agregar', {'curp': CURP_JUAN, 'categoria': 'contacto', 'campo': 'telefono', 'valor': '7221234567',
                                                'de': 'madre'}, token)[0] == 200
        assert len(pedir(url, '/api/por_confirmar', cabeceras=token)[1]['datos']) == 1
        # Baja: necesita motivo. Borrar: además hay que escribir BORRAR.
        assert pedir(url, '/api/alumno/baja', {'curp': CURP_JUAN}, token)[0] == 400
        assert pedir(url, '/api/alumno/borrar', {'curp': CURP_JUAN, 'motivo': 'error', 'confirmar': 'si'}, token)[0] == 400
        codigo, respuesta = pedir(url, '/api/alumno/baja', {'curp': CURP_JUAN, 'motivo': 'Se mudó'}, token)
        assert codigo == 200, respuesta
        assert base._uno('SELECT estado FROM sidp.alumno WHERE curp = %s', (CURP_JUAN,)) == 'baja'
        assert app.bandeja.registro.db.execute('SELECT estado FROM alumno WHERE curp = ?', (CURP_JUAN,)).fetchone() == ('baja',)
    finally:
        servidor.shutdown()
        cerebro.shutdown()


@con_base
def test_lo_escaneado_sin_la_pc_4_se_manda_cuando_vuelve(base, modelo_que_ve, tmp_path):
    trabajos = taller.Taller(base, tmp_path / 'trabajos', hoy=HOY)
    app = aplicacion.Aplicacion(tmp_path / 'sistema', HOY, puerto=0, expedientes=tmp_path / 'Expedientes')
    servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    url = iniciar(servidor)
    cerebro = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1', base=base,
                                         taller=trabajos)
    url_cerebro = iniciar(cerebro)
    try:
        token = {'X-SIDP-Token': app.token}
        filas = [{k: a[k] for k in ('curp', 'primer_apellido', 'segundo_apellido', 'nombres')} for a in alumnos()]
        pedir(url, '/api/listas/guardar', {'grado': 1, 'letra': 'A', 'filas': filas}, token)
        leido = escanear(url, app, pdf_de_hojas([ACTA.splitlines()]))[1]
        assert pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': leido['propuesta']['alumno']}, token)[0] == 200
        assert [p.name for p in (tmp_path / 'sistema' / 'pendientes_pc4').iterdir()] == ['0001.json']
        # La PC 4 vuelve; ella todavía no tiene la lista de alumnos (409) y el servidor se la manda primero.
        assert app.configurar(url_cerebro, 'clave-de-prueba') is None
        assert app.bandeja.enviar_pendientes() == 1
        assert not list((tmp_path / 'sistema' / 'pendientes_pc4').iterdir())
        assert trabajos.una_vez()['esperados'] == 10
    finally:
        servidor.shutdown()
        cerebro.shutdown()


@con_base
def test_la_ia_propone_los_campos_de_una_plantilla_nueva(base, modelo_que_ve, tmp_path):
    cerebro = cerebro_red.crear_servidor('clave-de-prueba', 0, url='http://127.0.0.1:9/api/chat', anfitrion='127.0.0.1', base=base)
    url_cerebro = iniciar(cerebro)
    app = aplicacion.Aplicacion(tmp_path / 'sistema', HOY, puerto=0)
    servidor = aplicacion.crear_servidor(app, '127.0.0.1')
    url = iniciar(servidor)
    try:
        assert app.configurar(url_cerebro, 'clave-de-prueba') is None
        muestra = pdf_de_hojas([['FICHA DE INSCRIPCION']])
        cuerpo = (b'--limite\r\nContent-Disposition: form-data; name="archivo"; filename="ficha.pdf"\r\n'
                  b'Content-Type: application/pdf\r\n\r\n' + muestra + b'\r\n--limite--\r\n')
        codigo, respuesta = pedir(url, '/api/plantillas/campos', cuerpo, {'X-SIDP-Token': app.token}, tipo='multipart/form-data; boundary=limite')
        assert codigo == 200, respuesta
        assert [(c['etiqueta'], c['categoria'], c['campo']) for c in respuesta['campos']] == [
            ('Nombre del alumno', 'alumno', 'nombre'), ('Teléfono de la madre', 'contacto', 'telefono'), ('Alergias', 'salud', 'alergia')]
        # Sin taller (la PC 4 no tiene base o no arrancó) no se aceptan trabajos.
        assert pedir(url_cerebro, '/trabajo', pedido_de_juan(), {'X-SIDP-Clave': 'clave-de-prueba'})[0] == 503
    finally:
        servidor.shutdown()
        cerebro.shutdown()
