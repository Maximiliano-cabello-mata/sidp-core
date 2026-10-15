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
import csv
import datetime
import io
import itertools
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


def grado_por_edad(curps_grupo, inicio_ciclo):
    """El grado que corresponde a la edad de la mayoría (año de nacimiento de sus CURP), o None.

    Sirve cuando la hoja no dice el grado o dice otra cosa (el formato EIA de la SEP pone la fase, no el grado).
    En el ciclo 2026-2027, los nacidos en 2020 van en 1°: grado = inicio del ciclo - año - 5.
    """
    anios = sorted(int(d['fecha'][:4]) for d in (comparador.desglose_curp(c) for c in curps_grupo if c) if d)
    if len(anios) < 3:
        return None
    grado = inicio_ciclo - anios[len(anios) // 2] - 5
    return grado if 1 <= grado <= 6 else None


COLUMNAS_CSV = {'grado': 'grado', 'grupo': 'letra', 'letra': 'letra', 'primer apellido': 'primer_apellido',
                'segundo apellido': 'segundo_apellido', 'nombre(s)': 'nombres', 'nombres': 'nombres', 'nombre': 'nombres', 'curp': 'curp'}


def grupos_de_csv(texto):
    """Una lista ya revisada en CSV (la misma forma que descarga el panel): Grado, Grupo, Primer apellido,
    Segundo apellido, Nombre(s) y CURP. Devuelve los grupos como grupos_de_hojas; [] si no tiene esas columnas."""
    filas = [f for f in csv.reader(io.StringIO(texto.lstrip('\ufeff'))) if any(c.strip() for c in f)]
    if not filas:
        return []
    campos = [COLUMNAS_CSV.get(c.strip().lower()) for c in filas[0]]
    if not {'grado', 'letra', 'primer_apellido', 'nombres'} <= set(campos):
        return []
    grupos = {}
    for fila in filas[1:]:
        datos = {campo: fila[i].strip().lstrip("'") for i, campo in enumerate(campos) if campo and i < len(fila)}
        grado = int(re.sub(r'\D', '', datos.get('grado', '')) or 0) or None
        letra = datos.get('letra', '').upper()[:1] or None
        curp = re.sub(r'[^A-Z0-9]', '', mayusculas(datos.get('curp', '')))
        desglose = comparador.desglose_curp(curp)
        grupo = grupos.setdefault((grado, letra), {'grado': grado, 'letra': letra, 'filas': [], 'hojas': ['CSV'],
                                                   'letra_supuesta': letra is None})
        grupo['filas'].append({'nombres': datos.get('nombres', '').upper(), 'primer_apellido': datos.get('primer_apellido', '').upper(),
                               'segundo_apellido': datos.get('segundo_apellido', '').upper(), 'curp': curp,
                               'dudoso': bool(curp) and not (desglose and desglose['digito_valido'])})
    return sorted(grupos.values(), key=lambda g: (g['grado'] or 9, g['letra'] or 'Z'))


def grupos_de_hojas(hojas, inicio_ciclo, apellidos_primero=True):
    """Hojas [(nombre, texto)] de una o varias listas -> grupos [{grado, letra, filas, hojas, letra_supuesta}].

    Un PDF puede traer varios grupos (la lista oficial de la SEP trae toda la escuela, una hoja por grupo).
    El grado sale de lo escrito en la hoja o, si hay CURP, de la edad de la mayoría; una hoja sin grado
    propio sigue la lista del grupo anterior. Sin letra en la hoja, se ponen A, B, C... por grado.
    """
    leidas = [(nombre, t, lista_de_grupo(t, apellidos_primero)) for nombre, t in hojas]
    con_curp = any(sum(bool(f['curp']) for f in filas) >= 3 for _, _, filas in leidas)
    grupos, vistas = [], set()
    for nombre, t, filas in leidas:
        if con_curp:  # Lista oficial con CURP: las hojas sin CURP son instrucciones o avisos.
            filas = [f for f in filas if f['curp']]
        filas = [f for f in filas if not f['curp'] or f['curp'] not in vistas]  # Un alumno en dos hojas, una vez.
        vistas.update(f['curp'] for f in filas if f['curp'])
        if not filas:
            continue
        escrito, letra = grado_y_grupo(t)
        por_edad = grado_por_edad([f['curp'] for f in filas if not f['dudoso']], inicio_ciclo)
        grado = por_edad or escrito
        letra = letra if escrito == grado else None  # Si el número de la hoja no es el grado, su letra tampoco cuenta.
        anterior = grupos[-1] if grupos else None
        if anterior and (grado is None or (grado, letra) == (anterior['grado'], anterior['letra'])):
            anterior['filas'] += filas  # La lista sigue en la hoja siguiente.
            anterior['hojas'].append(nombre)
        else:
            grupos.append({'grado': grado, 'letra': letra, 'filas': filas, 'hojas': [nombre], 'letra_supuesta': letra is None})
    for grupo in grupos:
        if grupo['letra'] is None and grupo['grado']:
            usadas = {g['letra'] for g in grupos if g['grado'] == grupo['grado'] and g['letra']}
            grupo['letra'] = next(l for l in 'ABCDEFGH' if l not in usadas)
    return grupos


# Nombres frecuentes: sirven para separar dos nombres que la lista trae pegados ("IKERDANIEL").
NOMBRES_CONOCIDOS = frozenset("""
AARON ABEL ABIGAIL ABRIL ADRIAN ADRIANA AIDA ALAN ALBERTO ALDO ALEJANDRA ALEJANDRO ALEXA ALEXANDER ALEXIS ALFREDO ALICIA
ALISSON ALONDRA ALONSO AMANDA AMAURY ANA ANDREA ANDRES ANGEL ANGELA ANTONIO ARIADNA ARIANA ARLETH ARTURO AXEL BENJAMIN BRENDA
BRUNO CAMILA CARLOS CAROLINA CESAR CRISTIAN DANIEL DANIELA DANNA DAVID DIANA DIEGO DYLAN EDUARDO ELENA ELIZABETH EMILIA
EMILIANO EMILIO EMILY EMMANUEL ENRIQUE ERICK ERIKA ESTEBAN FATIMA FERNANDA FERNANDO FRANCISCO FRIDA GABRIEL GABRIELA GAEL
GERARDO GUADALUPE HECTOR HUGO IAN IKER IRVING ISAAC ISABEL ISABELLA ISMAEL ITZEL IVAN JAVIER JESUS JIMENA JONATHAN JORGE
JOSE JOSUE JUAN JULIO KARLA KEVIN LAURA LEONARDO LIA LIAM LUCIA LUIS LUNA MANUEL MARIA MARIANA MARIO MATEO MATIAS
MAXIMILIANO MELANIE MIGUEL MISAEL MONSERRAT NAHOMI NAOMI NATALIA NICOLAS NICOLE OSCAR PABLO PAOLA PATRICIA PAULINA PEDRO
RAFAEL RAUL REGINA RENATA RICARDO ROBERTO RODRIGO ROMINA ROSA RUBI SAMANTHA SANTIAGO SARA SEBASTIAN SERGIO SOFIA TADEO
VALENTINA VALERIA VANESSA VICTOR XAVIER XIMENA YAEL YAMILETH YARETZI ZOE""".split())
# Apellidos frecuentes: deciden entre dos cortes que cuadran con la CURP ("RIVERAARIZA" -> RIVERA ARIZA, no RIVER AARIZA).
APELLIDOS_CONOCIDOS = frozenset("""
AGUILAR ALVAREZ ARIZA CASTILLO CASTRO CHAVEZ CONTRERAS CRUZ DIAZ DOMINGUEZ ESPINOSA ESPINOZA FERNANDEZ FLORES GARCIA GOMEZ
GONZALEZ GUTIERREZ GUZMAN HERNANDEZ HERRERA JIMENEZ JUAREZ LOPEZ MALDONADO MARTINEZ MEDINA MENDOZA MORALES MORENO MUÑOZ
ORTIZ PEREZ RAMIREZ RAMOS REYES RIVERA RODRIGUEZ ROJAS ROMERO RUIZ SALAZAR SANCHEZ SANTIAGO TORRES VARGAS VAZQUEZ""".split())


def mayusculas_con_enie(texto):
    """Como mayusculas(), pero la Ñ se queda (en los nombres sí importa; en la CURP se escribe X)."""
    return 'Ñ'.join(mayusculas(pedazo) for pedazo in (texto or '').replace('ñ', 'Ñ').split('Ñ'))


def _clave_curp(palabras, nombre=False):
    """Cuál palabra da sus letras a la CURP: sin partículas (DE LA) y, en el nombre, sin MARIA o JOSE si hay otro."""
    utiles = [i for i, p in enumerate(palabras) if p not in PARTICULAS] or list(range(len(palabras)))
    if nombre and len(utiles) > 1 and palabras[utiles[0]] in NOMBRES_COMUNES:
        utiles = utiles[1:]
    return utiles[0]


def _letras_curp(palabras, nombre=False):
    return palabras[_clave_curp(palabras, nombre)].replace('Ñ', 'X')


def _consonante(palabra, letra_curp):
    """La consonante interna; una N donde la CURP dice X era una Ñ que la lista perdió (ZUNIGA -> ZUÑIGA)."""
    letra = _interna(palabra, False)
    return 'X' if letra == 'N' and letra_curp == 'X' else letra


def _poner_enie(palabras, letra_curp, nombre=False):
    """Devuelve la Ñ a la palabra que da sus letras a la CURP, si la CURP dice que la tenía."""
    if not palabras:
        return palabras
    i = _clave_curp(palabras, nombre)
    palabra = palabras[i]
    if letra_curp == 'X' and _interna(palabra, False) == 'N':
        n = next(j for j, letra in enumerate(palabra) if j and letra not in VOCALES)
        palabras = palabras[:i] + [palabra[:n] + 'Ñ' + palabra[n + 1:]] + palabras[i + 1:]
    return palabras


def _cuadra_curp(curp, primero, segundo, nombres):
    a1, nombre = _letras_curp(primero), _letras_curp(nombres, True)
    a2 = _letras_curp(segundo) if segundo else None
    return (a1[0] == curp[0] and curp[1] in (_interna(a1, True), 'X') and (a2[0] if a2 else 'X') == curp[2] and nombre[0] == curp[3]
            and _consonante(a1, curp[13]) == curp[13] and (_consonante(a2, curp[14]) if a2 else 'X') == curp[14]
            and _consonante(nombre, curp[15]) == curp[15])


def separar_con_curp(palabras, curp, conocidas=frozenset()):
    """Acomoda apellidos y nombres con las letras de la CURP, aunque la lista traiga palabras pegadas.

    "DIAZGARCIA FRANCO PAOLO" con DIGF... -> DIAZ, GARCIA, FRANCO PAOLO. Se prueba partir hasta dos palabras;
    gana la opción con menos cortes y con pedazos que son palabras conocidas. None si nada cuadra; si dos
    acomodos distintos empatan, el renglón queda como duda.
    """
    conocidas = conocidas | NOMBRES_CONOCIDOS | APELLIDOS_CONOCIDOS | PARTICULAS
    opciones = []
    for cortes in range(3):
        for elegidas in itertools.combinations(range(len(palabras)), cortes):
            pedazos = [[p] if i not in elegidas else None for i, p in enumerate(palabras)]
            for posiciones in itertools.product(*[range(2, len(palabras[i]) - 1) for i in elegidas]):
                for i, posicion in zip(elegidas, posiciones):
                    pedazos[i] = [palabras[i][:posicion], palabras[i][posicion:]]
                lista = [w for pedazo in pedazos for w in pedazo]
                nuevas = [w for i in elegidas for w in pedazos[i]]
                for a, b in itertools.combinations(range(1, len(lista)), 2):
                    primero, segundo, nombres = lista[:a], lista[a:b], lista[b:]
                    if primero[-1] in PARTICULAS or segundo[-1] in PARTICULAS or nombres[0] in PARTICULAS - {'DE', 'DEL'}:
                        continue
                    if _cuadra_curp(curp, primero, segundo, nombres):
                        opciones.append(((cortes, sum(w not in conocidas for w in nuevas), len(primero) + len(segundo)),
                                         ' '.join(_poner_enie(primero, curp[13])), ' '.join(_poner_enie(segundo, curp[14])),
                                         ' '.join(_poner_enie(nombres, curp[15], True))))
        if opciones:
            break  # Con menos cortes ya cuadra: no se parte más.
    if not opciones:
        return None
    opciones.sort()
    empate = len(opciones) > 1 and opciones[1][0] == opciones[0][0] and opciones[1][1:] != opciones[0][1:]
    _, primero, segundo, nombres = opciones[0]
    return {'primer_apellido': primero, 'segundo_apellido': segundo, 'nombres': separar_nombres(nombres, conocidas), 'dudoso': empate}


def separar_nombres(nombres, conocidas=frozenset()):
    """Dos nombres pegados se separan si los dos pedazos son nombres conocidos (IKERDANIEL -> IKER DANIEL), o si
    termina en un nombre conocido largo y lo de antes también parece un nombre (CITLALLINAHOMI -> CITLALLI NAHOMI)."""
    conocidas = conocidas | NOMBRES_CONOCIDOS
    salida = []
    for palabra in nombres.split():
        cortes = [(palabra[:i], palabra[i:]) for i in range(2, len(palabra) - 1)
                  if palabra not in conocidas and palabra[i:] in conocidas
                  and (palabra[:i] in conocidas or palabra[:i] in ('DE', 'DEL') or (i >= 4 and len(palabra) - i >= 6))]
        salida += list(cortes[0]) if len(cortes) == 1 else [palabra]
    return ' '.join(salida)


def lista_de_grupo(texto, apellidos_primero=True):
    """Los alumnos de una lista de grupo, un renglón por alumno: [{nombres, primer_apellido, segundo_apellido, curp, dudoso}].

    Se quitan números de lista y encabezados. Si el renglón trae CURP, el nombre se acomoda con sus letras;
    si no, se usa el orden de la lista (casi siempre apellidos primero, como en las listas de la SEP).
    """
    filas = []
    texto = mayusculas_con_enie(texto)
    repetidas = re.findall(r'[A-ZÑ]{3,}', texto)
    conocidas = frozenset(p for p in set(repetidas) if repetidas.count(p) >= 2)  # Las que aparecen sueltas más de una vez.
    for linea in texto.splitlines():
        curp = next(iter(curps(linea)), None)
        # Una CURP mal leída (dígito verificador que no cuadra) se propone, pero como duda.
        dudosa = None if curp else next(iter(curps(linea, exigir_digito=False)), None)
        # Las palabras con números (una CURP rota, una fecha) no son parte del nombre.
        limpia = ' '.join(p for p in linea.replace(curp or '\0', ' ').split() if not re.search(r'[A-Z]\d|\d[A-Z]', p))
        palabras = [p for p in re.sub(r'[^A-ZÑ]+', ' ', limpia).split()]
        palabras = [p for p in palabras if len(p) > 1 or p == 'Y']
        if not palabras or sum(p in ENCABEZADOS for p in palabras) >= max(1, len(palabras) // 2):
            continue
        if len(palabras) < 2 or len(palabras) > 7:
            continue
        persona = nombre_por_curp(' '.join(palabras), curp) if curp else None
        if persona and set(' '.join(persona.values()).split()) == set(palabras):  # Sin dejar palabras fuera.
            filas.append({**persona, 'nombres': separar_nombres(persona['nombres'], conocidas), 'curp': curp, 'dudoso': False})
            continue
        acomodo = separar_con_curp(palabras, curp, conocidas) if curp and len(palabras) <= 7 else None
        if acomodo:
            filas.append({**acomodo, 'curp': curp})
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
