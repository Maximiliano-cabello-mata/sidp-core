"""Lo que se cuenta de cada alumno con los datos del estándar (validacion/estandar.py): lo que pide el 911, salud
mínima, domicilio y boletas.

Lo usan el análisis de la PC 4 (pandas), el Excel por grado del servidor y el motor de documentos, para que todos
cuenten igual. Son reglas fijas, sin IA.

- Discapacidad y condiciones: los tipos fijos que pide el cuestionario 911.3.
- Edad para el 911: años cumplidos al 1 de septiembre del ciclo.
- Lugar de nacimiento: la entidad que trae la CURP (posiciones 12 y 13; NE es nacido en el extranjero).
- Repite el grado, de dónde viene, beca, lengua indígena y afromexicano: los pone la escuela (911.3).
"""
import datetime
import re
import unicodedata


ENTIDADES = {
    'AS': 'Aguascalientes', 'BC': 'Baja California', 'BS': 'Baja California Sur', 'CC': 'Campeche', 'CL': 'Coahuila',
    'CM': 'Colima', 'CS': 'Chiapas', 'CH': 'Chihuahua', 'DF': 'Ciudad de México', 'DG': 'Durango', 'GT': 'Guanajuato',
    'GR': 'Guerrero', 'HG': 'Hidalgo', 'JC': 'Jalisco', 'MC': 'Estado de México', 'MN': 'Michoacán', 'MS': 'Morelos',
    'NT': 'Nayarit', 'NL': 'Nuevo León', 'OC': 'Oaxaca', 'PL': 'Puebla', 'QT': 'Querétaro', 'QR': 'Quintana Roo',
    'SP': 'San Luis Potosí', 'SL': 'Sinaloa', 'SR': 'Sonora', 'TC': 'Tabasco', 'TS': 'Tamaulipas', 'TL': 'Tlaxcala',
    'VZ': 'Veracruz', 'YN': 'Yucatán', 'ZS': 'Zacatecas', 'NE': 'Nacido en el extranjero',
}
ENTIDAD_ESCUELA = 'MC'
EDADES_911 = ('Menos de 6', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15 y más')
# El cuestionario 911.3 (2026-2027) pide estos tipos, por grado y sexo. El orden importa: lo más específico primero.
DISCAPACIDAD_911 = (
    ('Sordoceguera', r'SORDOCEG'), ('Baja visión', r'BAJA VISION|DEBILIDAD VISUAL'), ('Ceguera', r'CEGUERA|CIEG[OA]|INVIDENTE'),
    ('Hipoacusia', r'HIPOACUS'), ('Sordera', r'SORDERA|SORD[OA]\b'),
    ('Discapacidad múltiple', r'MULTIPLE'), ('Discapacidad motriz', r'MOTRI|MOTORA|PARALISIS|SILLA DE RUEDAS|AMPUTA|ESPINA BIFIDA'),
    ('Discapacidad intelectual', r'INTELECTUAL|SINDROME DE DOWN|\bDOWN\b|RETRASO MENTAL'), ('Discapacidad psicosocial', r'PSICOSOCIAL'),
    ('Trastorno del espectro autista', r'AUTIS|ESPECTRO|ASPERGER|\bTEA\b'),
    ('TDAH', r'TDAH|DEFICIT DE ATENCION|HIPERACTIV'), ('Aptitudes sobresalientes', r'SOBRESALIENTE|ALTAS CAPACIDADES|SUPERDOTA'),
)
OTRAS_CONDICIONES = 'Otras condiciones'
FORMATIVOS = (('lenguajes', 'Lenguajes'), ('saberes', 'Saberes y pensamiento científico'), ('etica', 'Ética, naturaleza y sociedades'),
              ('humano', 'De lo humano y lo comunitario'))
PROMEDIO_BAJO = 7.0  # Debajo de 7 el alumno necesita apoyo; debajo de 6 no acredita.
# Lo que escriben los médicos cuando no hay nada: "Negadas", "Ninguna", "No refiere", "Sin alergias", "Aparentemente sano".
NINGUNO = re.compile(r'(NINGUN\w*|NADA|NO\b.*|NEGAD\w*|NIEGA\w*|SIN\b.*|N ?/? ?A|NA|APARENTEMENTE SAN\w*|SAN[OA]|-+|\.+|0)')


def normal(texto):
    """Mayúsculas sin acentos ni signos raros, para contar igual "Penicilina." y "PENICILINA"."""
    texto = unicodedata.normalize('NFD', str(texto or '').upper())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return ' '.join(re.sub(r'[^A-Z0-9+/ -]+', ' ', texto).split())


def es_ninguno(texto):
    return not normal(texto) or bool(NINGUNO.fullmatch(normal(texto)))


def lista(valores):
    """Los valores que sí dicen algo, normalizados y sin repetir ("Penicilina, polvo" son dos)."""
    salida = []
    for valor in valores or []:
        for parte in re.split(r'[,;]| Y ', normal(valor)):
            parte = parte.strip(' -')
            if parte and not es_ninguno(parte) and parte not in salida:
                salida.append(parte)
    return salida


def titulo(texto):
    """CHALCO DE DIAZ COVARRUBIAS -> Chalco de Diaz Covarrubias (para mostrar)."""
    chicas = {'DE', 'DEL', 'LA', 'LAS', 'LOS', 'Y', 'EL'}
    return ' '.join(p.lower() if i and p in chicas else p.capitalize() for i, p in enumerate(normal(texto).split()))


def numero(texto):
    hallado = re.search(r'\d+(?:[.,]\d+)?', str(texto or ''))
    return float(hallado.group().replace(',', '.')) if hallado else None


def fecha(texto):
    if isinstance(texto, datetime.date):
        return texto
    try:
        return datetime.date.fromisoformat(str(texto)[:10]) if texto else None
    except ValueError:
        return None


def edad_al(nacimiento, dia):
    return dia.year - nacimiento.year - ((dia.month, dia.day) < (nacimiento.month, nacimiento.day))


def columna_911(edad):
    if edad is None:
        return None
    return EDADES_911[0] if edad < 6 else EDADES_911[-1] if edad >= 15 else str(edad)




def discapacidades(discapacidad, padecimientos=()):
    """Los tipos del 911 que corresponden a lo escrito. Un diagnóstico (TDAH, autismo) en padecimientos también cuenta."""
    tipos = []
    for texto in lista(discapacidad):
        hallado = next((t for t, patron in DISCAPACIDAD_911 if re.search(patron, texto)), OTRAS_CONDICIONES)
        if hallado not in tipos:
            tipos.append(hallado)
    for texto in lista(padecimientos):
        hallado = next((t for t, patron in DISCAPACIDAD_911 if re.search(patron, texto)), None)
        if hallado and hallado not in tipos:
            tipos.append(hallado)
    return tipos










def municipio(texto):
    """El municipio como se cuenta: sin "Municipio de", sin el estado al final."""
    texto = normal(str(texto or '').split(',')[0])
    texto = re.sub(r'^(MUNICIPIO|MPIO|MUN|ALCALDIA|DELEGACION)( DE)? ', '', texto)
    texto = re.sub(r' (ESTADO DE MEXICO|EDO MEX|EDOMEX|MEX|MEXICO)$', '', texto)
    return texto or None


def colonia(texto):
    texto = normal(texto)
    texto = re.sub(r'^(COLONIA|COL|FRACCIONAMIENTO|FRACC|BARRIO|BO|LOCALIDAD|PUEBLO|UNIDAD HABITACIONAL|U ?H)( DE)? ', '', texto)
    return texto or None


PROCEDENCIAS = ('misma', 'otra_edomex', 'otra_entidad', 'otro_pais')
BECAS = ('ninguna', 'federal', 'estatal', 'municipal', 'fundacion', 'escuela', 'particular', 'otro')


def si_no(texto):
    valor = normal(texto)
    return 'sí' if valor in ('SI', 'S', 'X') else 'no' if valor in ('NO', 'N') else None


def clave(texto, permitidas):
    valor = normal(texto).lower().replace(' ', '_')
    return valor if valor in permitidas else None


def valores_de(datos, categoria, campo):
    """Los valores vigentes (o por confirmar si no hay otros) de un campo del expediente de la PC 4."""
    filas = [d for d in (datos or {}).get(categoria, []) if d.get('campo') == campo and str(d.get('valor') or '').strip()
             and d.get('estado') != 'descartado']
    vigentes = [d for d in filas if d.get('estado') != 'por_confirmar'] or filas
    return [str(d['valor']).strip() for d in vigentes]


def _uno(datos, categoria, campo):
    valores = valores_de(datos, categoria, campo)
    return valores[-1] if valores else None


def _del_domicilio(datos, parte):
    """La colonia, el municipio o el CP: su propio campo o, si no, lo que se separó del domicilio completo."""
    directo = _uno(datos, 'domicilio', parte)
    if directo:
        return directo
    for d in reversed((datos or {}).get('domicilio', [])):
        if d.get('estado') != 'descartado' and (d.get('detalle') or {}).get(parte):
            return d['detalle'][parte]
    return None


def de_alumno(datos, grado, sexo=None, nacimiento=None, curp=None, ciclo=None, hoy=None):
    """Todo lo que se cuenta de un alumno, sin su nombre ni su CURP.

    datos: {categoria: [{'campo', 'valor', 'detalle', 'estado'}]} como lo devuelve la PC 4 (/alumno?curp=).
    """
    hoy = hoy or datetime.date.today()
    nacimiento = fecha(nacimiento)
    anio = int(str(ciclo)[:4]) if ciclo and str(ciclo)[:4].isdigit() else hoy.year if hoy.month >= 8 else hoy.year - 1
    edad = edad_al(nacimiento, datetime.date(anio, 9, 1)) if nacimiento else None
    entidad = (curp or '')[11:13].upper() if curp and len(curp) == 18 else None
    alergias = lista(valores_de(datos, 'salud', 'alergia'))
    padecimientos = lista(valores_de(datos, 'salud', 'padecimiento'))
    medicamentos = lista(valores_de(datos, 'salud', 'medicamento'))
    promedios, formativos = {}, {}
    for d in (datos or {}).get('escolar', []):
        hallado = re.fullmatch(r'([a-z]+)_([1-6])', d.get('campo') or '')
        if not hallado or d.get('estado') == 'descartado':
            continue
        valor = numero(d.get('valor'))
        if valor is None or not 5 <= valor <= 10:
            continue
        grado_boleta = int(hallado[2])
        if hallado[1] == 'promedio':
            promedios[grado_boleta] = valor
        elif hallado[1] in dict(FORMATIVOS):
            formativos.setdefault(grado_boleta, {})[hallado[1]] = valor
    for grado_boleta, campos in formativos.items():  # Sin promedio escrito: el de sus campos formativos.
        if grado_boleta not in promedios and len(campos) >= 3:
            promedios[grado_boleta] = round(sum(campos.values()) / len(campos), 1)
    ultimo = max(promedios) if promedios else None
    cp = re.search(r'\b\d{5}\b', str(_del_domicilio(datos, 'cp') or ''))
    return {
        'grado': int(grado) if grado else None, 'sexo': sexo if sexo in ('H', 'M') else None, 'edad_911': edad, 'columna_911': columna_911(edad),
        'entidad': ENTIDADES.get(entidad) if entidad else None,
        'nacido': None if not entidad or entidad not in ENTIDADES else 'Estado de México' if entidad == ENTIDAD_ESCUELA
        else 'Otro país' if entidad == 'NE' else 'Otra entidad',
        'alergias': alergias, 'padecimientos': padecimientos, 'medicamentos': medicamentos,
        'discapacidades': discapacidades(valores_de(datos, 'salud', 'discapacidad'), padecimientos),
        'repite': si_no(_uno(datos, 'escolar', 'repite_grado')), 'procedencia': clave(_uno(datos, 'escolar', 'procedencia'), PROCEDENCIAS),
        'beca': clave(_uno(datos, 'escolar', 'beca'), BECAS), 'lengua_indigena': si_no(_uno(datos, 'alumno', 'lengua_indigena')),
        'lengua': _uno(datos, 'alumno', 'lengua'), 'afro': si_no(_uno(datos, 'alumno', 'afrodescendiente')),
        'municipio': municipio(_del_domicilio(datos, 'municipio')), 'colonia': colonia(_del_domicilio(datos, 'colonia')),
        'cp': cp.group() if cp else None,
        'promedios': promedios, 'ultimo_promedio': promedios.get(ultimo), 'formativos': formativos.get(ultimo, {}),
        'con_salud': bool((datos or {}).get('salud')), 'con_domicilio': bool(_del_domicilio(datos, 'municipio') or _del_domicilio(datos, 'colonia')
                                                                              or _del_domicilio(datos, 'cp')),
        'con_boletas': bool(promedios),
    }
