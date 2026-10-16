"""Los campos de cada documento: qué datos se esperan, cómo se leen y cómo se dejan útiles.

Una plantilla dice qué campos trae su documento (por ejemplo, la ficha de inscripción trae "Teléfono de la
madre" y "Alergias"). Cada campo tiene:

    {'clave': 'telefono_madre', 'etiqueta': 'Teléfono de la madre', 'tipo': 'telefono',
     'categoria': 'contacto', 'campo': 'telefono', 'de': 'madre'}

- tipo: cómo se limpia y se revisa el valor (TIPOS): un teléfono queda en 10 dígitos, una fecha en AAAA-MM-DD,
  un tipo de sangre como "O+", una CURP se revisa con su dígito verificador.
- categoria y campo: a dónde va en la base de la PC 4 (tabla sidp.dato), para que el expediente lo muestre junto
  con lo que salió de otros documentos.

Los documentos ya se revisaron en papel: aquí no se valida, se copian sus datos. El modelo que ve (vision.py) lee
la hoja con la lista de campos de la plantilla; luego estas reglas fijas limpian cada valor y le ponen confianza:
alta (proceso fijo o coincide con otro dato), media (el modelo lo leyó y pasa las reglas) o baja (por confirmar).
"""
import datetime
import re
import unicodedata

from validacion import comparador

TIPOS = {
    'texto': 'Texto', 'nombre': 'Nombre de una persona', 'fecha': 'Fecha', 'curp': 'CURP', 'telefono': 'Teléfono',
    'correo': 'Correo electrónico', 'domicilio': 'Domicilio', 'cp': 'Código postal', 'sangre': 'Tipo de sangre',
    'si_no': 'Sí o no', 'numero': 'Número (peso, talla, promedio)', 'lista': 'Lista (alergias, medicamentos)',
}
CATEGORIAS = {
    'alumno': 'Datos del alumno', 'salud': 'Salud', 'contacto': 'Medios de contacto', 'domicilio': 'Domicilio',
    'madre': 'Madre', 'padre': 'Padre', 'tutor': 'Tutor', 'escolar': 'Escolar', 'otro': 'Otros datos',
}
DE = ('', 'alumno', 'madre', 'padre', 'tutor', 'emergencia', 'otro')
DE_NOMBRES = {'': '—', 'alumno': 'Alumno', 'madre': 'Madre', 'padre': 'Padre', 'tutor': 'Tutor', 'emergencia': 'Contacto de emergencia',
              'otro': 'Otra persona'}
VARIOS = {'telefono', 'correo', 'alergia', 'padecimiento', 'medicamento'}  # Campos que pueden tener varios valores.
# Lo que ya está en la ficha del alumno (lista oficial): solo se compara, no se guarda otra vez.
IDENTIDAD = {'curp', 'nombre', 'nombres', 'primer_apellido', 'segundo_apellido', 'fecha_nacimiento', 'sexo'}


def campo(clave, etiqueta, tipo, categoria, nombre=None, de=''):
    return {'clave': clave, 'etiqueta': etiqueta, 'tipo': tipo, 'categoria': categoria, 'campo': nombre or clave, 'de': de}


# Los documentos que trae el sistema, con lo que se espera de cada uno.
FABRICA = {
    'acta_alumno': [
        campo('curp', 'CURP del alumno', 'curp', 'alumno'),
        campo('nombres', 'Nombre(s) del alumno', 'nombre', 'alumno'),
        campo('primer_apellido', 'Primer apellido del alumno', 'nombre', 'alumno'),
        campo('segundo_apellido', 'Segundo apellido del alumno', 'nombre', 'alumno'),
        campo('fecha_nacimiento', 'Fecha de nacimiento', 'fecha', 'alumno'),
        campo('lugar_nacimiento', 'Lugar de nacimiento (municipio y estado)', 'texto', 'alumno'),
        campo('nombre_madre', 'Nombre completo de la madre', 'nombre', 'madre', 'nombre'),
        campo('curp_madre', 'CURP de la madre', 'curp', 'madre', 'curp'),
        campo('nombre_padre', 'Nombre completo del padre', 'nombre', 'padre', 'nombre'),
        campo('curp_padre', 'CURP del padre', 'curp', 'padre', 'curp'),
    ],
    'certificado_medico': [
        campo('tipo_sangre', 'Tipo de sangre (grupo y RH)', 'sangre', 'salud'),
        campo('alergias', 'Alergias', 'lista', 'salud', 'alergia'),
        campo('padecimientos', 'Enfermedades o padecimientos', 'lista', 'salud', 'padecimiento'),
        campo('medicamentos', 'Medicamentos que toma', 'lista', 'salud', 'medicamento'),
        campo('peso', 'Peso en kilos', 'numero', 'salud'),
        campo('talla', 'Talla o estatura en metros', 'numero', 'salud'),
        campo('apto', '¿Dice que está sano o apto para actividades escolares?', 'si_no', 'salud'),
        campo('observaciones', 'Observaciones o diagnóstico del médico', 'texto', 'salud'),
        campo('medico', 'Nombre del médico', 'nombre', 'salud'),
        campo('cedula', 'Cédula profesional del médico', 'texto', 'salud'),
        campo('fecha_certificado', 'Fecha del certificado', 'fecha', 'salud'),
    ],
    'boleta': [
        campo('grado_cursado', 'Grado que cursó', 'texto', 'escolar'),
        campo('ciclo_boleta', 'Ciclo escolar de la boleta', 'texto', 'escolar'),
        campo('promedio', 'Promedio final', 'numero', 'escolar'),
        campo('escuela_procedencia', 'Nombre de la escuela', 'texto', 'escolar'),
        campo('cct_procedencia', 'Clave de la escuela (CCT)', 'texto', 'escolar'),
    ],
    'ine_tutor': [
        campo('nombre_tutor', 'Nombre completo', 'nombre', 'tutor', 'nombre'),
        campo('curp_tutor', 'CURP', 'curp', 'tutor', 'curp'),
        campo('domicilio_ine', 'Domicilio', 'domicilio', 'domicilio', 'domicilio'),
        campo('vigencia_ine', 'Vigencia', 'texto', 'tutor', 'vigencia_ine'),
    ],
    'acta_tutor': [
        campo('nombre_tutor', 'Nombre completo de la persona registrada', 'nombre', 'tutor', 'nombre'),
        campo('curp_tutor', 'CURP de la persona registrada', 'curp', 'tutor', 'curp'),
        campo('nacimiento_tutor', 'Fecha de nacimiento', 'fecha', 'tutor', 'fecha_nacimiento'),
    ],
    'comprobante': [
        campo('domicilio', 'Domicilio del servicio', 'domicilio', 'domicilio'),
        campo('cp', 'Código postal', 'cp', 'domicilio'),
        campo('titular', 'Nombre del titular', 'nombre', 'domicilio'),
        campo('fecha_comprobante', 'Fecha del recibo o periodo', 'fecha', 'domicilio'),
    ],
}

# Para proponer a dónde va un campo nuevo según su etiqueta (la plantilla de la escuela). Lo primero que coincide.
PISTAS = [
    (r'CORREO|E-?MAIL', 'correo', 'contacto', 'correo'),
    (r'CELULAR|TEL[EÉ]FONO|TEL\b|WHATS', 'telefono', 'contacto', 'telefono'),
    (r'C\.?\s*P\b|C[OÓ]DIGO POSTAL', 'cp', 'domicilio', 'cp'),
    (r'DOMICILIO|DIRECCI[OÓ]N|CALLE|COLONIA', 'domicilio', 'domicilio', 'domicilio'),
    (r'SANGRE|\bRH\b', 'sangre', 'salud', 'tipo_sangre'),
    (r'ALERG', 'lista', 'salud', 'alergia'),
    (r'MEDICAMENT|TRATAMIENTO', 'lista', 'salud', 'medicamento'),
    (r'ENFERMEDAD|PADECIM|CR[OÓ]NIC|DISCAPACIDAD|CONDICI[OÓ]N', 'lista', 'salud', 'padecimiento'),
    (r'\bPESO\b', 'numero', 'salud', 'peso'),
    (r'TALLA|ESTATURA', 'numero', 'salud', 'talla'),
    (r'SEGURO|IMSS|ISSSTE|AFILIACI', 'texto', 'salud', 'servicio_medico'),
    (r'CURP', 'curp', 'alumno', 'curp'),
    (r'FECHA DE NACIMIENTO|NACIMIENTO', 'fecha', 'alumno', 'fecha_nacimiento'),
    (r'FECHA', 'fecha', 'otro', 'fecha'),
    (r'OCUPACI[OÓ]N|TRABAJO|EMPLEO', 'texto', 'tutor', 'ocupacion'),
    (r'ESCOLARIDAD|ESTUDIOS', 'texto', 'tutor', 'escolaridad'),
    (r'PROMEDIO|CALIFICACI', 'numero', 'escolar', 'promedio'),
    (r'ESCUELA DE PROCEDENCIA|PROCEDENCIA', 'texto', 'escolar', 'escuela_procedencia'),
    (r'NOMBRE', 'nombre', 'alumno', 'nombre'),
]
QUIEN = [(r'MADRE|MAM[AÁ]', 'madre'), (r'PADRE|PAP[AÁ]', 'padre'), (r'TUTOR', 'tutor'), (r'EMERGENCIA|URGENCIA', 'emergencia'),
         (r'ALUMN|NIÑ|EDUCAND', 'alumno')]


def clave_de(etiqueta):
    texto = unicodedata.normalize('NFD', etiqueta.lower())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return '_'.join(re.findall(r'[a-z0-9]+', texto))[:40] or 'campo'


def proponer(etiqueta):
    """Un campo completo a partir de su etiqueta ("Teléfono de la mamá" -> contacto/telefono, de la madre)."""
    texto = unicodedata.normalize('NFC', etiqueta.upper())
    de = next((quien for patron, quien in QUIEN if re.search(patron, texto)), '')
    tipo, categoria, nombre = next(((t, c, n) for patron, t, c, n in PISTAS if re.search(patron, texto)), ('texto', 'otro', None))
    if nombre == 'nombre' and de in ('madre', 'padre', 'tutor'):
        categoria = de
    elif nombre == 'nombre' and de == 'emergencia':
        categoria, nombre = 'contacto', 'nombre_emergencia'
    elif categoria == 'tutor' and de in ('madre', 'padre'):
        categoria = de
    elif nombre == 'curp' and de in ('madre', 'padre', 'tutor'):
        categoria = de
    return campo(clave_de(etiqueta), etiqueta.strip(), tipo, categoria, nombre or clave_de(etiqueta),
                 de if categoria == 'contacto' else '')


def de_documento(tipo, plantilla=None):
    """Los campos que se esperan de un documento: los de su plantilla o, si no tiene, los de fábrica."""
    if plantilla and plantilla.get('campos'):
        return plantilla['campos']
    return FABRICA.get(tipo, [])


def revisar_campos(campos):
    """La lista de campos que escribió una persona, completa y sin repetidos. ValueError si algo no sirve."""
    salida, vistas = [], set()
    for c in campos or []:
        etiqueta = str(c.get('etiqueta') or '').strip()
        if not etiqueta:
            continue
        base = proponer(etiqueta)
        tipo = c.get('tipo') if c.get('tipo') in TIPOS else base['tipo']
        categoria = c.get('categoria') if c.get('categoria') in CATEGORIAS else base['categoria']
        nombre = clave_de(c.get('campo') or base['campo'])
        clave = clave_de(c.get('clave') or etiqueta)
        while clave in vistas:
            clave = clave[:37] + f'_{len(vistas)}'
        vistas.add(clave)
        de = c.get('de') if c.get('de') in DE else base['de']
        salida.append(campo(clave, etiqueta[:80], tipo, categoria, nombre, de))
    if len(salida) > 60:
        raise ValueError('Una plantilla puede tener hasta 60 campos')
    return salida


# ---------------------------------------------------------------- Limpiar cada valor según su tipo

MESES = {m: i for i, m in enumerate(('ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE',
                                     'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'), 1)}
MESES.update({m[:3]: i for m, i in list(MESES.items())})
MESES['SETIEMBRE'] = 9
ROMANOS = {r: i for i, r in enumerate(('I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'), 1)}
VACIOS = {'', 'NINGUNO', 'NINGUNA', 'NO', 'N/A', 'NA', 'S/D', 'SIN', 'NEGADO', 'NEGADAS', 'NEGA', '-', '--', '?', 'NULL', 'NONE'}


def _mayus(texto):
    return re.sub(r'\s+', ' ', str(texto or '').upper()).strip(' .,;:')


def fecha(texto, hoy=None):
    """'14/03/2018', '14-III-2018', '14 de marzo de 2018' o '2018-03-14' -> '2018-03-14'; None si no se entiende."""
    t = _mayus(texto).replace(' DEL ', ' DE ')
    hoy = hoy or datetime.date.today()
    if m := re.search(r'\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b', t):
        a, me, d = int(m[1]), int(m[2]), int(m[3])
    elif m := re.search(r'\b(\d{1,2})[-/.\s]+([IVX]{1,4})[-/.\s]+(\d{2,4})\b', t):  # 14-III-2018
        d, me, a = int(m[1]), ROMANOS.get(m[2]), int(m[3])
        if not me:
            return None
    elif m := re.search(r'\b(\d{1,2})\s*(?:DE\s*)?([A-Z]{3,10})\.?\s*(?:DE\s*)?(\d{2,4})\b', t):
        d, me, a = int(m[1]), MESES.get(m[2]) or MESES.get(m[2][:3]), int(m[3])
        if not me:
            return None
    elif m := re.search(r'\b(\d{1,2})[-/.\s](\d{1,2})[-/.\s](\d{2,4})\b', t):
        d, me, a = int(m[1]), int(m[2]), int(m[3])
    else:
        return None
    if a < 100:
        a += 2000 if a <= hoy.year % 100 else 1900
    try:
        valor = datetime.date(a, me, d)
    except ValueError:
        return None
    return valor.isoformat() if datetime.date(1900, 1, 1) <= valor <= hoy + datetime.timedelta(days=400) else None


def telefono(texto):
    digitos = re.sub(r'\D', '', str(texto or '').upper().replace('O', '0').replace('L', '1').replace('S', '5'))
    if len(digitos) == 12 and digitos.startswith('52'):
        digitos = digitos[2:]
    if len(digitos) == 13 and digitos.startswith('521'):
        digitos = digitos[3:]
    return digitos if len(digitos) == 10 else None


def correo(texto):
    t = str(texto or '').strip().lower().replace(' ', '').replace('(at)', '@').replace('[at]', '@')
    t = re.sub(r'@(gmai|gmial|gmal|gamil)\.', '@gmail.', t)
    t = re.sub(r'\.(con|cpm|comm|co)$', '.com', t) if not t.endswith('.com.mx') else t
    return t if re.fullmatch(r'[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+', t) else None


def sangre(texto):
    t = _mayus(texto).replace('CERO', 'O').replace('0', 'O')
    t = re.sub(r'\s+', '', t.replace('POSITIVO', '+').replace('NEGATIVO', '-').replace('RH', '').replace('(', '').replace(')', ''))
    m = re.search(r'(AB|A|B|O)([+-])', t)
    return f'{m[1]}{m[2]}' if m else None


def numero(texto):
    t = str(texto or '').replace(',', '.')
    m = re.search(r'\d+(?:\.\d+)?', t)
    return m[0] if m else None


def si_no(texto):
    t = _mayus(texto)
    if 'NO APTO' in t or re.match(r'^(NO|N)\b', t):
        return 'no'
    if re.match(r'^(SI|SÍ|S|X|✓)(?=\W|$)', t) or re.search(r'\b(APTO|APTA|SANO|SANA)\b', t):
        return 'sí'
    return None


def domicilio(texto):
    """El domicilio como se escribió y sus partes cuando se reconocen (calle, número, colonia, CP, municipio)."""
    t = _mayus(texto)
    if len(t) < 6:
        return None, {}
    partes = {}
    if m := re.search(r'\b(?:C\.?\s*P\.?|CP|CODIGO POSTAL)\s*:?\s*(\d{5})\b', t) or re.search(r'\b(\d{5})\b', t):
        partes['cp'] = m[1]
    if m := re.search(r'\b(?:COL\.?|COLONIA|FRACC\.?|FRACCIONAMIENTO|BARRIO|BO\.?)\s+([A-ZÑ0-9 ]+?)(?=,|\bC\.?\s*P\b|\bCP\b|\bMUN|\b\d{5}\b|$)', t):
        partes['colonia'] = m[1].strip()
    if m := re.match(r'^((?:C\.?|CALLE|AV\.?|AVENIDA|CDA\.?|CERRADA|PRIV\.?|PRIVADA|AND\.?|ANDADOR|CALZ\.?)?\s*[A-ZÑ0-9 .]+?)\s+'
                     r'(?:NO\.?|NUM\.?|#)?\s*(\d+[A-Z]?|S/?N)\b', t):
        partes['calle'], partes['numero'] = m[1].strip(' .'), m[2]
    if m := re.search(r'\b(?:MUN\.?|MUNICIPIO|MPIO\.?)\s+(?:DE\s+)?([A-ZÑ ]+?)(?=,|\.|\bEDO|\bESTADO|$)', t):
        partes['municipio'] = m[1].strip()
    return t, partes


def lista(texto):
    t = _mayus(texto)
    if t in VACIOS or re.fullmatch(r'(NO|NINGUN[OA]?S?|NEGAD[OA]S?|SIN) ?.*', t) and len(t) < 25:
        return []
    return [p.strip(' .') for p in re.split(r',|;|/|\bY\b|\n', t) if p.strip(' .') and p.strip(' .') not in VACIOS][:10]


def limpiar(tipo, valor, hoy=None):
    """(valor útil o None, detalle). None quiere decir que no pasó las reglas de su tipo (queda por confirmar)."""
    crudo = str(valor or '').strip()
    if tipo == 'telefono':
        return telefono(crudo), {}
    if tipo == 'correo':
        return correo(crudo), {}
    if tipo == 'fecha':
        return fecha(crudo, hoy), {}
    if tipo == 'curp':
        curp = re.sub(r'[^A-Z0-9]', '', crudo.upper())
        return (curp if comparador.desglose_curp(curp) else None), {}
    if tipo == 'cp':
        m = re.search(r'\b\d{5}\b', crudo)
        return (m[0] if m else None), {}
    if tipo == 'sangre':
        return sangre(crudo), {}
    if tipo == 'numero':
        return numero(crudo), {}
    if tipo == 'si_no':
        return si_no(crudo), {}
    if tipo == 'domicilio':
        texto, partes = domicilio(crudo)
        return texto, partes
    if tipo == 'nombre':
        nombre = re.sub(r'[^A-ZÑÁÉÍÓÚÜ ]', ' ', crudo.upper())
        nombre = re.sub(r'\s+', ' ', nombre).strip()
        nombre = re.sub(r'^(?:(?:DR|DRA|LIC|PROF|PROFA|ING|SR|SRA|SRITA|C)\s+)+', '', nombre)  # "Dra. Rosa..." -> "ROSA...".
        return (nombre if len(nombre) >= 2 else None), {}
    texto = _mayus(crudo)
    return (texto or None), {}


def vacio(valor):
    return _mayus(valor) in VACIOS


def _palabras(texto):
    texto = unicodedata.normalize('NFD', str(texto or '').upper())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return re.findall(r'[A-Z0-9@._-]+', texto)


def de_texto(texto, campos, hoy=None):
    """En una hoja impresa o escrita a máquina: el valor que está junto a la etiqueta de cada campo, si pasa las reglas.

    Busca el renglón que trae las palabras de la etiqueta ("TELEFONO DE LA MADRE: 722 123 4567") y toma lo que sigue;
    si no sigue nada, el renglón de abajo. Con letra a mano el OCR casi nunca da algo que pase las reglas: ahí lee el
    modelo que ve.
    """
    renglones = [r for r in str(texto or '').splitlines() if r.strip()]
    salida = {}
    for c in campos:
        clave_palabras = [p for p in _palabras(c['etiqueta']) if len(p) >= 4][:5]
        if not clave_palabras:
            continue
        necesarias = len(clave_palabras) if len(clave_palabras) <= 3 else -(-len(clave_palabras) * 3 // 4)
        de_quien = set(clave_palabras) & QUIENES
        for i, renglon in enumerate(renglones):
            palabras = _palabras(renglon)
            if sum(1 for p in clave_palabras if p in palabras) < necesarias:
                continue
            if (set(palabras) & QUIENES) - de_quien:  # "Teléfono del padre" no es el renglón de la madre.
                continue
            ultima = max(j for j, p in enumerate(palabras) if p in clave_palabras)
            resto = ' '.join(renglon.split(':', 1)[1:]).strip() if ':' in renglon else ''
            resto = resto or ' '.join(_palabras_originales(renglon)[ultima + 1:])
            for candidato in (resto, renglones[i + 1] if i + 1 < len(renglones) else ''):
                limpio, _ = limpiar(c['tipo'], candidato, hoy) if candidato.strip() else (None, {})
                if limpio and c['tipo'] not in ('texto', 'nombre', 'lista', 'domicilio'):
                    salida[c['clave']] = candidato.strip()
                    break
            if c['clave'] in salida:
                break
    return salida


QUIENES = {'MADRE', 'PADRE', 'MAMA', 'PAPA', 'TUTOR', 'TUTORA', 'EMERGENCIA', 'ALUMNO', 'ALUMNA', 'MEDICO'}


def _palabras_originales(renglon):
    return re.findall(r'\S+', renglon)


# ---------------------------------------------------------------- Lo que se le pide al modelo que ve

def pregunta(nombre_documento, campos):
    renglones = '\n'.join(f'- {c["clave"]}: {c["etiqueta"]}' for c in campos)
    return (f'Hoja: {nombre_documento}. Copia cada campo tal como está escrito en la hoja, incluida la letra a mano. '
            'Si el campo no aparece, deja el valor vacío. Si no se entiende bien, escribe lo que más se parezca y pon ? '
            f'al final. No inventes datos.\nCampos:\n{renglones}')


def esquema(campos):
    return {'type': 'object', 'properties': {c['clave']: {'type': 'string'} for c in campos}, 'required': [c['clave'] for c in campos]}


PROPONER = ('Esta hoja es un formato o documento escolar. Lista los campos que se llenan o que trae con datos de una persona '
            '(por ejemplo "Nombre del alumno", "Teléfono de la madre", "Alergias", "Tipo de sangre", "Domicilio"). Escribe '
            'cada campo con la etiqueta como aparece impresa en la hoja. No copies los datos de nadie: solo las etiquetas.')
ESQUEMA_PROPONER = {'type': 'object', 'properties': {'campos': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['campos']}
