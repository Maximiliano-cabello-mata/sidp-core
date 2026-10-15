"""La base de datos de la PC 4 (PostgreSQL, esquema sidp): alumnos, documentos, procesos y defensas.

Necesita un PostgreSQL de prueba: SIDP_PRUEBA_BASE=postgresql://usuario:contraseña@127.0.0.1:5432/base
(en CI lo levanta el trabajo "base_cerebro"). Sin él, estas pruebas se saltan. Todo es inventado.
Cada prueba borra el esquema de prueba y lo crea de nuevo; en la base real nada se puede borrar.
"""
import json
import os
import urllib.error
import urllib.request

import pytest

from pruebas.test_entorno_pruebas import HOY, escanear, iniciar, pedir
from pruebas.test_lista_oficial import PRIMERO, SEGUNDO, hoja, pdf_de_hojas
from validacion import aplicacion, base_cerebro, cerebro_red, comparador
from validacion.ejemplo import generar

pytest.importorskip('pg8000')
pytest.importorskip('pypdf')
if not os.environ.get('SIDP_PRUEBA_BASE'):
    pytest.skip('sin PostgreSQL de prueba (SIDP_PRUEBA_BASE)', allow_module_level=True)

CICLO = '2026-2027'
CURP_JUAN = generar.curp('GAHJ200512HMCRRNA')


@pytest.fixture
def base():
    base = base_cerebro.BaseCerebro(os.environ['SIDP_PRUEBA_BASE'])
    base._consulta('DROP SCHEMA IF EXISTS sidp CASCADE; DROP TABLE IF EXISTS public.padron_alumno_v1, public.lectura_v1, '
                   'public.padron_alumno, public.lectura')
    base.preparar()
    base.preparar()  # Correrlo dos veces no rompe nada.
    return base


def alumnos(lista=PRIMERO, grado=1):
    return [{'curp': generar.curp(c), 'primer_apellido': p, 'segundo_apellido': s, 'nombres': n, 'grado': grado, 'letra': 'A'}
            for p, s, n, c in lista]


def id_de(base, curp):
    return base._uno('SELECT id FROM sidp.alumno WHERE curp = %s', (curp,))


def test_la_curp_se_revisa_igual_que_en_python(base):
    for prefijo in ('GAHJ200512HMCRRNA', 'LOMA200301MMCPRNA', 'PERM201107HMCRZTA', 'CUDR190716MMCRZGA', 'XEXX010101HNEXXXA'):
        curp = generar.curp(prefijo)
        assert base._uno('SELECT sidp.curp_digito(%s)', (curp,)) == comparador.digito_curp(curp) == curp[17]
        assert base._uno('SELECT sidp.curp_valida(%s)', (curp,)) is True
        assert str(base._uno('SELECT sidp.curp_fecha(%s)', (curp,))) == comparador.desglose_curp(curp)['fecha']
    malo = CURP_JUAN[:17] + str((int(CURP_JUAN[17]) + 1) % 10)
    assert base._uno('SELECT sidp.curp_valida(%s)', (malo,)) is False
    assert base._uno('SELECT sidp.curp_fecha(%s)', ('GAHJ201332HMCRRNA1',)) is None  # Mes 13.
    assert base._uno('SELECT sidp.normalizar(%s)', ('Hernández  Ruíz, ΜΑRÍA',)) == 'HERNANDEZ RUIZ MARIA'
    assert base._uno('SELECT sidp.grado_esperado(%s, %s)', ('2020-05-12', CICLO)) == 1
    assert base._uno('SELECT sidp.ciclo_de(%s)', ('2027-03-01',)) == CICLO


def test_los_alumnos_se_cargan_sin_duplicarse_y_nadie_se_da_de_baja_solo(base):
    resultado = base.cargar(CICLO, alumnos() + alumnos(SEGUNDO, 2))
    assert (resultado['nuevos'], resultado['inscritos'], resultado['rechazados']) == (7, 7, [])
    otra_vez = base.cargar(CICLO, alumnos())
    assert (otra_vez['nuevos'], otra_vez['actualizados'], otra_vez['inscritos'], otra_vez['no_vinieron']) == (0, 0, 0, 4)
    assert base.resumen()['alumnos'] == 7  # Los de 2° no se dieron de baja: solo se avisa.
    # La fecha, el sexo y la entidad salen de la CURP.
    assert base._consulta('SELECT fecha_nacimiento::text, sexo, entidad_nacimiento FROM sidp.alumno WHERE curp = %s',
                          (CURP_JUAN,)) == [['2020-05-12', 'H', 'MC']]
    # Un cambio de grupo y una corrección de nombre se guardan con su versión y su bitácora.
    cambio = [{**alumnos()[0], 'letra': 'B', 'segundo_apellido': 'HERNANDEZ LOPEZ'}]
    resultado = base.cargar(CICLO, cambio, actor='maestra')
    assert (resultado['actualizados'], resultado['cambios_de_grupo']) == (1, 1)
    alumno = id_de(base, CURP_JUAN)
    assert base._uno('SELECT version FROM sidp.alumno WHERE id = %s', (alumno,)) == 2
    assert base._consulta("SELECT actor, accion FROM sidp.bitacora WHERE tabla = 'alumno' AND registro = %s ORDER BY secuencia",
                          (str(alumno),)) == [['SIDP-Validador', 'insert'], ['maestra', 'update']]
    # Renglones malos se rechazan con su motivo, sin detener a los demás.
    malos = base.cargar(CICLO, [{'nombres': 'X'}, {'nombres': 'ANA', 'primer_apellido': 'RUIZ', 'curp': 'ABC'}])
    assert [r['motivo'] for r in malos['rechazados']] == ['falta el nombre o el primer apellido', 'la CURP no tiene la forma correcta']


def test_nada_se_borra_y_la_bitacora_no_se_cambia(base):
    base.cargar(CICLO, alumnos())
    for sentencia in ('DELETE FROM sidp.alumno', 'TRUNCATE sidp.alumno CASCADE', 'DELETE FROM sidp.inscripcion',
                      'UPDATE sidp.bitacora SET actor = %s', 'DELETE FROM sidp.bitacora', 'TRUNCATE sidp.bitacora'):
        with pytest.raises(Exception):
            base._consulta(sentencia, ('otro',) if '%s' in sentencia else ())
    assert base.resumen()['alumnos'] == 3
    # Un cambio que no cambia nada no sube la versión ni ensucia la bitácora.
    antes = base.resumen()['bitacora']
    base._consulta("UPDATE sidp.alumno SET nombres = nombres")
    assert base.resumen()['bitacora'] == antes and base._uno('SELECT max(version) FROM sidp.alumno') == 1


def test_documentos_faltantes_revision_y_vencimiento(base):
    base.cargar(CICLO, alumnos())
    alumno = id_de(base, CURP_JUAN)
    faltan = base._uno('SELECT faltan FROM sidp.v_faltantes WHERE alumno_id = %s', (alumno,))
    assert 'acta_nacimiento' in faltan and 'boleta_anterior' not in faltan  # En 1° no se pide boleta.
    primero = base._uno('SELECT sidp.registrar_documento(%s, %s, %s, %s)', (alumno, 'acta_nacimiento', 'a' * 64, 'escaneo'))
    segundo = base._uno('SELECT sidp.registrar_documento(%s, %s, %s, %s)', (alumno, 'acta_nacimiento', 'b' * 64, 'escaneo'))
    assert base._consulta('SELECT id, estado, reemplaza_a FROM sidp.documento ORDER BY id') == [
        [primero, 'reemplazado', None], [segundo, 'recibido', primero]]
    with pytest.raises(Exception):  # Rechazar pide motivo.
        base._consulta('SELECT sidp.revisar_documento(%s, %s, %s)', (segundo, 'rechazado', 'secretaria'))
    with pytest.raises(Exception):  # Solo una persona revisa.
        base._consulta('SELECT sidp.revisar_documento(%s, %s, %s)', (segundo, 'validado', 'cerebro'))
    base._consulta('SELECT sidp.revisar_documento(%s, %s, %s)', (segundo, 'validado', 'secretaria'))
    assert 'acta_nacimiento' not in base._uno('SELECT faltan FROM sidp.v_faltantes WHERE alumno_id = %s', (alumno,))
    comprobante = base._uno('SELECT sidp.registrar_documento(%s, %s, %s, %s, 1, %s)',
                            (alumno, 'comprobante_domicilio', 'c' * 64, 'foto', '2026-06-01'))
    assert base._uno('SELECT sidp.vencer_documentos(%s)', ('2026-10-15',)) == 1
    assert base._uno('SELECT estado FROM sidp.documento WHERE id = %s', (comprobante,)) == 'vencido'


def test_alertas_911_y_renapo(base):
    grande = generar.curp('ROVL170905MMCJGCA')  # Nacida en 2017: en 1° tiene extraedad.
    base.cargar(CICLO, alumnos() + [{'curp': grande, 'primer_apellido': 'ROJAS', 'segundo_apellido': 'VEGA', 'nombres': 'LUCIA',
                                     'grado': 1, 'letra': 'A'},
                                    {'primer_apellido': 'GARCIA', 'segundo_apellido': 'HERNANDES', 'nombres': 'JUAN',
                                     'grado': 1, 'letra': 'A'}])  # Sin CURP y casi igual a Juan: posible duplicado.
    alertas = {(tipo, alumno) for tipo, alumno in base._consulta('SELECT tipo, alumno_id FROM sidp.v_alertas')}
    assert ('extraedad', id_de(base, grande)) in alertas
    assert ('posible_duplicado', id_de(base, CURP_JUAN)) in alertas
    assert sum(1 for tipo, _ in alertas if tipo == 'sin_curp') == 1
    assert base._uno('SELECT sidp.marcar_renapo(%s, %s, %s)', (CURP_JUAN, 'validada', 'secretaria')) is True
    assert ('renapo_pendiente', id_de(base, CURP_JUAN)) not in {tuple(f) for f in base._consulta('SELECT tipo, alumno_id FROM sidp.v_alertas')}
    informe = base.informe()
    assert sum(f['alumnos'] for f in informe['matricula_911']) == 5
    assert {(f['sexo'], f['edad']) for f in informe['matricula_911'] if f['alumnos']} >= {('H', 6), ('M', 9)}
    assert informe['resumen']['grupos'][0]['extraedad'] == 1


def test_baja_y_cambio_de_grupo_dejan_huella(base):
    base.cargar(CICLO, alumnos())
    alumno = id_de(base, CURP_JUAN)
    base._consulta('SELECT sidp.cambiar_grupo(%s, %s, %s, %s, %s)', (alumno, CICLO, 1, 'C', 'direccion'))
    assert base._consulta('SELECT grado, letra FROM sidp.v_alumnos WHERE id = %s', (alumno,)) == [[1, 'C']]
    with pytest.raises(Exception):
        base._consulta('SELECT sidp.dar_baja(%s, %s, %s, %s)', (alumno, CICLO, ' ', 'direccion'))
    base._consulta('SELECT sidp.dar_baja(%s, %s, %s, %s)', (alumno, CICLO, 'cambio de domicilio', 'direccion'))
    assert base.resumen()['alumnos'] == 2
    assert base._uno("SELECT count(*) FROM sidp.bitacora WHERE tabla = 'inscripcion' AND actor = 'direccion'") == 2


def test_la_lista_oficial_se_carga_una_sola_vez(base, capsys):
    pdf = pdf_de_hojas([['INSTRUCCIONES'], hoja(PRIMERO), hoja(SEGUNDO)])
    resultado = base.importar_lista(pdf, CICLO)
    assert (resultado['nuevos'], resultado['ya_importado']) == (7, False)
    assert resultado['grupos_leidos'] == [{'grupo': '1° A', 'alumnos': 3, 'dudosos': 0}, {'grupo': '2° A', 'alumnos': 4, 'dudosos': 0}]
    assert base.importar_lista(pdf, CICLO)['ya_importado'] is True
    assert [g['grupo'] for g in base.resumen()['grupos']] == ['1° A', '2° A']
    # Lo que imprime para el informe del agente son solo números: ningún nombre ni CURP.
    os.environ['SIDP_BASE'] = os.environ['SIDP_PRUEBA_BASE']
    try:
        assert base_cerebro.main(['informe', '--ciclo', CICLO]) == 0
    finally:
        del os.environ['SIDP_BASE']
    salida = capsys.readouterr().out
    assert '7 alumnos inscritos' in salida and '1° A: 3 alumnos' in salida
    assert not any(texto in salida for texto in ('GARCIA', 'JUAN', CURP_JUAN[:10]))


def test_la_lista_revisada_en_csv_tambien_se_carga(base):
    renglones = ['Grado,Grupo,Primer apellido,Segundo apellido,Nombre(s),CURP']
    renglones += [f'1,A,{p},{s},{n},{generar.curp(c)}' for p, s, n, c in PRIMERO]
    resultado = base.importar_lista(('\ufeff' + '\n'.join(renglones)).encode('utf-8'), CICLO, es_csv=True)
    assert (resultado['nuevos'], resultado['grupos_leidos']) == (3, [{'grupo': '1° A', 'alumnos': 3, 'dudosos': 0}])


def test_la_version_1_pasa_a_la_2_sin_perder_alumnos(base):
    base._consulta('DROP SCHEMA sidp CASCADE')
    base._consulta('CREATE TABLE public.padron_alumno (curp char(18) PRIMARY KEY, primer_apellido text, segundo_apellido text, '
                   'nombres text, nombre_completo text, grado smallint, letra text, ciclo text, activo boolean)')
    base._consulta("INSERT INTO public.padron_alumno VALUES (%s, 'GARCIA', 'HERNANDEZ', 'JUAN', 'JUAN GARCIA HERNANDEZ', 1, 'A', %s, true)",
                   (CURP_JUAN, CICLO))
    base.preparar()
    assert base.resumen()['alumnos'] == 1
    assert base._uno("SELECT to_regclass('public.padron_alumno_v1') IS NOT NULL")


def test_una_curp_o_un_nombre_mal_leidos_encuentran_al_alumno(base):
    base.cargar(CICLO, alumnos())
    leida = CURP_JUAN[:13] + ('P' if CURP_JUAN[13] != 'P' else 'T') + CURP_JUAN[14:]
    sugerencias = base.sugerir(f'CURP: {leida}')
    assert [(s['por'], s['curp'], s['distancia'], s['nombres'], s['grado']) for s in sugerencias] == [('curp', CURP_JUAN, 1, 'JUAN', 1)]
    for texto in ('Nombre: JUAN GARCIA HERNANDES', 'HERNÁNDEZ GARCÍA JUAN', 'Registrado:\nLopez Martinez Ana Sofia'):
        primero = base.sugerir(texto)[0]
        assert primero['por'] == 'nombre' and primero['parecido'] >= base_cerebro.NOMBRE_MINIMO, texto
    assert base.sugerir('PEDRO RAMIREZ OCHOA') == []
    assert base._consulta('SELECT por, curp FROM sidp.buscar(%s)', (leida,)) == [['curp', CURP_JUAN]]
    assert base._consulta('SELECT por FROM sidp.buscar(%s)', ('garcia hernandez',))[0] == ['nombre']


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
        # El acta escaneada trae la CURP con una letra mal leída: el cerebro propone la de la base.
        leida = CURP_JUAN[:13] + ('P' if CURP_JUAN[13] != 'P' else 'T') + CURP_JUAN[14:]
        acta = generar.acta('JUAN', 'GARCIA', 'HERNANDEZ', '12/05/2020', 'HOMBRE', leida, 'PEDRO GARCIA RUIZ', 'ROSA HERNANDEZ DIAZ')
        codigo, leido = escanear(url, app, pdf_de_hojas([acta.splitlines()]))
        assert codigo == 200, leido
        propuesta = leido['propuesta']
        assert propuesta['alumno']['curp'] == CURP_JUAN, propuesta
        assert 'compárala con el acta' in propuesta['avisos'][0]
        assert leido['parecidos'] and leido['parecidos'][0]['curp'] == CURP_JUAN  # Y se liga al alumno de la lista.
        assert base._consulta('SELECT curp_leida, alumno_id, distancia FROM sidp.lectura') == [[leida, id_de(base, CURP_JUAN), 1]]
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
