"""Revisión de una ficha con procesos fijos, sin IA.

Una ficha son los datos que los lectores (QR, texto del PDF, OCR) sacaron de
los documentos de un alumno. Aquí se comparan entre sí con reglas. Lo que una
regla no puede decidir (un nombre o domicilio parecido pero no igual) queda
como "zona gris": se le puede pedir opinión al modelo, pero siempre pasa al
administrador. El modelo nunca quita una alerta de las reglas.
"""
import calendar
import datetime
import difflib
import re
import unicodedata

DICCIONARIO_CURP = '0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'
ABREVIATURAS = {
    'nombre': {'MA': 'MARIA', 'GPE': 'GUADALUPE', 'FCO': 'FRANCISCO'},
    'domicilio': {'AV': 'AVENIDA', 'AVE': 'AVENIDA', 'C': 'CALLE', 'CDA': 'CERRADA', 'FRACC': 'FRACCIONAMIENTO'},
}
# Palabras que no distinguen un domicilio de otro.
RELLENO_DOMICILIO = {'COL', 'COLONIA', 'NUM', 'NO', 'NUMERO', 'N', 'DE', 'LA', 'EL', 'MZ', 'LT'}
SOSPECHOSO = re.compile(r'IGNORA|INSTRUCCION|RESPONDE|ERES UN|SYSTEM|PROMPT|APRUEBA', re.I)

# Palabras que pueden sobrar en un domicilio sin cambiarlo.
SOBRANTES_DOMICILIO = {'CALLE', 'MEX', 'MEXICO', 'EDO', 'ESTADO'}

# Parecido mínimo (0 a 1) para zona gris; debajo, es distinto.
NOMBRE_GRIS = 0.80
DOMICILIO_GRIS = 0.70


def normalizar(texto, tipo='nombre'):
    texto = unicodedata.normalize('NFD', (texto or '').upper())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    palabras = re.sub(r'[^A-Z0-9]+', ' ', texto).split()
    palabras = [ABREVIATURAS[tipo].get(p, p) for p in palabras]
    relleno = RELLENO_DOMICILIO if tipo == 'domicilio' else ()
    return ' '.join(p for p in palabras if p not in relleno)


def parecido(a, b):
    ordenados = ' '.join(sorted(a.split())), ' '.join(sorted(b.split()))
    return max(difflib.SequenceMatcher(None, a, b).ratio(), difflib.SequenceMatcher(None, *ordenados).ratio())


def comparar(a, b, tipo):
    """Devuelve ('igual' | 'gris' | 'distinto', parecido)."""
    na, nb = normalizar(a, tipo), normalizar(b, tipo)
    if tipo == 'domicilio' and re.findall(r'\d+', na) != re.findall(r'\d+', nb):
        return 'distinto', parecido(na, nb)  # Otro número de casa es otro domicilio.
    if na == nb:
        return 'igual', 1.0
    valor, pa, pb = parecido(na, nb), set(na.split()), set(nb.split())
    if tipo == 'domicilio' and pa ^ pb <= SOBRANTES_DOMICILIO:
        return 'igual', valor
    if tipo == 'nombre' and (pa <= pb or pb <= pa):
        return 'gris', valor  # Falta un nombre o apellido: lo decide una persona.
    return ('gris' if valor >= (NOMBRE_GRIS if tipo == 'nombre' else DOMICILIO_GRIS) else 'distinto'), valor


def digito_curp(curp):
    suma = sum(DICCIONARIO_CURP.index(c) * (18 - i) for i, c in enumerate(curp[:17]))
    return str((10 - suma % 10) % 10)


def desglose_curp(curp):
    """Fecha, sexo y entidad que trae la CURP, o None si no tiene la forma correcta."""
    curp = (curp or '').upper()
    if not re.fullmatch(r'[A-Z]{4}\d{6}[HMX][A-Z]{5}[0-9A-Z]\d', curp):
        return None
    siglo = 1900 if curp[16].isdigit() else 2000
    try:
        fecha = datetime.date(siglo + int(curp[4:6]), int(curp[6:8]), int(curp[8:10]))
    except ValueError:
        return None
    return {'fecha': fecha.isoformat(), 'sexo': curp[10], 'entidad': curp[11:13],
            'digito_valido': digito_curp(curp) == curp[17]}


def sumar_meses(fecha, meses):
    mes = fecha.month - 1 + meses
    anio, mes = fecha.year + mes // 12, mes % 12 + 1
    return fecha.replace(year=anio, month=mes, day=min(fecha.day, calendar.monthrange(anio, mes)[1]))


def revisar(ficha, hoy):
    """Hallazgos de las reglas y comparaciones en zona gris de una ficha."""
    hallazgos, grises = [], []

    def hallazgo(campo, detalle, gravedad):
        hallazgos.append({'campo': campo, 'detalle': detalle, 'gravedad': gravedad, 'origen': 'regla'})

    def cotejar(campo, a, b, tipo):
        if not a or not b:
            return None
        resultado, valor = comparar(a, b, tipo)
        if resultado == 'distinto':
            hallazgo(campo, f'"{a}" no coincide con "{b}"', 'alta')
        elif resultado == 'gris':
            grises.append({'campo': campo, 'tipo': tipo, 'a': a, 'b': b, 'parecido': round(valor, 2)})
        return resultado

    alumno, acta = ficha.get('alumno', {}), ficha.get('acta_alumno', {})
    tutor, comprobante = ficha.get('tutor', {}), ficha.get('comprobante_domicilio', {})

    # Texto con órdenes escondidas: el proceso no lo obedece, lo reporta.
    for origen, datos in ficha.items():
        for clave, valor in (datos.items() if isinstance(datos, dict) else ()):
            if isinstance(valor, str) and SOSPECHOSO.search(valor):
                hallazgo(f'{origen}.{clave}', 'el documento trae texto que parece una orden', 'alta')

    cotejar('alumno.nombre', alumno.get('nombre'), acta.get('nombre'), 'nombre')

    if alumno.get('curp'):
        desglose = desglose_curp(alumno['curp'])
        if desglose is None:
            hallazgo('alumno.curp', 'la CURP no tiene un formato válido', 'alta')
        else:
            if not desglose['digito_valido']:
                hallazgo('alumno.curp', 'el dígito verificador de la CURP no es correcto', 'alta')
            if acta.get('fecha_nacimiento') and acta['fecha_nacimiento'] != desglose['fecha']:
                hallazgo('acta_alumno.fecha_nacimiento',
                         f'el acta dice {acta["fecha_nacimiento"]} y la CURP {desglose["fecha"]}', 'alta')
            sexo_acta = (acta.get('sexo') or '')[:1].upper()
            if sexo_acta in 'HM' and sexo_acta and sexo_acta != desglose['sexo']:
                hallazgo('acta_alumno.sexo', 'el sexo del acta no coincide con la CURP', 'alta')

    nombre_tutor = tutor.get('nombre_capturado')
    cotejar('tutor.ine_nombre', nombre_tutor, tutor.get('ine_nombre'), 'nombre')
    padres = [p for p in (acta.get('padre'), acta.get('madre')) if p]
    if nombre_tutor and padres:
        resultados = [comparar(nombre_tutor, p, 'nombre')[0] for p in padres]
        if 'igual' not in resultados:
            if 'gris' in resultados:
                cercano = max(padres, key=lambda p: comparar(nombre_tutor, p, 'nombre')[1])
                cotejar('tutor.parentesco', nombre_tutor, cercano, 'nombre')
            else:
                hallazgo('tutor.parentesco', f'"{nombre_tutor}" no aparece como padre ni madre en el acta', 'alta')

    if comprobante:
        if comprobante.get('fecha'):
            fecha = datetime.date.fromisoformat(comprobante['fecha'])
            if fecha > hoy:
                hallazgo('comprobante_domicilio.fecha', 'la fecha del comprobante es posterior a hoy', 'alta')
            elif sumar_meses(fecha, 3) < hoy:
                hallazgo('comprobante_domicilio.fecha', f'el comprobante es del {fecha} y tiene más de 3 meses', 'media')
        if cotejar('comprobante_domicilio.titular', nombre_tutor, comprobante.get('titular'), 'nombre') == 'distinto':
            # Un comprobante a nombre de otro familiar es común: lo decide el administrador.
            hallazgos[-1]['gravedad'] = 'media'
        cotejar('comprobante_domicilio.domicilio', tutor.get('domicilio_capturado'),
                comprobante.get('domicilio'), 'domicilio')

    return hallazgos, grises


def estado(hallazgos, grises):
    return 'revisión manual' if hallazgos or grises else 'listo para autorizar'
