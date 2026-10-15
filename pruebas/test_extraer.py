"""Datos que se proponen de documentos escaneados (expedientes ya revisados en papel)."""
from validacion import extraer
from validacion.ejemplo import generar

CURP = generar.curp('HERL180314HMCRMSA')
ACTA = generar.acta('LUIS', 'HERNANDEZ', 'RAMOS', '14/03/2018', 'HOMBRE', CURP, 'JUAN PEREZ LOPEZ', 'MARIA ELENA RAMOS SOTO')


def test_la_curp_se_corrige_si_el_ocr_confundio_letras_y_numeros():
    assert extraer.curps('CURP: ' + CURP[:4] + CURP[4:10].replace('1', 'I').replace('0', 'O') + CURP[10:]) == [CURP]
    assert extraer.curps('CURP: ' + CURP[:-1] + str((int(CURP[-1]) + 1) % 10)) == []  # El dígito no cuadra.


def test_una_letra_de_mas_solo_se_quita_si_queda_una_curp_del_texto():
    assert extraer.curps(f'LUIS HERNANDEZ RAMOS\nClave: {CURP[:17]}Z{CURP[17]}') == [CURP]


def test_el_nombre_se_encuentra_con_las_letras_de_la_curp():
    assert extraer.nombre_por_curp(ACTA, CURP) == {'nombres': 'LUIS', 'primer_apellido': 'HERNANDEZ', 'segundo_apellido': 'RAMOS'}
    # Una palabra del renglón anterior ("registrada") no se toma como nombre.
    curp = generar.curp('TOAR180716MMCRRGA')
    texto = 'Datos de la persona registrada\nNombre(s): REGINA  Primer apellido: TORRES  Segundo apellido: ARIAS'
    assert extraer.nombre_por_curp(texto, curp)['nombres'] == 'REGINA'


def test_del_acta_y_la_ine_salen_el_alumno_y_la_madre():
    paginas = extraer.agrupar([{'texto': ACTA}, {'texto': generar.ine('RAMOS', 'SOTO', 'MARIA ELENA', 'C. PINO 5')}])
    assert [p['tipo'] for p in paginas] == ['acta_alumno', 'ine_tutor']
    propuesta = extraer.proponer(paginas)
    assert propuesta['alumno']['curp'] == CURP and propuesta['alumno']['sexo'] == 'H'
    assert propuesta['tutor']['nombres'] == 'MARIA ELENA' and propuesta['tutor']['parentesco'] == 'madre'


def test_si_la_ine_es_de_otra_persona_se_lee_su_nombre_y_se_avisa():
    ine = 'INSTITUTO NACIONAL ELECTORAL\nCREDENCIAL PARA VOTAR\nNOMBRE\nVARGAS\nLUNA\nRICARDO\nDOMICILIO\nCALLE ROBLE 22'
    propuesta = extraer.proponer(extraer.agrupar([{'texto': ACTA}, {'texto': ine}]))
    assert propuesta['tutor'] == {'nombres': 'RICARDO', 'primer_apellido': 'VARGAS', 'segundo_apellido': 'LUNA'}
    assert any('revísalo' in aviso for aviso in propuesta['avisos'])


def test_sin_curp_legible_se_usa_el_nombre_con_etiquetas_y_se_pide_la_curp():
    texto = 'ACTA DE NACIMIENTO\nNombre(s): DIEGO  Primer apellido: CASTRO  Segundo apellido: NAVA\nClave: ilegible'
    propuesta = extraer.proponer([{'tipo': 'acta_alumno', 'texto': texto}])
    assert propuesta['alumno'] == {'nombres': 'DIEGO', 'primer_apellido': 'CASTRO', 'segundo_apellido': 'NAVA'}
    assert 'No se encontró la CURP del alumno en el acta: escríbela.' in propuesta['avisos']


def test_la_lista_de_un_grupo_se_lee_renglon_por_renglon():
    sofia = generar.curp('MACS180512MMCRRFA')
    texto = '\n'.join(['LISTA DE ASISTENCIA', 'TERCER GRADO GRUPO C', 'NO. NOMBRE DEL ALUMNO', '1 HERNANDEZ RAMOS LUIS',
                       '2. PEREZ MARIA DEL CARMEN', f'3 MARTINEZ CRUZ SOFIA {sofia}', '4 LOPEZ DIAZ PEDRO LOPD18O512HMCPZDA1'])
    assert extraer.grado_y_grupo(texto) == (3, 'C')
    assert extraer.grado_y_grupo('2° B') == (2, 'B')
    filas = extraer.lista_de_grupo(texto)
    assert [(f['nombres'], f['primer_apellido'], f['segundo_apellido']) for f in filas] == [
        ('LUIS', 'HERNANDEZ', 'RAMOS'), ('MARIA DEL CARMEN', 'PEREZ', ''), ('SOFIA', 'MARTINEZ', 'CRUZ'), ('PEDRO', 'LOPEZ', 'DIAZ')]
    assert filas[2]['curp'] == sofia and not filas[2]['dudoso']
    # La CURP mal leída no se mete al nombre: se propone y queda como duda para que la persona la corrija.
    assert filas[3]['dudoso'] and filas[3]['curp']
    assert extraer.lista_de_grupo('LUIS HERNANDEZ RAMOS', apellidos_primero=False)[0]['primer_apellido'] == 'HERNANDEZ'
