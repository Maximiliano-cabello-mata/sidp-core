"""Datos de documentos escaneados, para expedientes que la escuela ya revisó en papel.

Aquí no hay captura del padre contra la cual comparar: el lector saca el texto de cada página,
se reconoce qué documento es y se proponen los datos del alumno y del tutor. La persona que
escanea los revisa en el panel y guarda. Procesos fijos, sin IA:

- La CURP se busca con su dígito verificador. Si el OCR confundió una letra con un número
  (O y 0, I y 1, S y 5...), se corrige según la posición y el dígito debe cuadrar.
- La CURP trae la fecha de nacimiento, el sexo y las letras de los apellidos y el nombre. Con
  esas letras se encuentra el nombre dentro del texto, esté donde esté en la hoja.
- Del reverso de la INE se lee la franja con '<' (nombre, nacimiento, sexo y vigencia).
"""
import datetime
import re

from validacion import comparador, mrz, renapo
from validacion.expediente import TIPOS, fechas, mayusculas, parece

VOCALES = set('AEIOU')
PARTICULAS = {'DE', 'DEL', 'LA', 'LAS', 'LOS', 'Y', 'MC', 'MAC', 'VAN', 'VON', 'DA', 'DI'}
NOMBRES_COMUNES = {'MARIA', 'MA', 'JOSE', 'J'}  # La CURP usa el segundo nombre si el primero es uno de estos.
ETIQUETAS = {'NOMBRE', 'NOMBRES', 'S', 'PRIMER', 'SEGUNDO', 'APELLIDO', 'APELLIDOS', 'PATERNO', 'MATERNO', 'CURP', 'CLAVE',
             'SEXO', 'FECHA', 'NACIMIENTO', 'PADRE', 'MADRE', 'NACIONALIDAD', 'MEXICANA', 'MEXICANO', 'ALUMNO', 'DOMICILIO'}
# Qué se espera en cada posición de la CURP: letra o número (la 17 puede ser cualquiera).
FORMA = 'LLLLDDDDDDLLLLLLAD'
A_NUMERO = {'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'G': '6', 'B': '8', 'T': '7'}
A_LETRA = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '6': 'G', '7': 'T', '8': 'B'}
ESPACIOS = {**{t: v[0] for t, v in TIPOS.items()}, 'constancia_curp': 'Constancia de la CURP', 'otro': 'Otro documento'}


def _corregir_curp(pedazo, exigir_digito=True):
    """La CURP con las confusiones típicas del OCR corregidas, o None si no cuadra el dígito verificador."""
    if len(pedazo) != 18:
        return None
    salida = []
    for caracter, forma in zip(pedazo, FORMA):
        if forma == 'D' and not caracter.isdigit():
            caracter = A_NUMERO.get(caracter, caracter)
        elif forma == 'L' and caracter.isdigit():
            caracter = A_LETRA.get(caracter, caracter)
        salida.append(caracter)
    curp = ''.join(salida)
    desglose = comparador.desglose_curp(curp)
    return curp if desglose and (desglose['digito_valido'] or not exigir_digito) and curp[1] in VOCALES | {'X'} else None


def curps(texto, exigir_digito=True):
    """Las CURP válidas del texto, en el orden en que aparecen (con exigir_digito=False, también las que no cuadran)."""
    encontradas = []
    for pedazo in re.sub(r'[^A-Z0-9]+', ' ', mayusculas(texto)).split():
        curp = _corregir_curp(pedazo, exigir_digito)
        if not curp and len(pedazo) == 19:
            # El OCR metió una letra de más ("...GAZ4"). Vale quitar una solo si queda una única CURP
            # con dígito correcto, o una única cuyas letras corresponden a un nombre del mismo texto.
            opciones = {c for c in (_corregir_curp(pedazo[:i] + pedazo[i + 1:]) for i in range(19)) if c}
            if len(opciones) > 1:
                opciones = {c for c in opciones if nombre_por_curp(texto, c)}
            curp = opciones.pop() if len(opciones) == 1 else None
        if curp and curp not in encontradas:
            encontradas.append(curp)
    return encontradas


def _interna(palabra, vocal):
    for letra in palabra[1:]:
        if (letra in VOCALES) == vocal:
            return letra
    return 'X'


def _palabras(texto):
    """Palabras del texto sin etiquetas de formato, cada una con su número de renglón."""
    salida = []
    for numero, linea in enumerate(mayusculas(texto).splitlines()):
        salida += [(p, numero) for p in re.sub(r'[^A-Z]+', ' ', linea).split() if p not in ETIQUETAS and (len(p) > 1 or p == 'Y')]
    return salida


def _apellido(palabras, i):
    """Un apellido que empieza en i, con sus partículas (DE LA CRUZ): (palabras, la que cuenta, siguiente i)."""
    inicio = i
    while i < len(palabras) - 1 and palabras[i] in PARTICULAS:
        i += 1
    if i >= len(palabras):
        return None
    return palabras[inicio:i + 1], palabras[i], i + 1


def _cuadra(curp, apellido1, apellido2, nombres):
    if nombres[-1] in PARTICULAS or nombres[0] in PARTICULAS:  # "JUAN DE LA" no es un nombre: DE LA es del apellido.
        return False
    nombre = next((n for n in nombres if n not in NOMBRES_COMUNES | PARTICULAS), nombres[0])  # MARIA DEL CARMEN -> CARMEN.
    return (apellido1[0] == curp[0] and _interna(apellido1, True) == curp[1] and (apellido2 or 'X')[0] == curp[2]
            and nombre[0] == curp[3] and _interna(apellido1, False) == curp[13]
            and (_interna(apellido2, False) if apellido2 else 'X') == curp[14] and _interna(nombre, False) == curp[15])


def nombre_por_curp(texto, curp):
    """{'nombres', 'primer_apellido', 'segundo_apellido'} encontrados con las letras de la CURP, o None.

    Prueba los dos órdenes: nombres y luego apellidos (acta) y apellidos y luego nombres (INE,
    boletas). Con varios nombres posibles gana el más largo que cuadre; después de los apellidos
    los nombres solo se toman del mismo renglón.
    """
    lista = _palabras(texto)
    palabras, renglon = [p for p, _ in lista], [n for _, n in lista]

    def resultado(nombres, primero, segundo):
        return {'nombres': ' '.join(nombres), 'primer_apellido': ' '.join(primero[0]), 'segundo_apellido': ' '.join(segundo[0])}

    for i in range(len(palabras)):
        for cuantos in (3, 2, 1):  # Nombres primero: LUIS (MIGUEL) HERNANDEZ RAMOS.
            nombres = palabras[i:i + cuantos]
            primero = _apellido(palabras, i + cuantos)
            segundo = primero and _apellido(palabras, primero[2])
            if (len(nombres) == cuantos and len(set(renglon[i:i + cuantos])) == 1 and segundo
                    and _cuadra(curp, primero[1], segundo[1], nombres)):
                return resultado(nombres, primero, segundo)
        primero = _apellido(palabras, i)  # Apellidos primero: HERNANDEZ RAMOS LUIS (MIGUEL).
        segundo = primero and _apellido(palabras, primero[2])
        if segundo and segundo[2] < len(palabras):
            inicio = segundo[2]
            for cuantos in (3, 2, 1):
                nombres = palabras[inicio:inicio + cuantos]
                if (len(nombres) == cuantos and len(set(renglon[inicio:inicio + cuantos])) == 1
                        and _cuadra(curp, primero[1], segundo[1], nombres)):
                    return resultado(nombres, primero, segundo)
    return None


def _persona(texto, curp):
    desglose = comparador.desglose_curp(curp)
    datos = {'curp': curp, 'fecha_nacimiento': desglose['fecha'], 'sexo': desglose['sexo']}
    return {**datos, **(nombre_por_curp(texto, curp) or {})}


def _nombre_con_etiquetas(texto):
    """Actas nuevas: 'Nombre(s): DIEGO  Primer apellido: CASTRO  Segundo apellido: NAVA' en un renglón, o None."""
    for linea in mayusculas(texto).splitlines():
        hallado = re.search(r'NOMBRE\W*S?\W*:?\s*([A-Z ]+?)\s+PRIMER APELLIDO\W*([A-Z ]+?)\s+SEGUNDO APELLIDO\W*([A-Z ]*)', linea)
        if hallado and hallado.group(1).strip() and hallado.group(2).strip():
            return {'nombres': ' '.join(hallado.group(1).split()), 'primer_apellido': ' '.join(hallado.group(2).split()),
                    'segundo_apellido': ' '.join(hallado.group(3).split())}
    return None


def _nombre_tras(texto, etiqueta):
    """El nombre escrito después de una etiqueta en el mismo renglón (Padre: JUAN PEREZ LOPEZ), o None."""
    for linea in mayusculas(texto).splitlines():
        hallado = re.search(rf'\b{etiqueta}\b[^A-Z]*([A-Z ]+)', linea)
        if not hallado:
            continue
        palabras = []
        for palabra in hallado.group(1).split():
            if palabra in ETIQUETAS:
                break
            palabras.append(palabra)
        if 2 <= len(palabras) <= 6:
            apellidos = palabras[-2:] if len(palabras) > 2 else palabras[-1:]
            return {'nombres': ' '.join(palabras[:len(palabras) - len(apellidos)]), 'primer_apellido': apellidos[0],
                    'segundo_apellido': apellidos[1] if len(apellidos) > 1 else ''}
    return None


def _nombre_ine(texto):
    """Frente de la INE sin CURP legible: debajo de NOMBRE vienen primer apellido, segundo apellido y nombres."""
    lineas = [l.strip() for l in mayusculas(texto).splitlines() if l.strip()]
    for i, linea in enumerate(lineas):
        if linea == 'NOMBRE' and len(lineas) > i + 3:
            primero, segundo, nombres = lineas[i + 1:i + 4]
            if all(re.fullmatch(r'[A-Z ]{2,40}', parte) and parte not in ETIQUETAS for parte in (primero, segundo, nombres)):
                return {'nombres': nombres, 'primer_apellido': primero, 'segundo_apellido': segundo}
    return None


def tipo_de(texto, plantillas=None):
    """Qué documento es una página: el tipo con más textos fijos encontrados, o None.

    plantillas: las activas (validacion.plantillas). Las que agregó la escuela ganan si la página
    tiene sus textos fijos: son más específicas (una ficha de inscripción también dice "acta de nacimiento").
    """
    texto = mayusculas(texto)
    if any(marca in texto for marca in renapo.MARCAS) and 'ACTA DE NACIMIENTO' not in texto:
        return 'constancia_curp'
    if plantillas is None:
        plantillas = [{'clave': t, 'textos': marcas, 'minimo': 1, 'fabrica': True} for t, (_, _, marcas) in TIPOS.items()]
    propias = {p['clave']: sum(parece(texto, [m]) for m in p['textos']) for p in plantillas if not p.get('fabrica')}
    propias = {clave: n for clave, n in propias.items() if n >= next(p['minimo'] for p in plantillas if p['clave'] == clave)}
    if propias:
        return max(propias, key=propias.get)
    puntos = {p['clave']: sum(parece(texto, [m]) for m in p['textos']) for p in plantillas
              if p.get('fabrica') and p['clave'] != 'acta_tutor'}
    mejor = max(puntos, key=puntos.get, default=None)
    return mejor if mejor and puntos[mejor] else None


def agrupar(paginas, plantillas=None):
    """Cada página con su tipo; una página sin tipo (el reverso de una hoja) se junta con la anterior."""
    anterior = None
    for pagina in paginas:
        tipo = tipo_de(pagina['texto'] + ' ' + ' '.join(pagina.get('qr', [])), plantillas)
        pagina['tipo'] = tipo or anterior or 'otro'
        pagina['reconocido'] = bool(tipo)
        anterior = pagina['tipo']
    return paginas


def proponer(paginas, hoy=None):
    """Datos propuestos del alumno y del tutor a partir de las páginas leídas y agrupadas.

    paginas: [{'archivo', 'texto', 'qr', 'tipo'}]. Devuelve {'alumno', 'tutor', 'avisos', 'extraidos'}.
    """
    hoy = hoy or datetime.date.today()
    textos = {}
    for pagina in paginas:
        textos[pagina['tipo']] = textos.get(pagina['tipo'], '') + '\n' + pagina['texto'] + '\n' + '\n'.join(pagina.get('qr', []))
    alumno, tutor, avisos, extraidos = {}, {}, [], {}

    # Alumno: la CURP más joven del acta o de la constancia (en el acta también vienen las de los padres).
    fuente = textos.get('acta_alumno', '') + '\n' + textos.get('constancia_curp', '')
    candidatas = sorted(curps(fuente), key=lambda c: comparador.desglose_curp(c)['fecha'], reverse=True)
    if candidatas:
        alumno = _persona(fuente, candidatas[0])
    else:
        # Una CURP que no cuadra su dígito verificador (error del acta o del OCR) se propone igual, con aviso.
        dudosas = sorted(curps(fuente, exigir_digito=False), key=lambda c: comparador.desglose_curp(c)['fecha'], reverse=True)
        if dudosas:
            alumno = _persona(fuente, dudosas[0])
            avisos.append(f'La CURP {dudosas[0]} no cuadra su dígito verificador: compárala con el acta.')
    if 'nombres' not in alumno and _nombre_con_etiquetas(fuente):
        alumno.update(_nombre_con_etiquetas(fuente))
        if alumno.get('curp'):
            avisos.append('El nombre del alumno no corresponde con las letras de su CURP: revisa los dos.')
    if not alumno.get('curp'):
        avisos.append('No se encontró la CURP del alumno en el acta: escríbela.' if fuente.strip()
                      else 'No se encontró el acta de nacimiento del alumno.')
    elif 'nombres' not in alumno:
        avisos.append('Se encontró la CURP del alumno, pero no su nombre: escríbelo.')
    if textos.get('acta_alumno'):
        extraidos['acta_fechas'] = sorted({f.isoformat() for f in fechas(textos['acta_alumno'])})

    # Padres en el acta: por su CURP, o por lo escrito después de "Padre:" y "Madre:".
    padres = {}
    for curp in candidatas[1:]:
        persona = _persona(fuente, curp)
        padres['padre' if persona['sexo'] == 'H' else 'madre'] = persona
    for parentesco in ('padre', 'madre'):
        if parentesco not in padres and textos.get('acta_alumno'):
            nombre = _nombre_tras(textos['acta_alumno'], parentesco.upper())
            if nombre:
                padres[parentesco] = nombre

    # Tutor: el de la INE (franja del reverso o CURP del frente); si no hay INE, la madre o el padre del acta.
    ine = textos.get('ine_tutor', '')
    if ine:
        franja = mrz.leer(ine)
        curp_ine = next(iter(curps(ine)), None)
        if curp_ine:
            tutor = _persona(ine, curp_ine)
        elif franja and franja.get('nombre'):
            tutor = {'nombres': ' '.join(franja['nombres']), 'primer_apellido': franja['apellidos'][0],
                     'segundo_apellido': ' '.join(franja['apellidos'][1:])}
            if franja.get('nacimiento_valido'):
                tutor['fecha_nacimiento'] = franja['nacimiento'].isoformat()
        if franja:
            extraidos['ine_mrz'] = {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in franja.items()}
            if franja.get('vigencia') and franja['vigencia'] < hoy:
                avisos.append(f'La INE venció el {franja["vigencia"].isoformat()}.')
    completo = lambda p: ' '.join(filter(None, (p.get('nombres'), p.get('primer_apellido'), p.get('segundo_apellido'))))
    if ine and not tutor.get('nombres'):  # Sin CURP ni franja legibles: ¿la INE es de alguno de los padres del acta?
        palabras_ine = {p for p, _ in _palabras(ine)}
        for parentesco, persona in padres.items():
            if set(comparador.normalizar(completo(persona)).split()) <= palabras_ine:
                tutor = {**persona, 'parentesco': parentesco}
                break
        else:
            tutor = _nombre_ine(ine) or {}
            avisos.append('El nombre de la INE se tomó de lo que se alcanzó a leer: revísalo.' if tutor
                          else 'No se encontró el nombre en la INE: escríbelo.')
    for parentesco, persona in padres.items():
        if tutor and (persona.get('curp') and persona['curp'] == tutor.get('curp')
                      or comparador.normalizar(completo(persona)) == comparador.normalizar(completo(tutor))):
            tutor['parentesco'] = parentesco
    if not tutor and padres and not ine:
        parentesco = 'madre' if 'madre' in padres else 'padre'
        tutor = {**padres[parentesco], 'parentesco': parentesco}
        avisos.append(f'No hay INE: el tutor se tomó del acta ({parentesco}).')
    extraidos['padres_en_acta'] = {k: completo(v) for k, v in padres.items()}

    comprobante = textos.get('comprobante', '')
    if comprobante:
        pasadas = [f for f in fechas(comprobante) if f <= hoy]
        if pasadas:
            extraidos['comprobante_fecha'] = max(pasadas).isoformat()
    faltan = [ESPACIOS[t] for t in ('acta_alumno', 'certificado_medico', 'ine_tutor', 'comprobante') if t not in textos]
    if faltan:
        avisos.append('No se reconoció: ' + ', '.join(faltan) + '. Si sí está, elige su tipo en la lista de páginas.')
    return {'alumno': alumno, 'tutor': tutor, 'avisos': avisos, 'extraidos': extraidos}


# --- Listas de grupo ---

ENCABEZADOS = {'NOMBRE', 'NOMBRES', 'ALUMNO', 'ALUMNOS', 'ALUMNA', 'GRADO', 'GRUPO', 'ESCUELA', 'LISTA', 'CICLO', 'ESCOLAR', 'PROFESOR',
               'PROFESORA', 'MAESTRO', 'MAESTRA', 'DOCENTE', 'CLAVE', 'CCT', 'TURNO', 'MATUTINO', 'VESPERTINO', 'PRIMARIA', 'SECRETARIA',
               'EDUCACION', 'PUBLICA', 'APELLIDO', 'APELLIDOS', 'PATERNO', 'MATERNO', 'CURP', 'NO', 'NUM', 'FIRMA', 'TOTAL', 'HOMBRES',
               'MUJERES', 'ASISTENCIA', 'FECHA', 'ZONA', 'SECTOR', 'GOBIERNO', 'ESTADO', 'MEXICO', 'DIRECTOR', 'DIRECTORA'}
GRADOS_TEXTO = {'PRIMER': 1, 'PRIMERO': 1, 'SEGUNDO': 2, 'TERCER': 3, 'TERCERO': 3, 'CUARTO': 4, 'QUINTO': 5, 'SEXTO': 6}


def grado_y_grupo(texto):
    """(grado, letra) escritos en la hoja de la lista: "3° A", "GRADO: 3 GRUPO: A", "TERCER GRADO GRUPO B"; o (None, None)."""
    texto = mayusculas(texto)
    hallado = re.search(r'GRADO\W{0,3}([1-6])\b.{0,20}?GRUPO\W{0,3}([A-H])\b', texto)
    if hallado:
        return int(hallado.group(1)), hallado.group(2)
    hallado = re.search(r'\b([1-6])\s*(?:°|º|O|ER|DO|RO|TO|VO)?\s*["\']?\s*([A-H])["\']?\s*(?:$|\n|GRUPO)', texto)
    if hallado:
        return int(hallado.group(1)), hallado.group(2)
    hallado = re.search(r'\b(' + '|'.join(GRADOS_TEXTO) + r')\s+GRADO\b.{0,20}?GRUPO\W{0,3}([A-H])\b', texto)
    if hallado:
        return GRADOS_TEXTO[hallado.group(1)], hallado.group(2)
    return None, None


def lista_de_grupo(texto, apellidos_primero=True):
    """Los alumnos de una lista de grupo, un renglón por alumno: [{nombres, primer_apellido, segundo_apellido, curp, dudoso}].

    Se quitan números de lista y encabezados. Si el renglón trae CURP, el nombre se acomoda con sus letras;
    si no, se usa el orden de la lista (casi siempre apellidos primero, como en las listas de la SEP).
    """
    filas = []
    for linea in mayusculas(texto).splitlines():
        curp = next(iter(curps(linea)), None)
        # Una CURP mal leída (dígito verificador que no cuadra) se propone, pero como duda.
        dudosa = None if curp else next(iter(curps(linea, exigir_digito=False)), None)
        # Las palabras con números (una CURP rota, una fecha) no son parte del nombre.
        limpia = ' '.join(p for p in linea.replace(curp or '\0', ' ').split() if not re.search(r'[A-Z]\d|\d[A-Z]', p))
        palabras = [p for p in re.sub(r'[^A-Z]+', ' ', limpia).split()]
        palabras = [p for p in palabras if len(p) > 1 or p == 'Y']
        if not palabras or sum(p in ENCABEZADOS for p in palabras) >= max(1, len(palabras) // 2):
            continue
        if len(palabras) < 2 or len(palabras) > 7:
            continue
        persona = nombre_por_curp(' '.join(palabras), curp) if curp else None
        if persona:
            filas.append({**persona, 'curp': curp, 'dudoso': False})
            continue
        if apellidos_primero:
            primero = (_apellido(palabras, 0) or ([palabras[0]], palabras[0], 1))[0]
            resto = palabras[len(primero):]
            # "PEREZ MARIA DEL CARMEN": MARIA y JOSE casi siempre son nombre, así que no hay segundo apellido.
            segundo = _apellido(resto, 0) if len(resto) > 1 and resto[0] not in NOMBRES_COMUNES else None
            segundo_palabras = segundo[0] if segundo else []
            nombres = resto[len(segundo_palabras):]
        else:
            nombres, resto = palabras[:1], palabras[1:]
            if len(palabras) >= 4:
                nombres, resto = palabras[:2], palabras[2:]
            primero = resto[:1]
            segundo_palabras = resto[1:]
        if not nombres or not primero:
            continue
        filas.append({'nombres': ' '.join(nombres), 'primer_apellido': ' '.join(primero), 'segundo_apellido': ' '.join(segundo_palabras),
                      'curp': curp or dudosa or '', 'dudoso': bool(dudosa) or limpia != linea.strip() and not curp
                      or len(palabras) > 5 or len(palabras) < 3})
    return filas
