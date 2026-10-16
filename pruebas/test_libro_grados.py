"""El Excel por grado: un resumen que compara los grados, todos los alumnos y una hoja por grado con gráficas."""
import datetime
import io
import re
import zipfile

import openpyxl

from pruebas.test_entorno_pruebas import descargar, entorno, pedir  # noqa: F401 (entorno es la prueba con el panel)
from validacion import libro_grados

HOY = datetime.date(2026, 10, 16)


def salud(peso, talla, sangre, alergias=(), estado='vigente'):
    datos = [{'campo': 'peso', 'valor': peso, 'estado': estado}, {'campo': 'talla', 'valor': talla, 'estado': 'vigente'},
             {'campo': 'tipo_sangre', 'valor': sangre, 'estado': 'vigente'}]
    datos += [{'campo': 'alergia', 'valor': a, 'estado': 'vigente'} for a in alergias]
    return {'datos': {'salud': datos, 'escolar': [{'campo': 'promedio', 'valor': '9.2', 'estado': 'vigente'}]}}


def fila(grado, letra, apellido, nombre, curp='', sexo='', nacimiento='', documentos=0, validados=0):
    return [grado, letra, apellido, 'RUIZ', nombre, curp, 'No', sexo, nacimiento, '', '', '', documentos, validados]


def test_cada_alumno_junta_la_lista_de_aqui_con_lo_que_saco_el_escaneo():
    # Sin fecha ni sexo en la lista: salen de la CURP (inventada; el carácter 17 es letra porque nació en el 2000 o después).
    nino = libro_grados.alumno(fila(1, 'A', 'LOPEZ', 'ANA', 'LORA190305MMCPZNA1'), 2026,
                               salud('18,5 kg', '105 cm', 'o positivo', ['POLVO', 'POLVO', 'NUECES'], estado='por_confirmar'))
    assert (nino['fecha_nacimiento'], nino['sexo'], nino['edad'], nino['situacion']) == (datetime.date(2019, 3, 5), 'Mujer', 7, 'En su edad')
    assert (nino['peso'], nino['talla'], nino['imc'], nino['tipo_sangre']) == (18.5, 1.05, 16.8, 'O+')
    assert nino['alergias'] == 'POLVO, NUECES' and nino['promedio'] == 9.2 and nino['por_confirmar'] == 1
    grande = libro_grados.alumno(fila(1, 'A', 'PEREZ', 'LUIS', nacimiento='2017-01-10'), 2026)
    assert (grande['edad'], grande['situacion'], grande['peso'], grande['tipo_sangre']) == (9, 'Extraedad', None, None)
    # Un dato que no puede ser (peso de 400 kg) no entra a los promedios.
    assert libro_grados.alumno(fila(2, 'A', 'X', 'Y'), 2026, salud('400', '1.2', 'Z+'))['peso'] is None


def test_el_libro_trae_resumen_todos_y_una_hoja_por_grado_con_graficas():
    alumnos = [libro_grados.alumno(fila(1, 'A', 'LOPEZ', 'ANA', sexo='M', nacimiento='2019-03-05', documentos=4, validados=3), 2026,
                                   salud('18', '1.05', 'O+', ['POLVO'])),
               libro_grados.alumno(fila(1, 'B', 'GARCIA', 'JUAN', sexo='H', nacimiento='2019-07-01', documentos=2, validados=2), 2026,
                                   salud('22', '1.10', 'A+', ['NINGUNA'])),
               libro_grados.alumno(fila(3, 'A', 'CRUZ', 'SOFIA', sexo='M', nacimiento='2017-02-02'), 2026)]
    contenido = libro_grados.libro(alumnos, '2026-2027', HOY)
    libro = openpyxl.load_workbook(io.BytesIO(contenido))
    assert libro.sheetnames == ['Resumen', 'Todos', '1°', '2°', '3°', '4°', '5°', '6°']
    resumen = libro['Resumen']
    encabezado = [c.value for c in resumen[4]]
    primero = dict(zip(encabezado, [c.value for c in resumen[5]]))
    escuela = dict(zip(encabezado, [c.value for c in resumen[11]]))
    assert (primero['Grado'], primero['Grupos'], primero['Alumnos'], primero['Hombres'], primero['Mujeres']) == ('1°', 2, 2, 1, 1)
    assert (primero['Peso promedio (kg)'], primero['Con alergias'], primero['Validados por alumno']) == (20, 1, 2.5)
    assert (escuela['Grado'], escuela['Alumnos']) == ('Escuela', 3)
    assert [c.value for c in libro['1°'][4]][:4] == ['1° A', 'LOPEZ', 'RUIZ', 'ANA']
    assert libro['2°']['A2'].value == 'No hay alumnos en este grado.'
    # Las gráficas: 10 en el resumen, la de peso contra talla de toda la escuela y las de cada grado con alumnos.
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
        graficas = [n for n in archivo.namelist() if re.fullmatch(r'xl/charts/chart\d+\.xml', n)]
        assert len(graficas) == 10 + 1 + 7 + 6  # 1° tiene promedio de boleta; 3° no.
        assert all('<delete val="0"/>' in archivo.read(n).decode() for n in graficas if 'barChart' in archivo.read(n).decode())


def test_el_panel_descarga_el_excel_por_grado_aunque_la_pc_4_no_tenga_base(entorno):  # noqa: F811
    app, url = entorno
    token = {'X-SIDP-Token': app.token}
    pedir(url, '/api/listas/guardar', {'grado': 2, 'letra': 'A', 'filas': [
        {'nombres': 'LUIS', 'primer_apellido': 'HERNANDEZ', 'segundo_apellido': 'RAMOS', 'curp': 'HERL180314HMCRMSA9'}]}, token)
    cabeceras, contenido = descargar(url, '/api/exportar?que=por_grado&formato=xlsx', app.token)
    assert 'sidp_por_grado_' in cabeceras['Content-Disposition']
    libro = openpyxl.load_workbook(io.BytesIO(contenido))
    assert libro['2°']['D4'].value == 'LUIS' and libro['2°']['G4'].value == 'Hombre'  # El sexo sale de la CURP.
