"""Revisión de un expediente de inscripción completo: captura del padre contra sus documentos.

Un expediente es una carpeta con `captura.json` (lo que el padre escribió en la
plataforma) y un archivo por documento, nombrado por su tipo (`acta_alumno.pdf`,
`ine_tutor_frente.jpg`, `comprobante.pdf`...). En la plataforma, el tipo lo da el
espacio donde el padre subió el archivo.

En vez de adivinar dónde está cada dato en cada formato de acta o recibo, los
procesos buscan lo capturado dentro del texto del documento. Cada revisión deja
una regla con clave fija (para el resumen sin datos personales) y un detalle
(para el informe local). El modelo solo opina en la zona gris; decide una persona.
"""
import datetime
import difflib
import json
import re
import time
import unicodedata
from pathlib import Path

from validacion import comparador, lector, modelo, mrz

TIPOS = {  # (nombre, obligatorio, textos fijos que dice ese documento; se buscan con tolerancia a errores de OCR)
    'acta_alumno': ('Acta de nacimiento del alumno', True, ['ACTA DE NACIMIENTO', 'REGISTRO CIVIL', 'IDENTIDAD DE LA PERSONA REGISTRADA']),
    'certificado_medico': ('Certificado médico', True, ['CERTIFICADO MEDICO', 'CONSTANCIA MEDICA', 'CERTIFICADO DE SALUD',
                                                        'CEDULA PROFESIONAL', 'ESTADO DE SALUD']),
    'boleta': ('Boleta del ciclo anterior', False, ['BOLETA', 'REPORTE DE EVALUACION', 'EDUCACION PRIMARIA', 'EDUCACION PREESCOLAR',
                                                    'CALIFICACIONES', 'CICLO ESCOLAR']),
    'ine_tutor': ('INE del tutor', True, ['INSTITUTO NACIONAL ELECTORAL', 'CREDENCIAL PARA VOTAR', 'INSTITUTO FEDERAL ELECTORAL',
                                          'CLAVE DE ELECTOR', 'IDMEX']),
    'acta_tutor': ('Acta de nacimiento del tutor', False, ['ACTA DE NACIMIENTO', 'REGISTRO CIVIL', 'IDENTIDAD DE LA PERSONA REGISTRADA']),
    'comprobante': ('Comprobante de domicilio', True, ['COMISION FEDERAL DE ELECTRICIDAD', 'CFE', 'TELMEX', 'TELEFONOS DE MEXICO',
                                                        'AGUA', 'PREDIAL', 'IZZI', 'TOTALPLAY', 'MEGACABLE', 'NATURGY', 'GAS',
                                                        'SUMINISTRADOR DE SERVICIOS BASICOS', 'TOTAL A PAGAR']),
}
PARECIDO = 0.82  # Qué tanto debe parecerse un pedazo del texto a un texto fijo (el OCR cambia letras).
PADRES = {'madre', 'padre'}
MESES = {'ENE': 1, 'ENERO': 1, 'FEB': 2, 'FEBRERO': 2, 'MAR': 3, 'MARZO': 3, 'ABR': 4, 'ABRIL': 4, 'MAY': 5, 'MAYO': 5,
         'JUN': 6, 'JUNIO': 6, 'JUL': 7, 'JULIO': 7, 'AGO': 8, 'AGOSTO': 8, 'SEP': 9, 'SEPT': 9, 'SEPTIEMBRE': 9,
         'SETIEMBRE': 9, 'OCT': 10, 'OCTUBRE': 10, 'NOV': 11, 'NOVIEMBRE': 11, 'DIC': 12, 'DICIEMBRE': 12}
CURP = re.compile(r'\b[A-Z]{4}\d{6}[HMX][A-Z]{5}[0-9A-Z]\d\b')
SEXO = re.compile(r'SEXO\W{0,3}(HOMBRE|MUJER|MASCULINO|FEMENINO|H|M)\b')
SEXO_CURP = {'HOMBRE': 'H', 'MASCULINO': 'H', 'H': 'H', 'MUJER': 'M', 'FEMENINO': 'M', 'M': 'M'}
# Etiquetas de los formatos que se cuelan entre las palabras de un nombre ("Primer apellido: RAMOS").
ETIQUETAS_NOMBRE = {'NOMBRE', 'NOMBRES', 'S', 'PRIMER', 'SEGUNDO', 'APELLIDO', 'APELLIDOS', 'PATERNO', 'MATERNO'}


def mayusculas(texto):
    texto = unicodedata.normalize('NFD', (texto or '').upper())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


def parece(texto, marcas):
    """¿El documento dice alguno de sus textos fijos? Tolera letras cambiadas por el OCR (0 por O, 1 por I)."""
    palabras = re.sub(r'[^A-Z0-9]+', ' ', mayusculas(texto)).split()
    junto = ' '.join(palabras)
    for marca in marcas:
        if marca in junto:
            return True
        largo = len(marca.split())
        if len(marca) < 5:  # Las marcas cortas (CFE, GAS) solo cuentan escritas exactas.
            continue
        for inicio in range(len(palabras) - largo + 1):
            if difflib.SequenceMatcher(None, marca, ' '.join(palabras[inicio:inicio + largo])).ratio() >= PARECIDO:
                return True
    return False


def fechas(texto):
    """Fechas que aparecen en el texto: 14/03/2018, 2018-03-14, 14 DE MARZO DE 2018, 14-MAR-2018."""
    texto, encontradas = mayusculas(texto), []
    patrones = [
        (r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b', lambda d, m, a: (a, m, d)),
        (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', lambda a, m, d: (a, m, d)),
        (r'\b(\d{1,2})\s*(?:DE\s+|[/.-]\s*)?([A-Z]{3,10})\.?\s*(?:DE(?:L)?\s+|[/.-]\s*)?(\d{4})\b',
         lambda d, m, a: (a, MESES.get(m), d)),
    ]
    for patron, orden in patrones:
        for partes in re.findall(patron, texto):
            anio, mes, dia = orden(*partes)
            try:
                encontradas.append(datetime.date(int(anio), int(mes), int(dia)))
            except (TypeError, ValueError):
                pass
    return encontradas


def buscar(objetivo, texto, tipo, orden_libre=False):
    """El pedazo del texto que más se parece a lo capturado: ('igual' | 'gris' | 'distinto', pedazo)."""
    buscado = comparador.normalizar(objetivo, tipo)
    palabras = comparador.normalizar(texto, tipo).split()
    if tipo == 'nombre':
        palabras = [p for p in palabras if p not in ETIQUETAS_NOMBRE]
    largo = len(buscado.split())
    if orden_libre and largo:  # La INE pone primero los apellidos.
        for inicio in range(len(palabras) - largo + 1):
            if sorted(palabras[inicio:inicio + largo]) == sorted(buscado.split()):
                return 'igual', ' '.join(palabras[inicio:inicio + largo])
    rango = {'igual': 2, 'gris': 1, 'distinto': 0}
    mejor = ('distinto', 0.0, '')
    for ventana in range(max(1, largo - 1), largo + (3 if tipo == 'domicilio' else 2)):
        for inicio in range(len(palabras) - ventana + 1):
            pedazo = ' '.join(palabras[inicio:inicio + ventana])
            resultado, valor = comparador.comparar(buscado, pedazo, tipo)
            if (rango[resultado], valor) > (rango[mejor[0]], mejor[1]):
                mejor = (resultado, valor, pedazo)
                if resultado == 'igual':
                    return 'igual', pedazo
    if orden_libre and mejor[0] == 'gris':
        return 'gris', alinear(buscado.split(), mejor[2].split())
    return mejor[0], mejor[2]


def alinear(buscadas, encontradas):
    """Ordena las palabras encontradas como las capturadas (la INE pone primero los apellidos)."""
    restantes, orden = list(encontradas), []
    for palabra in buscadas:
        if not restantes:
            break
        cercana = max(restantes, key=lambda r: difflib.SequenceMatcher(None, palabra, r).ratio())
        restantes.remove(cercana)
        orden.append(cercana)
    return ' '.join(orden + restantes)


class Revision:
    def __init__(self, identificador):
        # extraidos: lo que se encontró en cada documento; va a la base como propuesta, nunca como dato confirmado.
        self.resultado = {'id': identificador, 'hallazgos': [], 'grises': [], 'no_leidos': [], 'documentos': {}, 'extraidos': {}}

    def hallazgo(self, regla, documento, detalle, gravedad='alta'):
        self.resultado['hallazgos'].append({'regla': regla, 'documento': documento, 'detalle': detalle,
                                            'gravedad': gravedad, 'origen': 'proceso'})

    def no_leido(self, regla, documento, detalle):
        self.resultado['no_leidos'].append({'regla': regla, 'documento': documento, 'detalle': detalle})

    def cotejar(self, regla, documento, capturado, texto, tipo, que, orden_libre=False, gravedad='alta'):
        """Busca lo capturado en el texto del documento y anota lo que encuentre."""
        resultado, pedazo = buscar(capturado, texto, tipo, orden_libre)
        if resultado != 'distinto':
            self.resultado['extraidos'][regla] = pedazo
        if resultado == 'gris':
            self.resultado['grises'].append({'regla': regla, 'documento': documento, 'tipo': tipo, 'a': capturado,
                                             'b': pedazo, 'sin_consultar': comparador.sin_consultar(capturado, pedazo, tipo)})
        elif resultado == 'distinto':
            self.hallazgo(regla, documento, f'{que} capturado ("{capturado}") no aparece en el documento', gravedad)
        return resultado


def leer_documentos(carpeta, claves=TIPOS):
    """Texto de cada tipo de documento; un tipo puede tener varios archivos (frente y reverso)."""
    documentos = {}
    for archivo in sorted(Path(carpeta).iterdir()):
        if archivo.suffix == '.json' or archivo.name.startswith('.'):  # captura, resultado y registro no son documentos.
            continue
        tipo = next((t for t in sorted(claves, key=len, reverse=True) if archivo.stem.lower().startswith(t)), None)
        lectura = lector.leer(archivo)
        destino = documentos.setdefault(tipo or 'sin_tipo', {'archivos': [], 'texto': '', 'qr': [], 'metodo': set(), 'problemas': []})
        destino['archivos'].append(archivo.name)
        destino['texto'] += lectura['texto'] + '\n'
        destino['qr'] += lectura['qr']
        destino['metodo'] |= set(lectura['metodo'])
        destino['problemas'] += lectura['problemas']
    return documentos


def revisar(carpeta, hoy=None, usar_modelo=True, nombre_modelo=modelo.MODELO, url=modelo.URL, opinador=None, plantillas=None):
    """Revisa un expediente. Devuelve el resultado con estado, hallazgos, zona gris y lo que no se pudo leer.

    plantillas: las plantillas activas (validacion.plantillas); sin ellas, solo los documentos de fábrica.
    """
    from validacion import plantillas as modulo_plantillas
    vigentes = {p['clave']: p for p in (plantillas if plantillas is not None else modulo_plantillas.fabrica().values())}
    inicio, hoy, carpeta = time.monotonic(), hoy or datetime.date.today(), Path(carpeta)
    revision = Revision(carpeta.name)
    try:
        captura = json.loads((carpeta / 'captura.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        revision.no_leido('captura', 'captura.json', f'no se pudo leer la captura: {error}')
        captura = {}
    alumno, tutor = captura.get('alumno', {}), captura.get('tutor', {})
    documentos = leer_documentos(carpeta, vigentes)

    for tipo, datos in documentos.items():
        texto = (datos['texto'] + ' ' + ' '.join(datos['qr'])).strip()
        nombre = vigentes[tipo]['nombre'] if tipo in vigentes else 'Archivo sin tipo'
        revision.resultado['documentos'][tipo] = {'archivos': datos['archivos'], 'metodo': sorted(datos['metodo']),
                                                  'caracteres': len(texto), 'qr': len(datos['qr']), 'problemas': datos['problemas']}
        datos['texto'] = texto
        if tipo == 'sin_tipo':
            revision.hallazgo('archivo_sin_tipo', ', '.join(datos['archivos']),
                              'el nombre del archivo no dice qué documento es', 'media')
            continue
        if len(texto) < lector.MINIMO_TEXTO:
            revision.no_leido('no_leido', nombre, '; '.join(datos['problemas']) or 'no se encontró texto en el documento')
            continue
        if comparador.SOSPECHOSO.search(texto):
            revision.hallazgo('texto_sospechoso', nombre, 'el documento trae texto que parece una orden')
        if tipo == 'ine_tutor':  # Reverso de la INE: la franja con '<' trae nombre y fechas comprobables.
            franja = mrz.leer(texto)
            if franja:
                revision.resultado['extraidos']['ine_mrz'] = {k: (v.isoformat() if hasattr(v, 'isoformat') else v)
                                                              for k, v in franja.items()}
                if franja.get('nombre'):
                    datos['texto'] = texto = texto + '\n' + franja['nombre']
                if franja.get('vigencia') and franja['vigencia'] < hoy:
                    revision.hallazgo('ine_vencida', nombre, f'la INE venció el {franja["vigencia"].isoformat()}')
        if not vigentes[tipo].get('fabrica'):  # Documento que agregó la escuela: se valida con su plantilla.
            modulo_plantillas.aplicar(vigentes[tipo], texto, alumno, tutor, hoy, revision)
        elif not parece(texto, vigentes[tipo]['textos']):
            revision.hallazgo('tipo_incorrecto', nombre, f'no parece un(a) {nombre.lower()}', 'media')

    for tipo, plantilla in vigentes.items():
        if plantilla['obligatorio'] and tipo not in documentos:
            revision.hallazgo('falta_documento', plantilla['nombre'], 'falta el documento')

    def texto_de(tipo):
        datos = documentos.get(tipo)
        return datos['texto'] if datos and len(datos['texto']) >= lector.MINIMO_TEXTO else None

    # CURP capturada: formato y dígito verificador.
    desglose = comparador.desglose_curp(alumno.get('curp'))
    if not alumno.get('curp'):
        revision.hallazgo('curp_falta', 'Captura', 'no se capturó la CURP del alumno')
    elif desglose is None:
        revision.hallazgo('curp_formato', 'Captura', 'la CURP capturada no tiene un formato válido')
    elif not desglose['digito_valido']:
        revision.hallazgo('curp_digito', 'Captura', 'el dígito verificador de la CURP capturada no es correcto')

    acta = texto_de('acta_alumno')
    if acta:
        documento = TIPOS['acta_alumno'][0]
        if alumno.get('nombre'):
            revision.cotejar('acta_nombre', documento, alumno['nombre'], acta, 'nombre', 'El nombre del alumno')
        curps = set(CURP.findall(mayusculas(acta)))
        revision.resultado['extraidos']['acta_curps'] = sorted(curps)
        revision.resultado['extraidos']['acta_fechas'] = sorted({f.isoformat() for f in fechas(acta)})
        if alumno.get('curp') and curps and alumno['curp'].upper() not in curps:
            revision.hallazgo('acta_curp', documento, f'la CURP del acta ({", ".join(sorted(curps))}) no es la capturada')
        if desglose:
            if datetime.date.fromisoformat(desglose['fecha']) not in fechas(acta):
                revision.no_leido('acta_fecha', documento, f'no se encontró en el acta la fecha de nacimiento de la CURP ({desglose["fecha"]})')
            sexo = SEXO.search(mayusculas(acta))
            if sexo:
                revision.resultado['extraidos']['acta_sexo'] = SEXO_CURP[sexo.group(1)]
            if sexo and SEXO_CURP[sexo.group(1)] != desglose['sexo']:
                revision.hallazgo('acta_sexo', documento, 'el sexo del acta no coincide con la CURP')
        if tutor.get('nombre') and tutor.get('parentesco', '').lower() in PADRES:
            revision.cotejar('acta_tutor', documento, tutor['nombre'], acta, 'nombre', f'El nombre del tutor ({tutor["parentesco"]})')

    for tipo in ('certificado_medico', 'boleta'):
        texto = texto_de(tipo)
        if texto and alumno.get('nombre'):
            revision.cotejar(f'{tipo}_nombre', TIPOS[tipo][0], alumno['nombre'], texto, 'nombre', 'El nombre del alumno',
                             orden_libre=True, gravedad='media')

    for tipo in ('ine_tutor', 'acta_tutor'):
        texto = texto_de(tipo)
        if texto and tutor.get('nombre'):
            revision.cotejar(f'{tipo}_nombre', TIPOS[tipo][0], tutor['nombre'], texto, 'nombre', 'El nombre del tutor',
                             orden_libre=True)

    comprobante = texto_de('comprobante')
    if comprobante:
        documento = TIPOS['comprobante'][0]
        pasadas = [f for f in fechas(comprobante) if f <= hoy]
        if pasadas:
            revision.resultado['extraidos']['comprobante_fecha'] = max(pasadas).isoformat()
        if not pasadas:
            revision.no_leido('comprobante_fecha', documento, 'no se encontró la fecha del comprobante')
        elif comparador.sumar_meses(max(pasadas), 3) < hoy:
            revision.hallazgo('comprobante_viejo', documento, f'la fecha más reciente del comprobante es {max(pasadas)}: tiene más de 3 meses', 'media')
        if tutor.get('domicilio'):
            revision.cotejar('comprobante_domicilio', documento, tutor['domicilio'], comprobante, 'domicilio', 'El domicilio')

    for gris in revision.resultado['grises']:
        if usar_modelo and not gris['sin_consultar']:  # opinador: el cerebro de otra PC (modelo.opinar_remoto).
            gris['opinion'] = opinador(gris) if opinador else modelo.opinar(gris, nombre_modelo, url)
        else:
            gris['opinion'] = {'misma': 'duda', 'motivo': gris['sin_consultar'] or 'sin modelo', 'segundos': 0.0}
    r = revision.resultado
    r['estado'] = 'revisión manual' if r['hallazgos'] or r['grises'] or r['no_leidos'] else 'listo para autorizar'
    r['segundos'] = round(time.monotonic() - inicio, 1)
    return r
