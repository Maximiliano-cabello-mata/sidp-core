"""La biblioteca de la escuela en la base de la PC 4: registrar libros con una foto, prestarlos y recibirlos.

Registrar: se toma una foto de la portada (y de la contraportada, si trae código de barras). El cerebro busca, en orden:
1. El código de barras (EAN-13 = ISBN) con zxing-cpp: segundos.
2. Ese ISBN en los libros que ya tiene la escuela: si está, solo se suma otro ejemplar.
3. Ese ISBN en Open Library (internet, una sola vez por ISBN; queda guardado en sidp.biblio_consulta).
4. Sin código o sin respuesta: el modelo que ve lee la portada (título, autor, editorial). Tarda hasta un minuto.
Con el título se buscan los parecidos (pg_trgm) para no registrar dos veces el mismo libro. La persona confirma.

Cada libro físico lleva una etiqueta LIB-000123 (Code 128, validacion/codigo_barras.py) que lee el lector USB al prestar
y al devolver. Alumno: 7 días y 2 libros a la vez (sidp.biblio_regla); sin multas. Tablas: validacion/base_cerebro.sql.
"""
import base64
import json
import os
import re
import time
import urllib.request

RUTAS_POST = ('/biblioteca/identificar', '/biblioteca/alta', '/biblioteca/prestar', '/biblioteca/devolver')
TIPOS = ('libro', 'libro_texto', 'consulta', 'revista', 'otro')
SERIES = ('Al sol solito', 'Pasos de luna', 'Astrolabio', 'Espejo de Urania')
MUY_PARECIDO = 0.8  # Desde aquí es el mismo libro; entre 0.45 y 0.8 se muestran para que la persona decida.
OPEN_LIBRARY = 'https://openlibrary.org/api/books?format=json&jscmd=data&bibkeys=ISBN:'
PREGUNTA = ('Es la foto de un libro (portada, contraportada o página legal). Lee lo que está impreso: el título, el autor '
            '(o autores), la editorial, el año, el ISBN si se ve y la serie si es de Libros del Rincón (Al sol solito, Pasos de luna, '
            'Astrolabio o Espejo de Urania). Si algo no se ve, déjalo vacío. No inventes nada.')
ESQUEMA = {'type': 'object', 'properties': {c: {'type': 'string'} for c in ('titulo', 'autor', 'editorial', 'anio', 'isbn', 'serie')},
           'required': ['titulo', 'autor', 'editorial', 'anio', 'isbn', 'serie']}


class ErrorBiblioteca(Exception):
    """Algo que la persona puede corregir; el mensaje es para ella."""


def isbn13(texto):
    """El ISBN-13 con su dígito verificador correcto, o None (acepta ISBN-10, guiones y espacios)."""
    d = re.sub(r'[^0-9X]', '', str(texto or '').upper())
    if re.fullmatch(r'\d{9}[\dX]', d):
        if sum((10 if c == 'X' else int(c)) * (10 - i) for i, c in enumerate(d)) % 11:
            return None
        d = '978' + d[:9]
        return d + str((10 - sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(d)) % 10) % 10)
    if not re.fullmatch(r'97[89]\d{10}', d):
        return None
    return d if (10 - sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(d[:12])) % 10) % 10 == int(d[12]) else None


def codigos_de_barras(contenido):
    """Los ISBN que trae una foto en su código de barras (EAN-13)."""
    try:
        import cv2
        import numpy
        import zxingcpp
    except ImportError:
        return []
    imagen = cv2.imdecode(numpy.frombuffer(contenido, numpy.uint8), cv2.IMREAD_COLOR)
    if imagen is None:
        return []
    try:
        leidos = zxingcpp.read_barcodes(imagen, formats=zxingcpp.BarcodeFormat.EAN13)
    except Exception:
        return []
    return list(dict.fromkeys(i for i in (isbn13(c.text) for c in leidos) if i))


def open_library(base, isbn, espera=8):
    """Lo que sabe Open Library de un ISBN (guardado en la base: no se pregunta dos veces), o None."""
    guardado = base._consulta('SELECT encontrado, respuesta FROM sidp.biblio_consulta WHERE isbn = %s', (isbn,))
    if guardado:
        return guardado[0][1] if guardado[0][0] else None
    if os.environ.get('SIDP_SIN_INTERNET'):
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(OPEN_LIBRARY + isbn, headers={'User-Agent': 'SIDP (biblioteca escolar)'}),
                                    timeout=espera) as respuesta:
            datos = json.load(respuesta).get(f'ISBN:{isbn}')
    except (OSError, ValueError):
        return None  # Sin internet: no se guarda nada y se intenta la próxima vez.
    libro = None
    if datos:
        anio = re.search(r'\b(1[89]\d\d|20\d\d)\b', datos.get('publish_date') or '')
        libro = {'titulo': ' '.join(filter(None, (datos.get('title'), datos.get('subtitle')))),
                 'autor': '; '.join(a['name'] for a in datos.get('authors') or [] if a.get('name')),
                 'editorial': ', '.join(p['name'] for p in datos.get('publishers') or [] if p.get('name')),
                 'anio': anio.group(1) if anio else '', 'paginas': datos.get('number_of_pages')}
    base._consulta('INSERT INTO sidp.biblio_consulta (isbn, encontrado, respuesta) VALUES (%s, %s, CAST(%s AS jsonb)) '
                   'ON CONFLICT (isbn) DO NOTHING', (isbn, bool(libro), json.dumps(libro, ensure_ascii=False)))
    return libro


def _por_isbn(base, isbns):
    for isbn in isbns:
        fila = base._consulta('SELECT t.id, t.titulo, t.autor, t.ejemplares FROM sidp.biblio_isbn i JOIN sidp.v_biblio_titulos t '
                              'ON t.id = i.titulo_id WHERE i.isbn = %s', (isbn,))
        if fila:
            return dict(zip(('id', 'titulo', 'autor', 'ejemplares'), fila[0]))
    return None


def parecidos(base, titulo, autor=None):
    if not (titulo or '').strip():
        return []
    filas = base._consulta('SELECT titulo_id, titulo, autor, ejemplares, parecido FROM sidp.biblio_parecidos(%s, %s)', (titulo, autor or None))
    return [dict(zip(('id', 'titulo', 'autor', 'ejemplares', 'parecido'), f)) for f in filas]


def identificar(base, fotos, url=None):
    """Qué libro es: {existente, parecidos, propuesta, metodo, segundos}. No guarda nada (lo confirma la persona)."""
    from validacion import vision
    inicio = time.monotonic()
    contenidos = [base64.b64decode(f['contenido']) for f in fotos[:3]]
    if not contenidos:
        raise ErrorBiblioteca('Pon al menos una foto del libro.')
    isbns = list(dict.fromkeys(i for c in contenidos for i in codigos_de_barras(c)))
    salida = {'existente': None, 'parecidos': [], 'propuesta': {}, 'metodo': None, 'isbn': isbns[0] if isbns else None}
    if isbns:
        salida['existente'] = _por_isbn(base, isbns)
        if salida['existente']:
            salida.update(metodo='base', segundos=round(time.monotonic() - inicio, 1))
            return salida
        libro = open_library(base, isbns[0])
        salida['propuesta'] = {**(libro or {}), 'isbn': isbns[0]}
        salida['metodo'] = 'open_library' if libro else 'codigo_barras'
    if not salida['propuesta'].get('titulo'):
        try:
            visto, _ = vision.preguntar([vision.paginas(c, f.get('nombre', ''))[0] for c, f in zip(contenidos, fotos)], PREGUNTA, ESQUEMA,
                                        url=url, espera=300)
        except vision.ErrorVision as error:
            if not isbns:
                raise ErrorBiblioteca(f'No se pudo leer la portada ({error}). Escribe los datos a mano.')
            visto = {}
        leido = {k: ' '.join(str(visto.get(k) or '').split()) for k in ESQUEMA['properties']}
        leido['isbn'] = salida['isbn'] or isbn13(leido['isbn']) or ''
        leido['serie'] = next((s for s in SERIES if s.lower() == leido['serie'].lower()), '')
        salida['propuesta'] = {**leido, **{k: v for k, v in salida['propuesta'].items() if v}}
        salida['metodo'] = salida['metodo'] or 'visto'
        if leido['isbn'] and not salida['existente']:
            salida['existente'] = _por_isbn(base, [leido['isbn']])
    propuesta = salida['propuesta']
    if not salida['existente']:
        salida['parecidos'] = parecidos(base, propuesta.get('titulo'), propuesta.get('autor'))
        mejor = salida['parecidos'][0] if salida['parecidos'] else None
        if mejor and mejor['parecido'] >= MUY_PARECIDO:
            salida['existente'] = {k: mejor[k] for k in ('id', 'titulo', 'autor', 'ejemplares')}
    salida['segundos'] = round(time.monotonic() - inicio, 1)
    return salida


def _entero(texto, minimo, maximo):
    try:
        valor = int(str(texto).strip())
    except (TypeError, ValueError):
        return None
    return valor if minimo <= valor <= maximo else None


def alta(base, pedido, actor):
    """Un libro nuevo (o más ejemplares de uno que ya está, con titulo_id): sus etiquetas y cuántos hay ahora."""
    cuantos = _entero(pedido.get('cuantos') or 1, 1, 200)
    if not cuantos:
        raise ErrorBiblioteca('Escribe cuántos ejemplares iguales registras (de 1 a 200).')
    titulo_id = pedido.get('titulo_id')
    isbn = isbn13(pedido.get('isbn')) if pedido.get('isbn') else None
    if pedido.get('isbn') and not isbn:
        raise ErrorBiblioteca('Ese ISBN no es válido: revisa los 13 números del código de barras (o déjalo vacío).')
    if not titulo_id and isbn:
        ya = _por_isbn(base, [isbn])
        titulo_id = ya and ya['id']
    if not titulo_id:
        titulo = ' '.join(str(pedido.get('titulo') or '').split())
        if not titulo:
            raise ErrorBiblioteca('Escribe al menos el título del libro.')
        tipo = pedido.get('tipo') if pedido.get('tipo') in TIPOS else 'libro'
        serie = pedido.get('serie') if pedido.get('serie') in SERIES else None
        origen = pedido.get('origen') if pedido.get('origen') in ('codigo_barras', 'open_library', 'visto') else 'manual'
        titulo_id = base._uno(
            'INSERT INTO sidp.biblio_titulo (titulo, autor, editorial, anio, serie, tipo, paginas, origen, actor) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
            (titulo, (pedido.get('autor') or '').strip() or None, (pedido.get('editorial') or '').strip() or None,
             _entero(pedido.get('anio'), 1800, 2100), serie, tipo, _entero(pedido.get('paginas'), 1, 5000), origen, actor))
        if isbn:
            base._consulta('INSERT INTO sidp.biblio_isbn (isbn, titulo_id) VALUES (%s, %s)', (isbn, titulo_id))
    codigos = base._uno('SELECT sidp.biblio_ejemplares_alta(%s, %s, %s, %s)', (int(titulo_id), cuantos, pedido.get('ubicacion') or '', actor))
    titulo, ejemplares = base._consulta('SELECT titulo, ejemplares FROM sidp.v_biblio_titulos WHERE id = %s', (int(titulo_id),))[0]
    return {'titulo_id': titulo_id, 'titulo': titulo, 'codigos': list(codigos), 'ejemplares': ejemplares}


def resumen(base):
    """Todo lo que muestra la pestaña Biblioteca: títulos, préstamos abiertos y los alumnos por grupo (para prestar)."""
    titulos = [dict(zip(('id', 'titulo', 'autor', 'editorial', 'anio', 'serie', 'tipo', 'estado', 'ejemplares', 'disponibles',
                         'ubicacion', 'codigos', 'isbns'), f))
               for f in base._consulta('SELECT id, titulo, autor, editorial, anio, serie, tipo, estado, ejemplares, disponibles, ubicacion, '
                                       'codigos, isbns FROM sidp.v_biblio_titulos ORDER BY sidp.normalizar(titulo)')]
    prestamos = [dict(zip(('codigo', 'titulo', 'curp', 'lector', 'grupo', 'vence', 'atraso'), (*f[:5], f[5].isoformat(), f[6])))
                 for f in base._consulta('SELECT codigo, titulo, curp, lector, grupo, vence, atraso FROM sidp.v_biblio_prestamos '
                                         'ORDER BY atraso DESC, vence')]
    lectores = {}
    for grado, letra, curp, nombre in base._consulta(
            "SELECT grado, letra, curp, primer_apellido || ' ' || coalesce(segundo_apellido || ' ', '') || nombres FROM sidp.v_inscritos "
            "WHERE ciclo = (SELECT max(ciclo) FROM sidp.v_inscritos) ORDER BY grado, letra, primer_apellido, segundo_apellido, nombres"):
        lectores.setdefault(f'{grado}° {letra}', []).append({'curp': curp, 'nombre': nombre})
    return {
        'resumen': {'titulos': len(titulos), 'ejemplares': sum(t['ejemplares'] for t in titulos), 'prestados': len(prestamos),
                    'atrasados': sum(1 for p in prestamos if p['atraso'] > 0)},
        'titulos': titulos, 'prestamos': prestamos, 'lectores': [{'grupo': g, 'alumnos': a} for g, a in lectores.items()],
    }


def consultar(base, ruta, consulta):
    if ruta == '/biblioteca':
        return resumen(base)
    if ruta == '/biblioteca/etiquetas':  # Lo que lleva cada etiqueta (el servidor arma la hoja para imprimir).
        codigos = [c for c in (consulta.get('codigos', [''])[0] or '').upper().split(',') if c][:300]
        filas = base._consulta('SELECT e.codigo, t.titulo, e.ubicacion FROM sidp.biblio_ejemplar e JOIN sidp.biblio_titulo t '
                               'ON t.id = e.titulo_id WHERE e.codigo = ANY(%s) ORDER BY e.codigo', (codigos,))
        return {'etiquetas': [{'codigo': c, 'nombre': t, 'ubicacion': u} for c, t, u in filas]}
    raise ErrorBiblioteca('No existe esa consulta de la biblioteca.')


def hacer(base, ruta, pedido, url=None):
    actor = (pedido.get('actor') or 'biblioteca').strip()[:80]
    if ruta == '/biblioteca/identificar':
        return identificar(base, pedido.get('fotos') or [], url)
    if ruta == '/biblioteca/alta':
        return {**alta(base, pedido, actor), 'biblioteca': resumen(base)}
    if ruta == '/biblioteca/prestar':
        if not pedido.get('curp'):
            raise ErrorBiblioteca('Primero elige quién se lleva el libro.')
        hecho = base._uno('SELECT sidp.biblio_prestar(%s, %s, %s)', (pedido.get('codigo') or '', pedido['curp'], actor))
        return {**hecho, 'biblioteca': resumen(base)}
    if ruta == '/biblioteca/devolver':
        estado = pedido.get('estado') if pedido.get('estado') in ('bueno', 'regular', 'malo') else 'bueno'
        hecho = base._uno('SELECT sidp.biblio_devolver(%s, %s, %s)', (pedido.get('codigo') or '', estado, actor))
        return {**hecho, 'biblioteca': resumen(base)}
    raise ErrorBiblioteca('No existe esa acción de la biblioteca.')
