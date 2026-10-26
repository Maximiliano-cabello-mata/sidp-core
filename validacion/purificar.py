"""La purificación: de todo lo que dice una hoja, solo lo que la escuela necesita.

El modelo que ve transcribe la hoja completa (frente y vuelta, cada una aparte) y el OCR o el PDF dan otro texto. Aquí,
con reglas fijas y sin IA, se sacan de esos textos:

- los teléfonos y correos de la familia, con de quién es cada uno (madre, padre, tutor o contacto de emergencia);
  los del médico, la clínica, la escuela o las líneas de atención no;
- el nombre del contacto de emergencia y su parentesco;
- lo de salud del alumno (alergias, padecimientos, medicamentos, discapacidad o condición). Lo que el médico escribió
  o marcó del alumno sí; las opciones impresas sin marcar y los antecedentes de familiares (heredofamiliares) no,
  porque un "Hipertensión [ ]" sin marcar o la diabetes del abuelo no son del niño.

Cada lectura (lo transcrito, el OCR, cada lectura del modelo) es una fuente. Un dato que sale igual en varias fuentes
es más seguro; uno que sale en una sola queda por confirmar. Las enfermedades graves siempre las confirma una persona.
"""
import difflib
import re
import unicodedata

from validacion import campos as campos_mod
from validacion import indicadores

MARCA = r'(?:[\[\(]\s*[X✓✔✗*•]\s*[\]\)]|☒|☑|✓|✔)'
CASILLA = r'(?:[\[\(]\s*[X✓✔✗*•]?\s*[\]\)]|☒|☑|☐|✓|✔)'
ETIQUETA_TEL = re.compile(r'\bTEL\w*|\bCEL\w*|\bMOVIL|WHATS\w*|CONTACTO|LLAMAR|AVISAR|EMERGENCIA|URGENCIA|\bNUM(?:ERO)?\b|\bNO\.?\s*DE\s*TEL')
# Lo que delata un teléfono que no es de la familia.
INSTITUCION = re.compile(
    r'\bDRA?\b|DOCTOR|MEDIC[OA]\b|CEDULA|CLINICA|HOSPITAL|CONSULTORIO|CENTRO DE SALUD|UNIDAD MEDICA|\bIMSS\b|ISSSTE|ISSEMYM|\bDIF\b|'
    r'SECRETARIA|GOBIERNO|ESCUELA|PRIMARIA|\bSEP\b|\bCFE\b|TELMEX|\bFAX\b|ATENCION A|QUEJAS|CITAS|\bLADA\b|WWW|HTTP|FOLIO|'
    r'\bC\.?\s?C\.?\s?T\b|\bR\.?\s?F\.?\s?C\b|CUENTA|LOCATEL|FARMACIA|LABORATORIO|SUPERVISI|ZONA ESCOLAR')
# De quién es un dato, por lo que dice junto a él. El orden importa: "padre o tutor" es del padre si no dice más.
DUENOS = (
    ('madre', r'\bMADRE\b|\bMAMA\b|\bMAMI\b|\bMATERN'),
    ('padre', r'\bPADRE\b|\bPAPA\b|\bPATERN'),
    ('tutor', r'\bTUTOR\w*'),
    ('emergencia', r'EMERGENCIA|URGENCIA|AVISAR|EN CASO DE|\bABUEL\w*|\bTI[OA]S?\b|\bHERMAN[OA]S?\b|\bPADRINO\b|\bMADRINA\b|'
                   r'\bVECIN[OA]\b|\bPRIM[OA]\b|RECOGER|AUTORIZAD'),
)
PARENTESCOS = ('ABUELA', 'ABUELO', 'TIA', 'TIO', 'HERMANA', 'HERMANO', 'MADRINA', 'PADRINO', 'VECINA', 'VECINO', 'PRIMA', 'PRIMO',
               'MAMA', 'PAPA', 'MADRE', 'PADRE', 'TUTORA', 'TUTOR')
# Títulos de la parte de la hoja que es del médico o la clínica (no el título "Certificado médico" ni el de la escuela).
TITULO_CLINICA = re.compile(r'DATOS DEL MEDICO|MEDICO (?:QUE|TRATANTE|RESPONSABLE)|UNIDAD MEDICA|CLINICA|HOSPITAL|CONSULTORIO|'
                            r'CENTRO DE SALUD|RESPONSABLE SANITARIO')
EMERGENCIA = re.compile(r'EMERGENCIA|URGENCIA|AVISAR A|EN CASO DE')
# Palabras de la etiqueta que van antes del nombre ("En caso de emergencia avisar a: ROSA...").
ETIQUETA_NOMBRE = {'EN', 'CASO', 'DE', 'EMERGENCIA', 'URGENCIA', 'AVISAR', 'A', 'LLAMAR', 'CONTACTO', 'NOMBRE', 'PERSONA', 'QUE',
                   'SE', 'LE', 'PUEDE', 'DEL', 'LA', 'EL', 'COMPLETO', 'Y', 'PARENTESCO', 'AL', 'CON', 'COMUNICARSE'}
# Palabras que nunca van en el nombre de una persona: el renglón era otra cosa ("Firma del padre o tutor").
NO_NOMBRE = {'FIRMA', 'NOMBRE', 'FECHA', 'SELLO', 'TELEFONO', 'CELULAR', 'DOMICILIO', 'OBSERVACIONES', 'ALUMNO', 'ALUMNA', 'GRADO',
             'GRUPO', 'ESCUELA', 'PRIMARIA', 'CORREO', 'CURP', 'MEDICO', 'CERTIFICADO', 'TEL', 'CEL', 'NUMERO', 'DIRECCION', 'CALLE',
             'COLONIA', 'MUNICIPIO', 'EMERGENCIA', 'URGENCIA', 'ALERGIAS', 'SANGRE', 'CICLO', 'ESCOLAR'}
CORREO = re.compile(r'[A-Z0-9._%+-]+\s?@\s?[A-Z0-9-]+(?:\s?\.\s?[A-Z0-9-]+)+', re.I)
DOMINIOS_INSTITUCION = re.compile(r'GOB\.MX$|SEP\.|IMSS|ISSSTE|SALUD|EDOMEX|ISSEMYM', re.I)

# Salud del alumno: la etiqueta dice a qué campo va. "Alergia a medicamentos" es alergia: el orden importa.
SALUD = (
    ('alergia', re.compile(r'ALERGI')),
    ('medicamento', re.compile(r'MEDICAMENT|TRATAMIENTO|TOMA ALGUN')),
    ('discapacidad', re.compile(r'DISCAPACIDAD|BARRERAS|NECESIDADES EDUCATIVAS|\bNEE\b|\bCONDICION\b')),
    ('padecimiento', re.compile(r'PADECIM|PADECE|ENFERMEDAD|PATOLOGIC|CRONIC|DIAGNOSTICO')),
)
# Antecedentes de la familia: lo que sigue no es del alumno.
FAMILIA = re.compile(r'HEREDO|FAMILIAR|\bABUEL|\bPADRES\b|\bMADRE\b|\bPADRE\b|\bMAMA\b|\bPAPA\b|MATERN|PATERN|\bHERMAN')
# Lo que la etiqueta "Diagnóstico" o "Condición" también trae y no es de lo que se saca (Solo lo necesario).
NO_SALUD = re.compile(r'NUTRICI|\bPESO\b|TALLA|\bIMC\b|AGUDEZA|VISUAL|DENTAL|BUCAL|VACUN|ESQUEMA|SANGU|\bRH\b|ACTIVIDAD FISICA|'
                      r'NO PATOLOGIC|SIGNOS VITALES|TEMPERATURA|FRECUENCIA')
# Otra sección de la hoja: termina la de antecedentes de la familia.
OTRA_SECCION = re.compile(r'PERSONALES|DEL ALUMNO|DEL PACIENTE|EXPLORACI|ALERGI|MEDICAMENT|DISCAPAC|OBSERVACI|DIAGNOSTIC|'
                          r'NO PATOLOGIC|IMPRESION|CONCLUSI|PADECIMIENTO ACTUAL')
NADA = re.compile(r'(NINGUN\w*|NADA|NO\b.*|NEGAD\w*|NIEGA\w*|SIN\b.*|N ?/? ?A|NA|APARENTEMENTE SAN\w*|CLINICAMENTE SAN\w*|SAN[OA]|'
                  r'NO REFIERE\w*|-+|\.+|0)')
# La letra a mano a veces se lee partida ("NINGU NA", "NIN GUNO").
NADA_PARTIDO = re.compile(r'NINGUN[OA]S?|NADA|NEGAD[OA]S?')
# Lo que una persona siempre confirma viendo la hoja, aunque todas las lecturas coincidan.
GRAVES = re.compile(r'HIPERTENSI|DIABET|EPILEP|CONVULS|CARDI|CORAZON|SOPLO|MENTAL|NERVIOS|PSIQUI|PSICO|DEPRESI|ANSIEDAD|ESQUIZO|'
                    r'BIPOLAR|CANCER|LEUCEMIA|TUMOR|\bVIH\b|\bSIDA\b|HEPATITIS|RENAL|RI[NÑ]ON|INSUFICIENCIA|TUBERCULOSIS|ASMA|'
                    r'AUTIS|TDAH|DEFICIT|HIPERACTIV|PARALISIS|DOWN')


def normal(texto):
    """Mayúsculas sin acentos; deja números, @ y los signos que sirven para leer un formato."""
    texto = unicodedata.normalize('NFD', str(texto or '').upper())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


def renglones(texto):
    return [r.strip() for r in str(texto or '').splitlines() if r.strip() and not re.fullmatch(r'-{2,}.*-{2,}', r.strip())]


def es_ninguno(texto):
    t = ' '.join(re.sub(r'[^A-Z0-9/ -]+', ' ', normal(texto)).split())
    return not t or bool(NADA.fullmatch(t) or NADA_PARTIDO.fullmatch(t.replace(' ', '')))


def es_grave(texto):
    return bool(GRAVES.search(normal(texto)))


def parecido(a, b, minimo=0.85):
    """Dos lecturas de lo mismo: iguales sin acentos ni signos, una dentro de la otra o casi iguales."""
    a, b = indicadores.normal(a), indicadores.normal(b)
    if not a or not b:
        return False
    if a == b or (min(len(a), len(b)) >= 4 and (f' {a} ' in f' {b} ' or f' {b} ' in f' {a} ')):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= minimo


def un_digito(a, b):
    """Dos teléfonos que solo cambian en un dígito: casi seguro, el mismo leído distinto."""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1


# ---------------------------------------------------------------- Teléfonos, correos y contacto de emergencia

def _telefonos_en(renglon):
    """[(posición, teléfono de 10 dígitos)] de un renglón. Junta "55 1234 5678" y separa dos números seguidos."""
    salida = []
    for corrida in re.finditer(r'(?<!\d)\+?\d[\d \t().-]*\d(?!\d)', renglon):
        grupos = [(m.start() + corrida.start(), m.group()) for m in re.finditer(r'\d+', corrida.group())]
        inicio, juntos = None, ''
        for posicion, digitos in grupos:
            if inicio is None:
                inicio, juntos = posicion, ''
            juntos += digitos
            numero = _normalizar_telefono(juntos)
            if numero:
                salida.append((inicio, numero))
                inicio = None
            elif len(juntos) >= 13:
                inicio, juntos = posicion, digitos
                numero = _normalizar_telefono(juntos)
                if numero:
                    salida.append((inicio, numero))
                    inicio = None
    return salida


def _normalizar_telefono(digitos):
    if len(digitos) == 13 and digitos[:3] in ('044', '045', '521'):
        digitos = digitos[3:]
    elif len(digitos) == 12 and digitos.startswith('52'):
        digitos = digitos[2:]
    if len(digitos) != 10 or digitos[0] in '01' or digitos.startswith(('800', '900')):
        return None
    return digitos


def _duenos(renglon):
    return sorted((m.start(), quien) for quien, patron in DUENOS for m in re.finditer(patron, renglon))


def _dueno(duenos, posicion, siguiente, antes):
    """De quién es el dato en `posicion`: la palabra entre el dato anterior y este ("Madre: 55...") o, si el renglón
    escribe el dueño después ("55... (mamá)"), la que está entre este y el siguiente."""
    previos = [q for p, q in duenos if p < posicion]
    despues = [q for p, q in duenos if posicion < p < siguiente]
    if antes and previos:
        return previos[-1]
    return (despues or previos or [''])[0]


def contactos(texto, exigir_etiqueta=True):
    """{'telefonos': [{valor, de}], 'correos': [{valor, de}], 'emergencia': [{nombre, parentesco}]} de un texto.

    exigir_etiqueta: un número de 10 dígitos sin "Tel.", "Cel." ni de quién es junto a él no se toma (puede ser un folio).
    Con False (lo que el modelo contestó a "¿qué teléfonos hay?") se toma cualquiera que no sea de una institución.
    """
    salida = {'telefonos': [], 'correos': [], 'emergencia': []}
    lineas = renglones(texto)
    seccion, edad = '', 99  # De quién es la parte de la hoja ("DATOS DE LA MADRE") y cuántos renglones van desde su título.
    for i, crudo in enumerate(lineas):
        renglon = re.sub(r'@\s*([A-Z0-9-]+)\s+(COM|MX|NET|ORG)\b', r'@\1.\2', normal(crudo))
        duenos = _duenos(renglon)
        telefonos = _telefonos_en(renglon)
        correos = [(m.start(), m.group()) for m in CORREO.finditer(renglon)]
        institucion = bool(INSTITUCION.search(renglon)) and not duenos
        anterior = normal(lineas[i - 1]) if i else ''
        etiqueta = bool(ETIQUETA_TEL.search(renglon)) or (bool(ETIQUETA_TEL.search(anterior)) and not _telefonos_en(anterior))
        edad += 1
        de_seccion = seccion if edad <= 5 else ''
        datos = sorted([(p, 't', v) for p, v in telefonos] + [(p, 'c', v) for p, v in correos])
        antes = bool(datos) and any(p < datos[0][0] for p, _ in duenos)
        for n, (posicion, clase, valor) in enumerate(datos):
            siguiente = datos[n + 1][0] if n + 1 < len(datos) else len(renglon) + 1
            de = _dueno(duenos, posicion, siguiente, antes) or ('' if de_seccion == 'institucion' else de_seccion)
            if institucion or (de_seccion == 'institucion' and not duenos):
                continue
            if clase == 't':
                if exigir_etiqueta and not (etiqueta or de):
                    continue
                if not any(t['valor'] == valor for t in salida['telefonos']):
                    salida['telefonos'].append({'valor': valor, 'de': de})
            else:
                limpio = campos_mod.correo(valor.lower())
                if limpio and not DOMINIOS_INSTITUCION.search(limpio.split('@')[1]) and not any(c['valor'] == limpio for c in salida['correos']):
                    salida['correos'].append({'valor': limpio, 'de': de})
        if not datos and len(renglon.split()) <= 8:  # Un título: lo que sigue es de esa persona (o de la clínica).
            if duenos:
                seccion, edad = duenos[0][1], 0
            elif TITULO_CLINICA.search(renglon):
                seccion, edad = 'institucion', 0
            elif re.search(r'ALUMN|PACIENTE', renglon):
                seccion = ''
        if EMERGENCIA.search(renglon):
            persona = _emergencia(crudo, lineas[i + 1:i + 4])
            if persona and not any(parecido(persona['nombre'], e['nombre']) for e in salida['emergencia']):
                salida['emergencia'].append(persona)
    return salida


def _emergencia(renglon, siguientes):
    """El nombre (y parentesco) de quien se avisa en una emergencia: en el mismo renglón o, si es un título, abajo."""
    resto = renglon.split(':', 1)[1] if ':' in renglon else renglon
    persona = _nombre_de(resto)
    if persona or re.search(r'\d', resto):
        return persona
    for siguiente in siguientes:  # "EN CASO DE EMERGENCIA" como título: el nombre viene abajo.
        texto = normal(siguiente)
        if re.search(r'\bNOMBRE\b', texto) or not re.search(r'\d|@|:', texto):
            persona = _nombre_de(siguiente.split(':', 1)[1] if ':' in siguiente else siguiente)
            if persona:
                parentesco = next((normal(s).split(':', 1)[1].strip() for s in siguientes if re.search(r'PARENTESCO', normal(s)) and ':' in s), '')
                return {**persona, 'parentesco': persona['parentesco'] or _parentesco(parentesco)}
        if EMERGENCIA.search(texto):
            break
    return None


def _parentesco(texto):
    palabras = re.findall(r'[A-ZÑ]+', normal(texto))
    return next((p for p in palabras if p in PARENTESCOS), '')


def _nombre_de(texto):
    t = normal(texto)
    t = re.split(r'\d|\bTEL\w*|\bCEL\w*|\bCORREO|@|\bPARENTESCO|\bDOMICILIO|\bDIRECCION', t)[0]
    parentesco = _parentesco(t)
    t = re.sub(r'\(([^)]*)\)', ' ', t)
    palabras = [p for p in re.findall(r'[A-ZÑ]+', t) if p not in PARENTESCOS]
    while palabras and palabras[0] in ETIQUETA_NOMBRE:
        palabras.pop(0)
    if 'ILEGIBLE' in palabras or set(palabras) & NO_NOMBRE or not 2 <= len(palabras) <= 6 or sum(len(p) >= 3 for p in palabras) < 2:
        return None
    nombre = campos_mod.limpiar('nombre', ' '.join(palabras))[0]
    return {'nombre': nombre, 'parentesco': parentesco} if nombre else None


# ---------------------------------------------------------------- Salud del alumno

def _valor_marcado(texto):
    """Lo que dice un valor con casillas: 'NINGUNA' si se marcó "No", lo marcado de una lista de opciones, o None si
    tiene casillas y ninguna está marcada (las opciones impresas sin marcar no son del alumno)."""
    if not re.search(CASILLA, texto):
        return texto
    cual = re.search(r'CUAL\w*\s*[?:.]*\s*(.*)$', texto)
    cual = re.sub(CASILLA, ' ', cual[1]).strip(' .,;:') if cual else ''
    # "Sí [X] No [ ]" (la casilla va después de su palabra) o "[X] Sí [ ] No" (antes): se ve en cómo empieza.
    casilla_antes = bool(re.match(r'\s*' + CASILLA, texto))
    marcado = (lambda palabra: re.search(MARCA + rf'\s*{palabra}\b', texto)) if casilla_antes else \
        (lambda palabra: re.search(rf'\b{palabra}\s*:?\s*' + MARCA, texto))
    if marcado('NO'):
        return 'NINGUNA' if not cual or es_ninguno(cual) else None
    if marcado('SI'):
        return cual or None  # "Sí" sin decir qué: no hay qué guardar (que lo vea una persona en la hoja).
    partes = re.split(f'({CASILLA})', texto.split('CUAL')[0])
    marcadas = []
    for n, parte in enumerate(partes):
        if not re.fullmatch(MARCA, parte):
            continue
        opcion = partes[n + 1] if casilla_antes and n + 1 < len(partes) else partes[n - 1] if n else ''
        opcion = re.sub(r'^[\s,;:.¿?-]+|[\s,;:.¿?-]+$', '', opcion)
        if opcion:
            marcadas.append(opcion)
    if cual and marcadas and re.fullmatch(r'OTR[OA]S?', marcadas[-1]):
        marcadas[-1] = cual
    return ', '.join(marcadas) if marcadas else None


def _valor_de(renglon, etiqueta, patron):
    """Lo que está después de la etiqueta: tras ':' o '?', o tras la palabra de la etiqueta ("Alergias negadas")."""
    if etiqueta != renglon:
        return renglon[len(etiqueta) + 1:].strip()
    if '?' in renglon:
        return renglon.split('?', 1)[1].strip()
    hallado = patron.search(renglon)
    return re.sub(r'^\w*', '', renglon[hallado.end():], count=1).strip() if hallado else ''


def _agregar(encontrados, campo, valor):
    if valor is None:
        return
    valor = re.sub(r'\[?ILEGIBLE\]?', ' ', normal(valor)).strip(' .,;:')
    if not valor:
        return
    valores = encontrados.setdefault(campo, [])
    if es_ninguno(valor):
        valores.append('NINGUNA')
        return
    valor = re.sub(r'^SI\b[\s,.:;-]*', '', valor)  # "Sí, a la penicilina".
    for parte in campos_mod.lista(re.sub(r'\([^)]*\)', lambda m: '' if FAMILIA.search(m.group()) else m.group(), valor)):
        parte = re.sub(r'^(?:A LA|A LOS|A LAS|AL|A)\s+', '', parte).strip()
        if parte and not es_ninguno(parte) and not FAMILIA.search(parte) and not any(parecido(parte, v) for v in valores):
            valores.append(parte)


def salud(texto):
    """{campo: 'VALOR, VALOR' o 'NINGUNA'} de las etiquetas de salud de la hoja (solo las que aparecen).

    El campo lo dice la etiqueta, no el valor ("Diagnóstico: rinitis alérgica" es un padecimiento). Lo de los antecedentes
    de la familia no cuenta, ni las opciones impresas sin marcar. Un título como "Antecedentes personales patológicos:"
    abre su campo para los renglones de abajo ("Asma [ ]", "Epilepsia: no").
    """
    encontrados = {}
    familia, abierto, edad = 0, None, 0
    for crudo in renglones(texto):
        renglon = normal(crudo)
        etiqueta = renglon.split(':', 1)[0] if ':' in renglon else renglon
        campo = next((c for c, patron in SALUD if patron.search(etiqueta)), None)
        if FAMILIA.search(etiqueta) and not re.search(r'PERSONALES|DEL ALUMNO|DEL PACIENTE', etiqueta):
            if re.search(r'HEREDO|FAMILIAR|ANTECEDENTES', etiqueta) and not renglon[len(etiqueta) + 1:].strip():
                familia, abierto = 8, None  # Un título: lo que sigue es de la familia.
            continue
        if familia and OTRA_SECCION.search(etiqueta):  # Una enfermedad listada en la sección de la familia no la termina.
            familia = 0
        if familia:
            familia -= 1
            continue
        if campo:
            abierto = None
            if NO_SALUD.search(etiqueta):
                continue
            valor = _valor_de(renglon, etiqueta, dict(SALUD)[campo])
            if not valor:
                abierto, edad = campo, 0
                continue
            _agregar(encontrados, campo, _valor_marcado(valor))
            continue
        if not abierto:
            continue
        edad += 1
        si_no = re.fullmatch(r'(.+?)\s*[:.-]\s*(SI|NO|S|N|X)\b[\s.]*', renglon)
        if edad > 6 or (':' in renglon and not si_no and not re.search(CASILLA, renglon)):
            abierto = None
        elif re.search(CASILLA, renglon):
            _agregar(encontrados, abierto, _valor_marcado(renglon))
        elif si_no:
            _agregar(encontrados, abierto, si_no[1] if si_no[2] in ('SI', 'S', 'X') else 'NINGUNA')
        elif edad == 1:
            _agregar(encontrados, abierto, renglon)
        else:
            abierto = None
    salida = {}
    for campo, valores in encontrados.items():
        positivos = [v for v in valores if v != 'NINGUNA']
        salida[campo] = ', '.join(positivos) if positivos else 'NINGUNA'
    return salida


def de_campos(texto, lista, hoy=None):
    """{clave: valor} para los campos de la plantilla, sacado de un texto completo (lo transcrito o el PDF)."""
    salida = {}
    de_salud = salud(texto)
    hallados = contactos(texto)
    usados = set()
    for c in lista:
        if c['categoria'] == 'salud' and c['tipo'] == 'lista' and c['campo'] in de_salud:
            salida[c['clave']] = de_salud[c['campo']]
        elif c['tipo'] in ('telefono', 'correo'):
            lista_datos = hallados['telefonos' if c['tipo'] == 'telefono' else 'correos']
            dato = next((d for d in lista_datos if d['valor'] not in usados and (d['de'] == c.get('de') or not c.get('de'))), None)
            if dato:
                salida[c['clave']] = dato['valor']
                usados.add(dato['valor'])
        elif c['campo'] == 'nombre_emergencia' and hallados['emergencia']:
            salida[c['clave']] = hallados['emergencia'][0]['nombre']
    for clave, valor in campos_mod.de_texto(texto, [c for c in lista if c['clave'] not in salida], hoy, libres=True).items():
        salida[clave] = valor
    return salida


# ---------------------------------------------------------------- Duplicados en el expediente de un alumno

NIVEL = {'baja': 1, 'media': 2, 'alta': 3, 'confirmado': 4}


def _fuerza(fila):
    return (NIVEL.get(fila['confianza'], 0), fila['estado'] == 'vigente', fila['id'])


def duplicados(filas):
    """[(id que se marca como reemplazado, id que se queda)] entre los datos vigentes o por confirmar de un alumno.

    Dos lecturas casi iguales del mismo campo ("PENICILINA" y "PENISILINA", dos teléfonos que cambian en un dígito
    cuando uno está por confirmar) se quedan en una: la más segura. Un "NINGUNA" leído por la máquina sobra si hay un
    valor de verdad en el mismo campo. Lo confirmado por una persona nunca se marca.
    """
    marcar = []
    por_campo = {}
    for fila in filas:
        if fila['estado'] in ('vigente', 'por_confirmar'):
            por_campo.setdefault((fila['categoria'], fila['campo']), []).append(fila)
    for (_categoria, campo), grupo in por_campo.items():
        grupo = sorted(grupo, key=_fuerza, reverse=True)
        quedan = []
        for fila in grupo:
            maquina = fila['confianza'] != 'confirmado' and fila['quien'] == 'cerebro'
            if (fila.get('detalle') or {}).get('nada') or es_ninguno(fila['valor']):
                hay_valor = next((q for q in grupo if q['estado'] == 'vigente' and not es_ninguno(q['valor'])
                                  and not (q.get('detalle') or {}).get('nada')), None)
                if maquina and hay_valor and campo in campos_mod.VARIOS:
                    marcar.append((fila['id'], hay_valor['id']))
                    continue
            igual = next((q for q in quedan if _mismo(campo, q, fila)), None)
            if igual and maquina:
                marcar.append((fila['id'], igual['id']))
            else:
                quedan.append(fila)
    return marcar


def _mismo(campo, uno, otro):
    a, b = str(uno['valor']), str(otro['valor'])
    if campo == 'telefono':
        a, b = re.sub(r'\D', '', a), re.sub(r'\D', '', b)
        return a == b or (un_digito(a, b) and 'baja' in (uno['confianza'], otro['confianza']))
    if campo == 'correo':
        return a.lower() == b.lower() or difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.92
    return parecido(a, b)
