"""Archivos de Excel (.xlsx) y CSV sin instalar nada: solo la biblioteca estándar.

Un .xlsx es un zip con unos cuantos XML. Aquí solo hay texto y números, sin fórmulas ni estilos
(salvo el encabezado en negritas), que es lo que necesita una lista o un conteo para el 911.
"""
import csv
import io
import re
import zipfile
from xml.sax.saxutils import escape

TIPOS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{hojas}
</Types>"""
RELACIONES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
ESTILOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""
MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _columna(numero):
    letras = ''
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _celda(fila, columna, valor, negrita):
    referencia = f'{_columna(columna)}{fila}'
    estilo = ' s="1"' if negrita else ''
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{referencia}"{estilo}><v>{valor}</v></c>'
    texto = escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(valor if valor is not None else '')))
    return f'<c r="{referencia}" t="inlineStr"{estilo}><is><t xml:space="preserve">{texto}</t></is></c>'


def _hoja(filas):
    renglones = []
    for numero, fila in enumerate(filas, 1):
        celdas = ''.join(_celda(numero, columna, valor, numero == 1) for columna, valor in enumerate(fila, 1))
        renglones.append(f'<row r="{numero}">{celdas}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(renglones)}</sheetData></worksheet>')


def _nombre_hoja(nombre, usados):
    limpio = re.sub(r'[\[\]:*?/\\]', ' ', str(nombre)).strip()[:31] or 'Hoja'
    base, numero = limpio, 2
    while limpio.lower() in usados:
        limpio = f'{base[:28]} {numero}'
        numero += 1
    usados.add(limpio.lower())
    return limpio


def xlsx(hojas):
    """hojas: [(nombre, filas)], la primera fila de cada hoja es el encabezado. Devuelve los bytes del .xlsx."""
    salida, usados = io.BytesIO(), set()
    nombres = [_nombre_hoja(nombre, usados) for nombre, _ in hojas]
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as libro:
        libro.writestr('[Content_Types].xml', TIPOS_XML.format(hojas=''.join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(hojas) + 1))))
        libro.writestr('_rels/.rels', RELACIONES)
        libro.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                       + ''.join(f'<sheet name="{escape(n, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
                                 for i, n in enumerate(nombres, 1)) + '</sheets></workbook>')
        libro.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                                 f'Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(hojas) + 1))
                       + f'<Relationship Id="rId{len(hojas) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                       'Target="styles.xml"/></Relationships>')
        libro.writestr('xl/styles.xml', ESTILOS)
        for i, (_, filas) in enumerate(hojas, 1):
            libro.writestr(f'xl/worksheets/sheet{i}.xml', _hoja(filas))
    return salida.getvalue()


def csv_excel(filas):
    """CSV que Excel abre bien en español: UTF-8 con BOM (acentos y Ñ) y comas."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    for fila in filas:
        # Un texto que empieza con =, +, - o @ Excel lo tomaría como fórmula: se antepone un apóstrofo.
        escritor.writerow([f"'{v}" if isinstance(v, str) and v[:1] in ('=', '+', '-', '@') else v for v in fila])
    return ('﻿' + salida.getvalue()).encode('utf-8')
