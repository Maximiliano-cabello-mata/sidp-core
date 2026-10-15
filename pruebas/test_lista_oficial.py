"""La lista oficial de la escuela (formato de estadística de la SEP, toda la escuela en un PDF) como base de alumnos.

Todo es inventado: los nombres y las CURP salen de validacion/ejemplo/generar.py.
"""
import io

import pytest

from pruebas.pdf_sencillo import pdf_de_texto
from pruebas.test_entorno_pruebas import entorno, formulario, pedir  # noqa: F401 (entorno es un fixture)
from validacion import servicio
from validacion.ejemplo import generar
from validacion.expediente import mayusculas
from validacion.extraer import curps, grado_por_edad

pypdf = pytest.importorskip('pypdf')

# Ciclo 2026-2027: 1° nació en 2020, 2° en 2019. El número del encabezado es la fase (3), no el grado.
PRIMERO = [('GARCIA', 'HERNANDEZ', 'JUAN', 'GAHJ200512HMCRRNA'), ('LOPEZ', 'MARTINEZ', 'ANA SOFIA', 'LOMA200301MMCPRNA'),
           ('PEREZ', 'RUIZ', 'MATEO', 'PERM201107HMCRZTA')]
SEGUNDO = [('CRUZ', 'DIAZ', 'REGINA', 'CUDR190716MMCRZGA'), ('NAVA', 'SOTO', 'DIEGO', 'NASD190220HMCVTGA'),
           ('ROJAS', 'VEGA', 'LUCIA', 'ROVL190905MMCJGCA'), ('TORRES', 'LUNA', 'EMILIO', 'TOLE191230HMCRNMA')]


def hoja(alumnos, inicio=1):
    renglones = ['ESTADISTICA DE INICIO DE CURSOS 2026-2027', 'FASE 3', 'CURP NUM NOMBRE']
    return renglones + [f'{generar.curp(c)} {i} {p} {s} {n}' for i, (p, s, n, c) in enumerate(alumnos, inicio)]


def pdf_de_hojas(hojas):
    escritor = pypdf.PdfWriter()
    for renglones in hojas:
        escritor.add_page(pypdf.PdfReader(io.BytesIO(pdf_de_texto(renglones))).pages[0])
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def test_las_letras_griegas_que_parecen_latinas_se_leen_como_latinas():
    curp = generar.curp('GAHJ200512HMCRRNA')
    griega = curp.replace('A', 'Α').replace('M', 'Μ')  # Alfa y mu griegas, como vienen en algunas CURP del PDF oficial.
    assert griega != curp and mayusculas(griega) == curp
    assert curps(f'{griega} 1 GARCIA HERNANDEZ JUAN') == [curp]


def test_el_grado_sale_de_la_edad_de_la_mayoria():
    nacidos_2019 = [generar.curp(c) for *_, c in SEGUNDO]
    assert grado_por_edad(nacidos_2019, 2026) == 2
    assert grado_por_edad(nacidos_2019[:1] + [generar.curp('GAHJ200512HMCRRNA')] * 3, 2026) == 1  # Uno repetidor no cambia el grupo.
    assert grado_por_edad(nacidos_2019[:2], 2026) is None  # Con menos de 3 no se adivina.


def test_la_lista_oficial_trae_toda_la_escuela_y_se_guarda_de_un_jalon(entorno):  # noqa: F811
    app, url = entorno
    token = {'X-SIDP-Token': app.token}
    instrucciones = ['INSTRUCCIONES', 'Capture la informacion de cada alumno', 'Grado 3 Grupo A']
    # 2° sigue en la hoja siguiente: se une al mismo grupo.
    contenido = pdf_de_hojas([instrucciones, hoja(PRIMERO), hoja(SEGUNDO[:3]), hoja(SEGUNDO[3:], 4)])
    cuerpo, tipo = formulario({}, [('archivo', 'estadistica.pdf', contenido)])
    codigo, leida = pedir(url, '/api/listas/leer', cuerpo, token, tipo=tipo)
    assert codigo == 200, leida
    assert [(g['grado'], g['letra'], g['letra_supuesta'], len(g['filas'])) for g in leida['grupos']] == [(1, 'A', True, 3), (2, 'A', True, 4)]
    assert [(f['primer_apellido'], f['nombres']) for f in leida['grupos'][1]['filas']][-1] == ('TORRES', 'EMILIO')
    assert leida['letra'] is None  # La hoja no dice la letra: la persona la confirma.
    # Dos grupos con el mismo grado y letra no se guardan; nada queda a medias.
    grupos = [{'grado': g['grado'], 'letra': g['letra'], 'filas': g['filas']} for g in leida['grupos']]
    codigo, respuesta = pedir(url, '/api/listas/guardar', {'grupos': [grupos[0], {**grupos[1], 'grado': 1}]}, token)
    assert codigo == 400 and 'mismo grado' in respuesta['error']
    codigo, respuesta = pedir(url, '/api/listas/guardar', {'grupos': [grupos[0], {**grupos[1], 'filas': [{'nombres': 'X'}]}]}, token)
    assert codigo == 400 and respuesta['error'].startswith('Grupo 2')
    assert pedir(url, '/api/grupos', cabeceras=token)[1]['grupos'] == []
    codigo, guardado = pedir(url, '/api/listas/guardar', {'grupos': grupos}, token)
    assert codigo == 200 and guardado['agregados'] == 7, guardado
    assert [(g['grupo'], g['agregados']) for g in guardado['guardados']] == [('1° A', 3), ('2° A', 4)]
    assert [(g['nombre'], g['alumnos'], g['sin_curp']) for g in guardado['grupos']] == [('1° A', 3, 0), ('2° A', 4, 0)]
    # Otra vez el mismo PDF: nadie se repite.
    assert pedir(url, '/api/listas/guardar', {'grupos': grupos}, token)[1]['ya_estaban'] == 7


def test_la_curp_mal_leida_se_corrige_con_el_padron():
    curp = generar.curp('GAHJ200512HMCRRNA')
    leida = curp[:6] + ('1' if curp[6] != '1' else '2') + curp[7:]
    sugerencia = {'por': 'curp', 'leida': leida, 'distancia': 1, 'curp': curp, 'primer_apellido': 'GARCIA',
                  'segundo_apellido': 'HERNANDEZ', 'nombres': 'JUAN', 'grado': 1, 'letra': 'A'}
    propuesta = {'alumno': {'curp': leida, 'nombres': 'JUAN'}, 'avisos': [f'La CURP {leida} no cuadra su dígito verificador']}
    servicio.con_padron(propuesta, [{'tipo': 'acta_alumno', 'sugerencias': [sugerencia]}])
    assert propuesta['alumno']['curp'] == curp and propuesta['alumno']['primer_apellido'] == 'GARCIA'
    assert len(propuesta['avisos']) == 1 and 'compárala con el acta' in propuesta['avisos'][0]
    # Si la CURP leída sí es de un alumno, no se toca nada.
    exacta = {**sugerencia, 'leida': curp, 'distancia': 0}
    propuesta = {'alumno': {'curp': curp}, 'avisos': []}
    servicio.con_padron(propuesta, [{'tipo': 'acta_alumno', 'sugerencias': [exacta, sugerencia]}])
    assert propuesta == {'alumno': {'curp': curp}, 'avisos': []}


def test_sin_curp_el_nombre_propone_al_alumno_solo_si_no_hay_empate():
    juan = {'por': 'nombre', 'parecido': 0.9, 'curp': generar.curp('GAHJ200512HMCRRNA'), 'primer_apellido': 'GARCIA',
            'segundo_apellido': 'HERNANDEZ', 'nombres': 'JUAN', 'grado': 1, 'letra': 'A'}
    propuesta = {'alumno': {}, 'avisos': []}
    servicio.con_padron(propuesta, [{'tipo': 'acta_alumno', 'sugerencias': [juan]}])
    assert propuesta['alumno']['curp'] == juan['curp'] and propuesta['alumno']['fecha_nacimiento'] == '2020-05-12'
    hermano = {**juan, 'nombres': 'JUAN PABLO', 'curp': generar.curp('GAHJ190512HMCRRNA'), 'parecido': 0.88}
    propuesta = {'alumno': {}, 'avisos': []}
    servicio.con_padron(propuesta, [{'tipo': 'acta_alumno', 'sugerencias': [juan, hermano]}])
    assert propuesta == {'alumno': {}, 'avisos': []}
