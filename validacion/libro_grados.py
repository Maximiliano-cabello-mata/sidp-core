"""El Excel de la escuela por grado, con gráficas que comparan los grados entre sí y a los alumnos de cada grado.

Lo arma el servidor (SIDP.exe) con lo que ya tiene: las listas de grupo y los documentos de aquí y, si la PC 4 contesta,
los datos que el escaneo sacó de cada alumno (peso, talla, tipo de sangre, alergias, promedio de la boleta...). Trae
nombres y CURP: es un archivo de la escuela, se descarga en la PC del administrador y no se sube a internet.

Hojas: Resumen (un renglón por grado y las gráficas que comparan los grados), Todos (cada alumno, con la gráfica de
peso contra talla de toda la escuela) y una hoja por grado (sus alumnos, sus grupos y una gráfica por alumno).
Usa openpyxl, que va dentro de SIDP.exe.
"""
import datetime
import io
import re

GRADOS = range(1, 7)
SANGRE = ('O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-')
# (clave, encabezado, ancho): las columnas de la lista de alumnos, en las hojas "Todos" y de cada grado.
COLUMNAS = [
    ('grupo', 'Grupo', 8), ('primer_apellido', 'Primer apellido', 16), ('segundo_apellido', 'Segundo apellido', 16),
    ('nombres', 'Nombre(s)', 20), ('curp', 'CURP', 21), ('renapo', 'CURP en RENAPO', 10), ('sexo', 'Sexo', 7),
    ('fecha_nacimiento', 'Fecha de nacimiento', 12), ('edad', 'Edad al 31 de dic.', 9), ('situacion', 'Edad para el grado', 13),
    ('documentos', 'Documentos', 11), ('validados', 'Documentos validados', 11), ('peso', 'Peso (kg)', 9),
    ('talla', 'Talla (m)', 9), ('imc', 'IMC', 7), ('tipo_sangre', 'Tipo de sangre', 9), ('alergias', 'Alergias', 22),
    ('padecimientos', 'Padecimientos', 22), ('medicamentos', 'Medicamentos', 18), ('promedio', 'Promedio de la boleta', 10),
    ('tutor', 'Tutor', 26), ('parentesco', 'Parentesco', 11), ('telefono', 'Teléfono', 13),
    ('por_confirmar', 'Datos por confirmar', 11),
]
SITUACIONES = ('En su edad', 'Extraedad', 'Menor edad', 'Sin fecha')
AZUL, VERDE, NARANJA, MORADO = '2F5597', '548235', 'C55A11', '7030A0'


class ErrorLibro(Exception):
    """Falta algo para armar el Excel; el mensaje es para la persona."""


# ---------------------------------------------------------------- Los datos de cada alumno

def _numero(texto):
    hallado = re.search(r'\d+(?:[.,]\d+)?', str(texto or ''))
    return float(hallado.group().replace(',', '.')) if hallado else None


def _fecha(texto):
    try:
        return datetime.date.fromisoformat(str(texto)[:10]) if texto else None
    except ValueError:
        return None


def de_curp(curp):
    """(fecha de nacimiento, sexo) que trae la CURP: posiciones 5 a 10 (AAMMDD) y 11 (H o M)."""
    curp = (curp or '').upper()
    if len(curp) != 18:
        return None, None
    siglo = 2000 if curp[16].isalpha() else 1900  # El carácter 17 es letra para los nacidos desde el 2000.
    try:
        fecha = datetime.date(siglo + int(curp[4:6]), int(curp[6:8]), int(curp[8:10]))
    except ValueError:
        fecha = None
    return fecha, curp[10] if curp[10] in 'HM' else None


def edad_al(nacimiento, dia):
    return dia.year - nacimiento.year - ((dia.month, dia.day) < (nacimiento.month, nacimiento.day))


def _dato(datos, categoria, campo, varios=False):
    """El valor del expediente de la PC 4: el confirmado si hay; si no, el que está por confirmar."""
    lista = [d for d in (datos or {}).get(categoria, []) if d.get('campo') == campo and str(d.get('valor') or '').strip()]
    lista.sort(key=lambda d: d.get('estado') != 'vigente')
    if varios:
        valores = list(dict.fromkeys(str(d['valor']).strip() for d in lista))
        return ', '.join(valores) or None
    return str(lista[0]['valor']).strip() if lista else None


def alumno(fila, anio, expediente=None):
    """Un renglón de la lista de aquí (grupos.exportar_alumnos) más el expediente de la PC 4, si lo hay."""
    (grado, letra, primer, segundo, nombres, curp, renapo, sexo, nacimiento, tutor, parentesco, telefono, documentos,
     validados) = fila[:14]
    expediente = expediente or {}
    datos = expediente.get('datos') or {}
    ficha = expediente.get('alumno') or {}
    curp_fecha, curp_sexo = de_curp(curp)
    nacimiento = _fecha(nacimiento) or _fecha(ficha.get('fecha_nacimiento')) or curp_fecha
    sexo = sexo if sexo in ('H', 'M') else ficha.get('sexo') if ficha.get('sexo') in ('H', 'M') else curp_sexo
    edad = edad_al(nacimiento, datetime.date(anio, 12, 31)) if nacimiento else None
    if edad is None:
        situacion = 'Sin fecha'
    elif edad - 5 - int(grado) >= 2:
        situacion = 'Extraedad'
    elif edad - 5 < int(grado):
        situacion = 'Menor edad'
    else:
        situacion = 'En su edad'
    peso = _numero(_dato(datos, 'salud', 'peso'))
    peso = peso if peso and 8 <= peso <= 150 else None
    talla = _numero(_dato(datos, 'salud', 'talla'))
    if talla and talla > 3:  # Escrita en centímetros.
        talla = talla / 100
    talla = round(talla, 2) if talla and 0.6 <= talla <= 2.1 else None
    sangre = (_dato(datos, 'salud', 'tipo_sangre') or '').upper().replace(' ', '').replace('POSITIVO', '+').replace('NEGATIVO', '-')
    promedio = _numero(_dato(datos, 'escolar', 'promedio'))
    principal = (expediente.get('tutores') or [{}])[0]
    if not tutor and principal.get('nombres'):
        tutor = ' '.join(p for p in (principal.get('nombres'), principal.get('primer_apellido'), principal.get('segundo_apellido')) if p)
        parentesco = parentesco or principal.get('parentesco') or ''
        telefono = telefono or principal.get('telefono') or ''
    return {
        'grado': int(grado), 'letra': letra, 'grupo': f'{grado}° {letra}', 'primer_apellido': primer, 'segundo_apellido': segundo,
        'nombres': nombres, 'curp': curp, 'renapo': renapo, 'sexo': {'H': 'Hombre', 'M': 'Mujer'}.get(sexo, ''),
        'fecha_nacimiento': nacimiento, 'edad': edad, 'situacion': situacion, 'documentos': documentos or 0,
        'validados': validados or 0, 'peso': peso, 'talla': talla,
        'imc': round(peso / talla ** 2, 1) if peso and talla else None,
        'tipo_sangre': sangre if sangre in SANGRE else None,
        'alergias': _dato(datos, 'salud', 'alergia', varios=True), 'padecimientos': _dato(datos, 'salud', 'padecimiento', varios=True),
        'medicamentos': _dato(datos, 'salud', 'medicamento', varios=True),
        'promedio': promedio if promedio and 5 <= promedio <= 10 else None,
        'tutor': tutor, 'parentesco': parentesco, 'telefono': telefono,
        'por_confirmar': sum(1 for lista in datos.values() for d in lista if d.get('estado') == 'por_confirmar'),
        'corto': f'{primer} {nombres.split()[0] if nombres else ""}'.strip(),
    }


def _ninguna(texto):
    return not texto or re.fullmatch(r'(?i)\s*(ninguna?s?|no|negad[oa]s?|sin\s+\w+|n/?a|-+)\s*', texto)


def _promedio(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 2) if valores else None


def resumen_grado(alumnos):
    """Un renglón de la hoja Resumen: los números de un grado (o de la escuela)."""
    total = len(alumnos)
    return {
        'grupos': len({a['letra'] for a in alumnos}), 'alumnos': total,
        'hombres': sum(a['sexo'] == 'Hombre' for a in alumnos), 'mujeres': sum(a['sexo'] == 'Mujer' for a in alumnos),
        'edad': _promedio([a['edad'] for a in alumnos]),
        **{s: sum(a['situacion'] == s for a in alumnos) for s in SITUACIONES},
        'documentos': sum(a['documentos'] for a in alumnos), 'validados': sum(a['validados'] for a in alumnos),
        'validados_por_alumno': round(sum(a['validados'] for a in alumnos) / total, 1) if total else None,
        'con_salud': sum(1 for a in alumnos if a['peso'] or a['talla'] or a['tipo_sangre']),
        'peso': _promedio([a['peso'] for a in alumnos]), 'talla': _promedio([a['talla'] for a in alumnos]),
        'imc': _promedio([a['imc'] for a in alumnos]),
        'con_alergias': sum(1 for a in alumnos if not _ninguna(a['alergias'])),
        'promedio': _promedio([a['promedio'] for a in alumnos]), 'por_confirmar': sum(a['por_confirmar'] for a in alumnos),
    }


RESUMEN = [('grupos', 'Grupos'), ('alumnos', 'Alumnos'), ('hombres', 'Hombres'), ('mujeres', 'Mujeres'), ('edad', 'Edad promedio'),
           ('En su edad', 'En su edad'), ('Extraedad', 'Extraedad'), ('Menor edad', 'Menor edad'), ('Sin fecha', 'Sin fecha de nacimiento'),
           ('documentos', 'Documentos'), ('validados', 'Documentos validados'), ('validados_por_alumno', 'Validados por alumno'),
           ('con_salud', 'Con datos de salud'), ('peso', 'Peso promedio (kg)'), ('talla', 'Talla promedio (m)'), ('imc', 'IMC promedio'),
           ('con_alergias', 'Con alergias'), ('promedio', 'Promedio de la boleta'), ('por_confirmar', 'Datos por confirmar')]


# ---------------------------------------------------------------- El libro

def _estilos():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    linea = Side(style='thin', color='BFBFBF')
    return {
        'titulo': Font(bold=True, size=16, color=AZUL), 'sub': Font(italic=True, size=10, color='595959'),
        'encabezado': Font(bold=True, color='FFFFFF'), 'relleno': PatternFill('solid', fgColor=AZUL),
        'total': Font(bold=True), 'relleno_total': PatternFill('solid', fgColor='DDEBF7'),
        'borde': Border(left=linea, right=linea, top=linea, bottom=linea),
        'centro': Alignment(horizontal='center', vertical='center', wrap_text=True),
    }


def _tabla(hoja, fila, columna, encabezado, renglones, estilos, total=False):
    """Escribe una tabla con encabezado; devuelve (primera fila de datos, última fila)."""
    for j, texto in enumerate(encabezado):
        celda = hoja.cell(fila, columna + j, texto)
        celda.font, celda.fill, celda.alignment, celda.border = estilos['encabezado'], estilos['relleno'], estilos['centro'], estilos['borde']
    for i, renglon in enumerate(renglones, 1):
        for j, valor in enumerate(renglon):
            celda = hoja.cell(fila + i, columna + j, valor)
            celda.border = estilos['borde']
            if isinstance(valor, datetime.date):
                celda.number_format = 'dd/mm/yyyy'
            if total and i == len(renglones):
                celda.font, celda.fill = estilos['total'], estilos['relleno_total']
    return fila + 1, fila + len(renglones)


def _grafica(tipo, titulo, eje_x='', eje_y='', apilada=False, horizontal=False, ancho=16, alto=8):
    from openpyxl.chart import BarChart, PieChart, ScatterChart
    grafica = {'barras': BarChart, 'pastel': PieChart, 'puntos': ScatterChart}[tipo]()
    grafica.title, grafica.width, grafica.height = titulo, ancho, alto
    grafica.visible_cells_only = False  # Los nombres cortos de las gráficas por alumno van en una columna escondida.
    if tipo == 'barras':
        grafica.type = 'bar' if horizontal else 'col'
        if horizontal:  # El primer alumno de la lista arriba, como en la tabla.
            grafica.x_axis.scaling.orientation = 'maxMin'
        if apilada:
            grafica.grouping, grafica.overlap = 'stacked', 100
    if tipo != 'pastel':
        grafica.x_axis.title, grafica.y_axis.title = eje_x, eje_y
        grafica.x_axis.delete = grafica.y_axis.delete = False  # openpyxl 3.1 esconde los ejes si no se dice.
        grafica.legend.position = 'b'
    return grafica


def _series(grafica, hoja, columnas, fila_titulo, primera, ultima, col_categorias, colores=()):
    from openpyxl.chart import Reference
    for indice, columna in enumerate(columnas):
        grafica.add_data(Reference(hoja, min_col=columna, min_row=fila_titulo, max_row=ultima), titles_from_data=True)
        if indice < len(colores):
            grafica.series[-1].graphicalProperties.solidFill = colores[indice]
            grafica.series[-1].graphicalProperties.line.solidFill = colores[indice]
    grafica.set_categories(Reference(hoja, min_col=col_categorias, min_row=primera, max_row=ultima))
    return grafica


def _anchos(hoja, anchos, desde=1):
    from openpyxl.utils import get_column_letter
    for j, ancho in enumerate(anchos):
        hoja.column_dimensions[get_column_letter(desde + j)].width = ancho


def _lista(hoja, fila, alumnos, estilos):
    """La lista de alumnos con todas las columnas; devuelve (primera fila de datos, última)."""
    renglones = [[a[clave] for clave, _, _ in COLUMNAS] for a in alumnos]
    primera, ultima = _tabla(hoja, fila, 1, [titulo for _, titulo, _ in COLUMNAS], renglones, estilos)
    _anchos(hoja, [ancho for _, _, ancho in COLUMNAS])
    hoja.row_dimensions[fila].height = 32
    if renglones:
        from openpyxl.utils import get_column_letter
        hoja.auto_filter.ref = f'A{fila}:{get_column_letter(len(COLUMNAS))}{ultima}'
    hoja.freeze_panes = hoja.cell(fila + 1, 5)
    return primera, ultima


def _col(clave):
    return next(i for i, (c, _, _) in enumerate(COLUMNAS, 1) if c == clave)


def _hoja_resumen(libro, alumnos, ciclo, hoy, estilos, escuela):
    hoja = libro.active
    hoja.title = 'Resumen'
    hoja['A1'] = f'{escuela} · ciclo {ciclo}' if escuela else f'Ciclo escolar {ciclo}'
    hoja['A1'].font = estilos['titulo']
    hoja['A2'] = (f'Hecho por SIDP el {hoy:%d/%m/%Y}. Trae datos personales de alumnos: no lo mandes por correo ni lo subas a '
                  'internet. Lo que dice "por confirmar" salió del escaneo y todavía no lo revisa una persona.')
    hoja['A2'].font = estilos['sub']
    renglones = []
    for grado in GRADOS:
        numeros = resumen_grado([a for a in alumnos if a['grado'] == grado])
        renglones.append([f'{grado}°'] + [numeros[c] for c, _ in RESUMEN])
    total = resumen_grado(alumnos)
    renglones.append(['Escuela'] + [total[c] for c, _ in RESUMEN])
    primera, ultima = _tabla(hoja, 4, 1, ['Grado'] + [t for _, t in RESUMEN], renglones, estilos, total=True)
    hoja.row_dimensions[4].height = 45
    _anchos(hoja, [9] + [11] * len(RESUMEN))
    ultima_grado = ultima - 1  # Las gráficas comparan los grados, sin el renglón de la escuela.
    columna = {c: i for i, (c, _) in enumerate(RESUMEN, 2)}

    # Tipo de sangre de toda la escuela (tabla chica para el pastel).
    fila_sangre = ultima + 3
    hoja.cell(fila_sangre - 1, 1, 'Tipo de sangre (toda la escuela)').font = estilos['total']
    cuantos = [[s, sum(a['tipo_sangre'] == s for a in alumnos)] for s in SANGRE]
    cuantos = [c for c in cuantos if c[1]] or [['Sin dato', 0]]
    s_primera, s_ultima = _tabla(hoja, fila_sangre, 1, ['Tipo', 'Alumnos'], cuantos, estilos)

    graficas = [
        _series(_grafica('barras', 'Alumnos por grado', 'Grado', 'Alumnos', apilada=True), hoja,
                [columna['hombres'], columna['mujeres']], 4, primera, ultima_grado, 1, (AZUL, NARANJA)),
        _series(_grafica('barras', 'Edad para el grado', 'Grado', 'Alumnos', apilada=True), hoja,
                [columna[s] for s in SITUACIONES], 4, primera, ultima_grado, 1, (VERDE, NARANJA, AZUL, 'A6A6A6')),
        _series(_grafica('barras', 'Edad promedio por grado', 'Grado', 'Años'), hoja, [columna['edad']], 4, primera, ultima_grado, 1, (AZUL,)),
        _series(_grafica('barras', 'Documentos recibidos y validados', 'Grado', 'Documentos'), hoja,
                [columna['documentos'], columna['validados']], 4, primera, ultima_grado, 1, ('A6A6A6', VERDE)),
        _series(_grafica('barras', 'Peso promedio por grado', 'Grado', 'kg'), hoja, [columna['peso']], 4, primera, ultima_grado, 1, (MORADO,)),
        _series(_grafica('barras', 'Talla promedio por grado', 'Grado', 'metros'), hoja, [columna['talla']], 4, primera, ultima_grado, 1, (VERDE,)),
        _series(_grafica('barras', 'IMC promedio por grado', 'Grado', 'IMC'), hoja, [columna['imc']], 4, primera, ultima_grado, 1, (NARANJA,)),
        _series(_grafica('barras', 'Promedio de la boleta por grado', 'Grado', 'Promedio'), hoja, [columna['promedio']], 4, primera,
                ultima_grado, 1, (AZUL,)),
        _series(_grafica('barras', 'Alumnos con alergias y datos por confirmar', 'Grado', 'Alumnos / datos'), hoja,
                [columna['con_alergias'], columna['por_confirmar']], 4, primera, ultima_grado, 1, ('C00000', 'FFC000')),
        _series(_grafica('pastel', 'Tipo de sangre'), hoja, [2], fila_sangre, s_primera, s_ultima, 1),
    ]
    fila_graficas = s_ultima + 3
    for i, grafica in enumerate(graficas):
        hoja.add_chart(grafica, f'{("A", "J")[i % 2]}{fila_graficas + (i // 2) * 17}')


def _hoja_todos(libro, alumnos, estilos):
    hoja = libro.create_sheet('Todos')
    hoja['A1'] = 'Todos los alumnos'
    hoja['A1'].font = estilos['titulo']
    primera, ultima = _lista(hoja, 3, alumnos, estilos)
    if not alumnos:
        return
    from openpyxl.chart import Reference, Series
    grafica = _grafica('puntos', 'Peso contra talla de todos los alumnos (un color por grado)', 'Talla (m)', 'Peso (kg)', ancho=24, alto=13)
    grafica.style = 13
    for grado in GRADOS:
        filas = [primera + i for i, a in enumerate(alumnos) if a['grado'] == grado]
        if not filas or not any(alumnos[f - primera]['peso'] and alumnos[f - primera]['talla'] for f in filas):
            continue
        serie = Series(Reference(hoja, min_col=_col('peso'), min_row=filas[0], max_row=filas[-1]),
                       Reference(hoja, min_col=_col('talla'), min_row=filas[0], max_row=filas[-1]), title=f'{grado}°')
        serie.marker.symbol, serie.graphicalProperties.line.noFill = 'circle', True
        grafica.series.append(serie)
    if grafica.series:
        hoja.add_chart(grafica, f'A{ultima + 3}')


def _hoja_grado(libro, grado, alumnos, estilos):
    hoja = libro.create_sheet(f'{grado}°')
    hoja['A1'] = f'{grado}° grado: {len(alumnos)} alumnos'
    hoja['A1'].font = estilos['titulo']
    if not alumnos:
        hoja['A2'] = 'No hay alumnos en este grado.'
        return
    primera, ultima = _lista(hoja, 3, alumnos, estilos)
    # Por grupo (A, B...): para comparar los grupos del grado.
    fila = ultima + 3
    hoja.cell(fila - 1, 1, 'Por grupo').font = estilos['total']
    grupos = sorted({a['letra'] for a in alumnos})
    renglones = []
    for letra in grupos:
        n = resumen_grado([a for a in alumnos if a['letra'] == letra])
        renglones.append([f'{grado}° {letra}', n['alumnos'], n['hombres'], n['mujeres'], n['edad'], n['Extraedad'], n['validados_por_alumno'],
                          n['peso'], n['talla'], n['promedio']])
    g_primera, g_ultima = _tabla(hoja, fila, 1, ['Grupo', 'Alumnos', 'Hombres', 'Mujeres', 'Edad promedio', 'Extraedad', 'Validados por alumno',
                                                 'Peso promedio (kg)', 'Talla promedio (m)', 'Promedio de la boleta'], renglones, estilos)
    # Edades del grado (tabla chica para su gráfica).
    edades = sorted({a['edad'] for a in alumnos if a['edad'] is not None})
    fila_edad = g_ultima + 3
    hoja.cell(fila_edad - 1, 1, 'Edades').font = estilos['total']
    e_primera, e_ultima = _tabla(hoja, fila_edad, 1, ['Edad', 'Hombres', 'Mujeres'],
                                 [[f'{e} años', sum(a['edad'] == e and a['sexo'] == 'Hombre' for a in alumnos),
                                   sum(a['edad'] == e and a['sexo'] == 'Mujer' for a in alumnos)] for e in edades] or [['Sin dato', 0, 0]], estilos)
    alto = max(8, 0.6 * len(alumnos) + 3)  # Una barra por alumno, con su nombre.
    nombre = len(COLUMNAS) + 2  # Columna oculta con el nombre corto para las gráficas por alumno.
    hoja.cell(3, nombre, 'Alumno')
    for i, a in enumerate(alumnos):
        hoja.cell(primera + i, nombre, a['corto'])
    from openpyxl.utils import get_column_letter
    hoja.column_dimensions[get_column_letter(nombre)].hidden = True
    graficas = [
        _series(_grafica('barras', 'Hombres y mujeres por grupo', 'Grupo', 'Alumnos', apilada=True), hoja, [3, 4], fila, g_primera, g_ultima, 1,
                (AZUL, NARANJA)),
        _series(_grafica('barras', 'Edades del grado', 'Edad', 'Alumnos', apilada=True), hoja, [2, 3], fila_edad, e_primera, e_ultima, 1,
                (AZUL, NARANJA)),
        _series(_grafica('barras', 'Peso de cada alumno', '', 'kg', horizontal=True, alto=alto), hoja, [_col('peso')], 3, primera, ultima, nombre,
                (MORADO,)),
        _series(_grafica('barras', 'Talla de cada alumno', '', 'metros', horizontal=True, alto=alto), hoja, [_col('talla')], 3, primera, ultima,
                nombre, (VERDE,)),
        _series(_grafica('barras', 'IMC de cada alumno', '', 'IMC', horizontal=True, alto=alto), hoja, [_col('imc')], 3, primera, ultima, nombre,
                (NARANJA,)),
        _series(_grafica('barras', 'Documentos validados de cada alumno', '', 'Documentos', horizontal=True, alto=alto), hoja,
                [_col('validados')], 3, primera, ultima, nombre, (AZUL,)),
    ]
    if any(a['promedio'] for a in alumnos):
        graficas.append(_series(_grafica('barras', 'Promedio de la boleta de cada alumno', '', 'Promedio', horizontal=True, alto=alto), hoja,
                                [_col('promedio')], 3, primera, ultima, nombre, (AZUL,)))
    fila_graficas = e_ultima + 3
    hoja.add_chart(graficas[0], f'A{fila_graficas}')
    hoja.add_chart(graficas[1], f'J{fila_graficas}')
    fila_graficas += 17
    for i, grafica in enumerate(graficas[2:]):  # Dos por renglón; cada renglón mide lo que la gráfica (unos 2 renglones por cm).
        hoja.add_chart(grafica, f'{("A", "J")[i % 2]}{fila_graficas + (i // 2) * int(alto * 2 + 2)}')


def libro(alumnos, ciclo, hoy=None, escuela=None):
    """Los bytes del .xlsx. alumnos: lo que devuelve alumno() para cada uno."""
    try:
        from openpyxl import Workbook
    except ImportError as error:
        raise ErrorLibro('Falta openpyxl para hacer el Excel con gráficas (python -m pip install openpyxl).') from error
    hoy = hoy or datetime.date.today()
    alumnos = sorted(alumnos, key=lambda a: (a['grado'], a['letra'], a['primer_apellido'] or '', a['segundo_apellido'] or '', a['nombres'] or ''))
    estilos = _estilos()
    trabajo = Workbook()
    _hoja_resumen(trabajo, alumnos, ciclo, hoy, estilos, escuela)
    _hoja_todos(trabajo, alumnos, estilos)
    for grado in GRADOS:
        _hoja_grado(trabajo, grado, [a for a in alumnos if a['grado'] == grado], estilos)
    trabajo.properties.creator = 'SIDP'
    salida = io.BytesIO()
    trabajo.save(salida)
    return salida.getvalue()
