"""Lo que se cuenta de cada alumno con los datos del estándar (validacion/estandar.py): lo que pide el 911, su salud,
domicilio y boletas.

Lo usan el análisis de la PC 4 (pandas), el Excel por grado del servidor y el motor de documentos, para que todos
cuenten igual. Son reglas fijas, sin IA.

- Discapacidad y condiciones: los tipos fijos que pide el cuestionario 911.3.
- Edad para el 911: años cumplidos al 1 de septiembre del ciclo.
- Lugar de nacimiento: la entidad que trae la CURP (posiciones 12 y 13; NE es nacido en el extranjero).
- Repite el grado, de dónde viene, beca, lengua indígena y afromexicano: los pone la escuela (911.3).
- Salud general del certificado médico (salud_general): peso, estatura, IMC y estado nutricional con las tablas de la
  OMS (validacion/oms.py, como "Vive saludable"), tipo de sangre, vista, oído, dientes, vacunas, educación física y
  servicio médico, cada uno en pocas clases fijas, y una frase con cómo está en general y lo que hay que atender.
"""
import datetime
import re
import unicodedata

from validacion import oms


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










# ---------------------------------------------------------------- Salud general (certificado médico)

NUTRICION = oms.CLASES
SANGRE = ('O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-')
VISTA = ('Normal', 'Usa lentes', 'Necesita valoración')
AUDICION = ('Normal', 'Usa aparato auditivo', 'Necesita valoración')
BUCAL = ('Sana', 'Necesita dentista')
VACUNAS = ('Completas', 'Incompletas')
EDUCACION_FISICA = ('Apto', 'Apto con cuidados', 'No apto')
SERVICIOS = (('IMSS-Bienestar', r'BIENESTAR|INSABI|SEGURO POPULAR'), ('IMSS', r'\bIMSS\b|SEGURO SOCIAL'), ('ISSSTE', r'ISSSTE'),
             ('ISSEMYM', r'ISSEMYM'), ('Pemex', r'PEMEX'), ('Sedena o Semar', r'SEDENA|SEMAR|MILITAR|MARINA'),
             ('Particular', r'PARTICULAR|PRIVAD|GASTOS MEDICOS'), ('Ninguno', r'(NINGUN\w*|NO|NO TIENE|NO CUENTA\b.*|SIN\b.*|N/A|NA)'))
# Un rango que puede tener un niño de primaria (con extraedad): lo de fuera es una lectura equivocada o "peso al nacer".
MEDIDAS = {'peso': (8.0, 120.0), 'talla': (0.7, 2.0)}
# "Sin caries", "No presenta alteraciones": lo negado no cuenta como problema.
NEGADO = re.compile(r'\b(?:SIN|NO (?:PRESENTA|TIENE|SE OBSERVAN?|HAY|REFIERE|USA)|NIEGA|AUSENCIA DE|NEGATIV[OA] A)\s+\w+')


def _sin_negado(texto):
    return NEGADO.sub(' ', texto)


def medida(campo, texto):
    """El peso en kg o la estatura en metros, como texto ("22.5", "1.18"); None si no es una medida de un niño.
    La estatura puede venir en centímetros ("118 cm") y el peso en gramos."""
    crudo = str(texto or '').replace(',', '.')
    hallado = re.search(r'\d+(?:\.\d+)?', crudo)
    if not hallado or campo not in MEDIDAS:
        return None
    valor, resto = float(hallado[0]), normal(crudo[hallado.end():])
    if campo == 'talla' and (valor > 3 or re.match(r'CM|CENTIM', resto)):
        valor /= 100
    if campo == 'peso' and re.match(r'(G|GR|GRS|GRAMOS)\b', resto) and valor > 1000:
        valor /= 1000
    if campo == 'peso' and re.match(r'(LB|LIBRA)', resto):
        return None
    bajo, alto = MEDIDAS[campo]
    if not bajo <= valor <= alto:
        return None
    return f'{valor:.2f}' if campo == 'talla' else f'{valor:.1f}'.rstrip('0').rstrip('.')


def sangre(texto):
    valor = normal(texto).replace(' ', '').replace('POSITIVO', '+').replace('NEGATIVO', '-').replace('RH', '')
    hallado = re.search(r'(AB|A|B|O|0)([+-])', valor)
    if not hallado:
        return None
    tipo = ('O' if hallado[1] == '0' else hallado[1]) + hallado[2]
    return tipo if tipo in SANGRE else None


def vista(agudeza, lentes=None):
    """Normal, usa lentes o necesita valoración (20/20 a 20/25 es normal)."""
    if si_no(lentes) == 'sí':
        return 'Usa lentes'
    texto = normal(agudeza)
    if not texto:
        return None
    limpio = _sin_negado(texto)
    if re.search(r'LENTES|ANTEOJOS|GAFAS', limpio):
        return 'Usa lentes'
    snellen = [int(x) for x in re.findall(r'20 ?/ ?(\d{2,3})', texto)]
    if snellen:
        return 'Normal' if max(snellen) <= 25 else 'Necesita valoración'
    if re.search(r'MIOP|ASTIGM|HIPERMET|DISMINU|\bBAJA\b|DEFICI|ESTRABISM|AMBLIOP|VALORA|OFTALM|OPTOM|ALTERAD|ANORMAL', limpio):
        return 'Necesita valoración'
    if re.search(r'NORMAL|BUEN|ADECUAD|SIN ALTERA|CONSERVAD', texto):
        return 'Normal'
    return None


def audicion(texto):
    texto = normal(texto)
    if not texto:
        return None
    limpio = _sin_negado(texto)
    if re.search(r'APARATO|AUXILIAR AUDITIVO|IMPLANTE', limpio):
        return 'Usa aparato auditivo'
    if re.search(r'HIPOACUS|SORD|DISMINU|\bBAJA\b|DEFICI|ALTERAD|ANORMAL|VALORA|OTORRINO|AUDIOMETR|TAPON|OTITIS', limpio):
        return 'Necesita valoración'
    if re.search(r'NORMAL|BUEN|ADECUAD|SIN ALTERA|CONSERVAD|INTEGR', texto):
        return 'Normal'
    return None


def bucal(texto):
    texto = normal(texto)
    if not texto:
        return None
    limpio = _sin_negado(texto)
    if re.search(r'CARIES|CARIAD|GINGIVI|SARRO|MALOCLU|TRATAMIENTO|DENTISTA|ODONTOLOG|CURACION|DEFICIENTE|MALA', limpio):
        return 'Necesita dentista'
    if re.search(r'SAN[OA]|BUEN|NORMAL|ADECUAD|SIN CARIES|SIN ALTERA|LIMPI', texto):
        return 'Sana'
    return None


def vacunas(texto):
    texto = normal(texto)
    if re.search(r'INCOMPLET|FALTA|PENDIENTE|ATRASAD|NO COMPLET', texto):
        return 'Incompletas'
    if re.search(r'COMPLET|AL CORRIENTE|AL DIA', texto):
        return 'Completas'
    return None


def nutricion_del_medico(texto):
    texto = normal(texto)
    for clase, patron in (('Obesidad', r'OBES'), ('Sobrepeso', r'SOBREPESO'), ('Delgadez', r'DESNUTRI|BAJO (DE )?PESO|DELGAD|PESO BAJO'),
                          ('Peso normal', r'NORMAL|ADECUAD|EUTROF|BUEN')):
        if re.search(patron, texto):
            return clase
    return None


def educacion_fisica(texto):
    """Si puede hacer educación física: apto, apto con cuidados (con restricciones) o no apto."""
    texto = normal(texto)
    if not texto:
        return None
    if re.search(r'NO APT[OA]|NO PUEDE|NO DEBE REALIZAR|CONTRAINDICAD|EXENT|SUSPEND|NO REALIZA', texto) or texto in ('NO', 'N'):
        return 'No apto'
    if re.search(r'RESTRICCI|CON CUIDADO|PRECAUCI|MODERAD|LIMITAD|EXCEPTO|SIN ESFUERZO|NO DEBE', _sin_negado(texto)):
        return 'Apto con cuidados'
    if re.search(r'\bAPT[OA]\b|PUEDE|SIN RESTRICCI|NORMAL|SAN[OA]', texto) or texto in ('SI', 'S', 'X'):
        return 'Apto'
    return None


def servicio(texto):
    texto = normal(texto)
    return next((nombre for nombre, patron in SERVICIOS if re.fullmatch(patron, texto) or (nombre != 'Ninguno' and re.search(patron, texto))),
                None) if texto else None


def es_sano(texto):
    """Lo que concluyó el médico dice que el alumno está sano ("Clínicamente sano", "En buen estado de salud")."""
    texto = normal(texto)
    return bool(re.search(r'(?<!NO )\bSAN[OA]\b|SALUDABLE|BUEN ESTADO|SIN PATOLOG|SIN ALTERACION|\bNORMAL\b', texto))


# El campo de sidp.dato y cómo se resume cada uno (lo usa taller.py para ver si dos lecturas dicen lo mismo).
CLASES = {'agudeza_visual': vista, 'audicion': audicion, 'salud_bucal': bucal, 'vacunas': vacunas, 'educacion_fisica': educacion_fisica,
          'estado_nutricional': nutricion_del_medico, 'servicio_medico': servicio, 'usa_lentes': lambda t: si_no(t),
          'estado_general': lambda t: 'Sano' if es_sano(t) else None}


def misma_clase(campo, uno, otro):
    """Dos lecturas de un dato de salud que dicen lo mismo con otras palabras ("20/20 ambos ojos" y "20/20")."""
    clase = CLASES.get(campo)
    return bool(clase) and clase(uno) is not None and clase(uno) == clase(otro)


# Lo que la ficha del alumno muestra en «Estado de salud» (base_cerebro.expediente_alumno).
CLAVES_SALUD = ('peso', 'talla', 'imc', 'z_imc', 'nutricion', 'nutricion_segun', 'tipo_sangre', 'vista', 'agudeza_visual', 'audicion',
                'bucal', 'vacunas', 'educacion_fisica', 'servicio_medico', 'fecha_certificado', 'estado_general', 'sano', 'recomendaciones',
                'con_certificado', 'atender', 'resumen')
ATENDER_NUTRICION = {'Delgadez severa': 'delgadez severa para su edad', 'Delgadez': 'delgadez para su edad',
                     'Sobrepeso': 'sobrepeso para su edad', 'Obesidad': 'obesidad para su edad'}


SIGLAS = {'TDAH', 'TEA', 'VIH', 'SIDA', 'IMSS', 'ISSSTE', 'DIF', 'NEE'}


def _minusculas(texto):
    """PENICILINA -> penicilina, pero TDAH sigue en mayúsculas (para la frase de cómo está)."""
    return ' '.join(p if p.upper() in SIGLAS else p.lower() for p in str(texto).split())


def salud_general(datos, sexo=None, nacimiento=None, hoy=None, cuidar=None):
    """El estado de salud del alumno según su certificado médico, con datos exactos y en general.

    cuidar: {'alergias', 'padecimientos', 'medicamentos', 'discapacidades'} ya contados (de_alumno), para la frase.
    Lo por confirmar no cuenta (indicadores.valores_de): un peso o una vista mal leídos no llegan a los formatos.
    """
    hoy = hoy or datetime.date.today()
    nacimiento = fecha(nacimiento)
    uno = lambda campo: _uno(datos, 'salud', campo)  # noqa: E731
    peso, talla = medida('peso', uno('peso')), medida('talla', uno('talla'))
    medido = fecha(uno('fecha_certificado'))
    medido = medido if medido and medido <= hoy and (not nacimiento or medido > nacimiento) else None
    oms_ = oms.estado_nutricional(peso, talla, sexo, nacimiento, medido or hoy) if peso and talla and sexo in ('H', 'M') else None
    medico = uno('estado_nutricional')
    nutricion, segun = (oms_['clase'], 'OMS') if oms_ and oms_['clase'] else (nutricion_del_medico(medico), 'médico') if nutricion_del_medico(medico) \
        else (None, None)
    general = uno('estado_general')
    salida = {
        'peso': float(peso) if peso else None, 'talla': float(talla) if talla else None,
        'imc': oms_['imc'] if oms_ else oms.imc(peso, talla) if peso and talla else None, 'z_imc': oms_['z'] if oms_ else None,
        'nutricion': nutricion, 'nutricion_segun': segun, 'tipo_sangre': sangre(uno('tipo_sangre')),
        'vista': vista(uno('agudeza_visual'), uno('usa_lentes')), 'agudeza_visual': uno('agudeza_visual'),
        'audicion': audicion(uno('audicion')), 'bucal': bucal(uno('salud_bucal')), 'vacunas': vacunas(uno('vacunas')),
        'educacion_fisica': educacion_fisica(uno('educacion_fisica')), 'servicio_medico': servicio(uno('servicio_medico')),
        'fecha_certificado': medido.isoformat() if medido else None, 'estado_general': general, 'sano': es_sano(general) if general else None,
        'recomendaciones': uno('recomendaciones'),
    }
    salida['con_certificado'] = any(salida[k] for k in ('peso', 'talla', 'tipo_sangre', 'vista', 'audicion', 'bucal', 'vacunas',
                                                         'educacion_fisica', 'fecha_certificado', 'estado_general', 'nutricion'))
    cuidar = cuidar or {}
    atender = [ATENDER_NUTRICION[nutricion]] if nutricion in ATENDER_NUTRICION else []
    atender += ['valoración de la vista'] if salida['vista'] == 'Necesita valoración' else []
    atender += ['valoración del oído'] if salida['audicion'] == 'Necesita valoración' else []
    atender += ['atención dental'] if salida['bucal'] == 'Necesita dentista' else []
    atender += ['completar sus vacunas'] if salida['vacunas'] == 'Incompletas' else []
    atender += {'No apto': ['no hace educación física'], 'Apto con cuidados': ['educación física con cuidados']}.get(salida['educacion_fisica'], [])
    atender += [f'alergia a {_minusculas(a)}' for a in cuidar.get('alergias') or []]
    atender += [_minusculas(p) for p in cuidar.get('padecimientos') or []]
    atender += [f'toma {_minusculas(m)}' for m in cuidar.get('medicamentos') or []]
    atender += [_minusculas(d) for d in cuidar.get('discapacidades') or [] if _minusculas(d).lower() not in ' '.join(atender).lower()]
    salida['atender'] = atender
    salida['resumen'] = resumen_salud(salida, atender)
    return salida


def resumen_salud(s, atender):
    """Cómo está en general, en una frase formal: lo que concluyó el médico, lo que requiere atención y lo que conviene saber."""
    if not s['con_certificado'] and not atender:
        return 'Sin datos del certificado médico.'
    partes = []
    if s['sano']:
        partes.append('Sano según el médico')
    elif s['estado_general']:
        partes.append(f'El médico anota: {s["estado_general"].lower()}')
    partes.append('Requiere atención: ' + ', '.join(atender) if atender else 'Sin nada que atender')
    tiene = [t for t, si in (('usa lentes', s['vista'] == 'Usa lentes'), ('usa aparato auditivo', s['audicion'] == 'Usa aparato auditivo')) if si]
    if tiene:
        partes.append(' y '.join(tiene))
    return '. '.join(p[0].upper() + p[1:] for p in partes) + '.'


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
    """Los valores vigentes (o por confirmar si no hay otros) de un campo del expediente de la PC 4.

    En salud, lo por confirmar no cuenta: una enfermedad que la lectura no aseguró (una "hipertensión" que era una opción
    impresa sin marcar) no sale en los formatos hasta que una persona la confirma viendo la hoja."""
    filas = [d for d in (datos or {}).get(categoria, []) if d.get('campo') == campo and str(d.get('valor') or '').strip()
             and d.get('estado') not in ('descartado', 'reemplazado')]
    vigentes = [d for d in filas if d.get('estado') != 'por_confirmar'] or ([] if categoria == 'salud' else filas)
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
    tipos = discapacidades(valores_de(datos, 'salud', 'discapacidad'), padecimientos)
    salud = salud_general(datos, sexo, nacimiento, hoy, {'alergias': alergias, 'padecimientos': padecimientos, 'medicamentos': medicamentos,
                                                        'discapacidades': tipos})
    return {
        **salud, 'edad': edad_al(nacimiento, hoy) if nacimiento else None,
        'grado': int(grado) if grado else None, 'sexo': sexo if sexo in ('H', 'M') else None, 'edad_911': edad, 'columna_911': columna_911(edad),
        'entidad': ENTIDADES.get(entidad) if entidad else None,
        'nacido': None if not entidad or entidad not in ENTIDADES else 'Estado de México' if entidad == ENTIDAD_ESCUELA
        else 'Otro país' if entidad == 'NE' else 'Otra entidad',
        'alergias': alergias, 'padecimientos': padecimientos, 'medicamentos': medicamentos,
        'discapacidades': tipos,
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
