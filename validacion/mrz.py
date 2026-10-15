"""Franja de lectura mecánica (MRZ) del reverso de la INE: tres renglones de 30 caracteres con '<'.

Proceso fijo: trae nombre, fecha de nacimiento, sexo y vigencia, y las fechas tienen dígito
verificador (norma ICAO 9303, formato TD1). Si un dígito no cuadra, el OCR leyó mal y el dato
no se usa. Sin IA.

    IDMEX1234567890<<0123456789012
    8501012M3112319MEX<02<<12345<7
    RAMOS<SOTO<<MARIA<ELENA<<<<<<<
"""
import datetime
import re

PESOS = (7, 3, 1)
FECHA_SEXO = re.compile(r'(\d{6})(\d)([MFX<])(\d{6})(\d)([A-Z<]{3})')


def digito(texto):
    """Dígito verificador ICAO: 0-9 valen su número, A-Z de 10 a 35 y '<' vale 0."""
    total = 0
    for i, c in enumerate(texto):
        valor = int(c) if c.isdigit() else (ord(c) - 55 if c.isalpha() else 0)
        total += valor * PESOS[i % 3]
    return total % 10


def _renglones(texto):
    """Renglones candidatos: sin espacios, con '«' y similares como '<'."""
    salida = []
    for linea in (texto or '').upper().splitlines():
        linea = re.sub(r'[«‹＜]', '<', linea)
        linea = re.sub(r'[^A-Z0-9<]', '', linea)
        if len(linea) >= 20 and ('<' in linea or FECHA_SEXO.search(linea)):
            salida.append(linea)
    return salida


def _fecha(aammdd, futuro=False):
    hoy = datetime.date.today()
    anio, mes, dia = int(aammdd[:2]), int(aammdd[2:4]), int(aammdd[4:])
    siglo = 2000 if (futuro or anio <= hoy.year % 100) else 1900
    try:
        return datetime.date(siglo + anio, mes, dia)
    except ValueError:
        return None


def _nombre(renglon):
    """APELLIDO1<APELLIDO2<<NOMBRE1<NOMBRE2<<<  →  (apellidos, nombres)."""
    renglon = renglon.rstrip('<')
    if '<<' not in renglon:
        return None
    apellidos, nombres = renglon.split('<<', 1)
    apellidos = [p for p in apellidos.split('<') if p]
    nombres = [p for p in nombres.replace('<<', '<').split('<') if p]
    if not apellidos or not nombres or any(re.search(r'\d', p) for p in apellidos + nombres):
        return None
    return apellidos, nombres


def leer(texto):
    """Datos de la MRZ que se pudieron comprobar, o None si no hay franja legible."""
    renglones = _renglones(texto)
    for i, renglon in enumerate(renglones):
        fechas = FECHA_SEXO.search(renglon)
        if not fechas:
            continue
        nacimiento, d_nac, sexo, vigencia, d_vig, pais = fechas.groups()
        datos = {'nacimiento_valido': digito(nacimiento) == int(d_nac), 'vigencia_valida': digito(vigencia) == int(d_vig),
                 'pais': pais.replace('<', '')}
        if datos['nacimiento_valido']:
            datos['nacimiento'] = _fecha(nacimiento)
        if datos['vigencia_valida']:
            datos['vigencia'] = _fecha(vigencia, futuro=True)
        if sexo in 'MF':
            datos['sexo'] = 'M' if sexo == 'F' else 'H'  # La CURP usa H y M.
        for siguiente in renglones[i + 1:i + 3]:
            nombre = _nombre(siguiente)
            if nombre:
                datos['apellidos'], datos['nombres'] = nombre
                datos['nombre'] = ' '.join(nombre[1] + nombre[0])
                break
        if datos['nacimiento_valido'] or datos['vigencia_valida'] or 'nombre' in datos:
            return datos
    return None
