"""Lector de documentos con procesos fijos: texto del PDF, códigos y OCR. Sin IA.

Cada herramienta es opcional. Si un equipo no la tiene, usa la siguiente; si no queda
ninguna, el documento queda como "no se pudo leer" y lo revisa el administrador. Nada sale
del equipo: todo corre local y los archivos temporales se borran al terminar.

Herramientas (ver validacion/requisitos.txt):
- pypdf: texto de los PDF descargados (actas de gob.mx, recibos de CFE).
- pypdfium2: convierte cada página de un PDF escaneado en imagen.
- opencv: endereza la foto (orillas, perspectiva, giro, contraste), mide qué tan borrosa está y lee QR.
- zxing-cpp: lee QR y códigos de barras mejor que opencv.
- PaddleOCR: lector principal de fotos y escaneos en español.
- Tesseract con español: respaldo de PaddleOCR y detector del giro de la página.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

TEXTO = {'.txt'}  # Documentos que ya vienen en texto: pruebas y capturas.
PDF = {'.pdf'}
IMAGEN = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
MINIMO_TEXTO = 40  # Con menos caracteres, un PDF se trata como escaneo.
BORROSA = 60.0  # Nitidez mínima (varianza del laplaciano); debajo, la foto está borrosa.
PAGINAS_MAXIMAS = 4  # De un PDF escaneado solo se leen las primeras páginas.
LADO_OCR = 2200  # Lado mayor, en pixeles, con el que se lee una página.
TESSERACT_WINDOWS = Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')


def _modulo(nombre):
    try:
        return __import__(nombre)
    except Exception:  # Un paquete a medio instalar también cuenta como que no está.
        return None


def _pypdf():
    return _modulo('pypdf')


def _cv2():
    cv2, numpy = _modulo('cv2'), _modulo('numpy')
    return (cv2, numpy) if cv2 and numpy else None


def _tesseract():
    ruta = os.environ.get('SIDP_TESSERACT') or shutil.which('tesseract')
    if not ruta and TESSERACT_WINDOWS.exists():
        ruta = str(TESSERACT_WINDOWS)
    return ruta


_PADDLE = {}


def _paddle():
    """PaddleOCR en español, cargado una sola vez. None si no está o no arranca."""
    if 'ocr' not in _PADDLE:
        _PADDLE['ocr'] = None
        if os.environ.get('SIDP_SIN_PADDLE'):
            return None
        modulo = _modulo('paddleocr')
        if modulo:
            for opciones in ({'lang': 'es', 'use_doc_orientation_classify': False, 'use_doc_unwarping': False,
                              'use_textline_orientation': True},  # PaddleOCR 3
                             {'lang': 'es', 'use_angle_cls': True, 'show_log': False}):  # PaddleOCR 2
                try:
                    _PADDLE['ocr'] = modulo.PaddleOCR(**opciones)
                    break
                except Exception as error:
                    _PADDLE.setdefault('error', f'{type(error).__name__}: {error}')  # El primer intento dice más.
    return _PADDLE['ocr']


def _texto_paddle(ocr, imagen):
    """Texto de PaddleOCR en renglones, de arriba abajo; acepta la salida de las versiones 2 y 3."""
    piezas = []  # (y, x, texto)
    if hasattr(ocr, 'predict'):
        for pagina in ocr.predict(imagen):
            datos = pagina.json.get('res', pagina.json) if hasattr(pagina, 'json') else pagina
            for texto, caja in zip(datos.get('rec_texts', []), datos.get('rec_boxes', datos.get('rec_polys', []))):
                caja = [float(v) for v in (caja if len(caja) == 4 and not hasattr(caja[0], '__len__') else
                                           (min(p[0] for p in caja), min(p[1] for p in caja), 0, 0))]
                piezas.append((caja[1], caja[0], texto))
    else:
        for pagina in ocr.ocr(imagen, cls=True) or []:
            for caja, (texto, _) in pagina or []:
                piezas.append((min(p[1] for p in caja), min(p[0] for p in caja), texto))
    piezas.sort()
    renglones, actual, y_actual = [], [], None
    for y, x, texto in piezas:  # Junta en un renglón las piezas a la misma altura.
        if y_actual is not None and y - y_actual > 18:
            renglones.append(' '.join(t for _, t in sorted(actual)))
            actual = []
        y_actual = y if not actual else y_actual
        actual.append((x, texto))
    if actual:
        renglones.append(' '.join(t for _, t in sorted(actual)))
    return '\n'.join(renglones)


def _ocr_tesseract(imagen, cv2):
    tesseract = _tesseract()
    if not tesseract:
        return '', 'falta Tesseract para leer fotos'
    with tempfile.TemporaryDirectory() as carpeta:  # Tesseract necesita un archivo; se borra al salir.
        temporal = Path(carpeta) / 'pagina.png'
        cv2.imwrite(str(temporal), imagen)
        for idioma in (['-l', 'spa'], []):  # Sin el idioma español, intenta con el que tenga.
            try:
                salida = subprocess.run([tesseract, str(temporal), 'stdout', '--psm', '3', *idioma], capture_output=True,
                                        text=True, encoding='utf-8', errors='replace', timeout=180)
            except (OSError, subprocess.SubprocessError) as error:
                return '', f'Tesseract falló: {error}'
            if salida.returncode == 0:
                return salida.stdout, None
    return '', 'Tesseract no pudo leer la imagen'


def _puntaje(gris, cv2):
    """Qué tan legible lee Tesseract la página: letras de palabras seguras (confianza 60 o más)."""
    tesseract = _tesseract()
    if not tesseract:
        return 0
    escala = 1200 / max(gris.shape[:2])
    chica = cv2.resize(gris, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA) if escala < 1 else gris
    with tempfile.TemporaryDirectory() as carpeta:
        temporal = Path(carpeta) / 'pagina.png'
        cv2.imwrite(str(temporal), chica)
        try:
            salida = subprocess.run([tesseract, str(temporal), 'stdout', '--psm', '3', 'tsv'], capture_output=True,
                                    text=True, encoding='utf-8', errors='replace', timeout=60).stdout
        except (OSError, subprocess.SubprocessError):
            return 0
    puntos = 0
    for renglon in salida.splitlines()[1:]:
        partes = renglon.split('\t')
        if len(partes) == 12 and partes[11].strip().isalpha() and len(partes[11].strip()) >= 3:
            try:
                puntos += len(partes[11].strip()) if float(partes[10]) >= 60 else 0
            except ValueError:
                pass
    return puntos


GIROS = {90: 'ROTATE_90_CLOCKWISE', 180: 'ROTATE_180', 270: 'ROTATE_90_COUNTERCLOCKWISE'}


def _girar(imagen, grados, cv2):
    return cv2.rotate(imagen, getattr(cv2, GIROS[grados])) if grados else imagen


def _mejor_giro(gris, cv2):
    """Si la página no se lee derecha, prueba girarla 90, 180 y 270 grados y se queda con la que mejor se lee."""
    puntos = {0: _puntaje(gris, cv2)}
    if puntos[0] >= 60:
        return 0
    for grados in GIROS:
        puntos[grados] = _puntaje(_girar(gris, grados, cv2), cv2)
    mejor = max(puntos, key=puntos.get)
    return mejor if puntos[mejor] > puntos[0] * 1.5 + 10 else 0


def nitidez(gris, cv2, numpy):
    """Nitidez de la parte con letras: varianza del laplaciano en los cuadros más nítidos (la hoja en blanco no cuenta)."""
    escala = 1500 / max(gris.shape[:2])
    gris = cv2.resize(gris, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC)
    laplaciano = cv2.Laplacian(gris, cv2.CV_64F)
    alto, ancho = gris.shape
    cuadros = [laplaciano[y:y + 100, x:x + 100].var() for y in range(0, alto - 99, 100) for x in range(0, ancho - 99, 100)]
    cuadros.sort(reverse=True)
    mejores = cuadros[:max(1, len(cuadros) // 10)]
    return float(sum(mejores) / len(mejores))


def _ordenar_esquinas(puntos, numpy):
    puntos = puntos.reshape(4, 2).astype('float32')
    suma, resta = puntos.sum(axis=1), numpy.diff(puntos, axis=1).ravel()
    return numpy.array([puntos[suma.argmin()], puntos[resta.argmin()], puntos[suma.argmax()], puntos[resta.argmax()]], dtype='float32')


def recortar_documento(imagen, cv2, numpy):
    """Si la foto muestra el documento sobre una mesa, lo recorta y le quita la perspectiva."""
    alto, ancho = imagen.shape[:2]
    escala = 800 / max(alto, ancho)
    chica = cv2.resize(imagen, None, fx=escala, fy=escala) if escala < 1 else imagen.copy()
    escala = min(escala, 1)
    gris = cv2.GaussianBlur(cv2.cvtColor(chica, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    orillas = cv2.dilate(cv2.Canny(gris, 50, 150), numpy.ones((3, 3), numpy.uint8))
    contornos, _ = cv2.findContours(orillas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_total = chica.shape[0] * chica.shape[1]
    for contorno in sorted(contornos, key=cv2.contourArea, reverse=True)[:5]:
        figura = cv2.approxPolyDP(contorno, 0.02 * cv2.arcLength(contorno, True), True)
        area = cv2.contourArea(figura)
        if len(figura) == 4 and 0.2 * area_total < area < 0.98 * area_total:
            esquinas = _ordenar_esquinas(figura, numpy) / escala
            (a, b, c, d) = esquinas
            ancho_n = int(max(numpy.linalg.norm(b - a), numpy.linalg.norm(c - d)))
            alto_n = int(max(numpy.linalg.norm(d - a), numpy.linalg.norm(c - b)))
            destino = numpy.array([[0, 0], [ancho_n - 1, 0], [ancho_n - 1, alto_n - 1], [0, alto_n - 1]], dtype='float32')
            matriz = cv2.getPerspectiveTransform(esquinas, destino)
            return cv2.warpPerspective(imagen, matriz, (ancho_n, alto_n)), True
    return imagen, False


def preparar(imagen, cv2, numpy, girar=True):
    """Endereza la página para leerla: recorte y perspectiva, tamaño, sombra y giro."""
    pasos = []
    imagen, recortada = recortar_documento(imagen, cv2, numpy)
    if recortada:
        pasos.append('recortada')
        alto, ancho = imagen.shape[:2]
        orilla = int(0.012 * max(alto, ancho))  # Quita el filo de la mesa que queda en la orilla.
        imagen = imagen[orilla:alto - orilla, orilla:ancho - orilla]
    alto, ancho = imagen.shape[:2]
    escala = LADO_OCR / max(alto, ancho)
    if escala > 1.15 or escala < 0.85:
        imagen = cv2.resize(imagen, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC if escala > 1 else cv2.INTER_AREA)
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    fondo = cv2.GaussianBlur(gris, (0, 0), 25)
    gris = cv2.divide(gris, fondo, scale=255)  # Quita sombras: cada pixel contra la luz de su alrededor.
    giro = _mejor_giro(gris, cv2) if girar else 0
    if giro:
        imagen, gris = _girar(imagen, giro, cv2), _girar(gris, giro, cv2)
        pasos.append(f'girada {giro}°')
    return imagen, gris, pasos


def _codigos(imagenes, cv2, resultado):
    """QR y códigos de barras: zxing-cpp si está; si no, el detector de QR de opencv."""
    zxing = _modulo('zxingcpp')
    encontrados = []
    for imagen in imagenes:
        if zxing:
            try:
                encontrados += [c.text for c in zxing.read_barcodes(imagen) if c.text]
            except Exception:
                pass
        else:
            try:
                ok, textos, _, _ = cv2.QRCodeDetector().detectAndDecodeMulti(imagen)
                encontrados += [t for t in (textos if ok else ()) if t]
            except cv2.error:
                pass
        if encontrados:
            break
    for texto in encontrados:
        if texto not in resultado['qr']:
            resultado['qr'].append(texto)


def _imagen(datos, nombre, resultado):
    """Códigos, nitidez y OCR de una imagen (bytes de un archivo o arreglo de pixeles)."""
    vision = _cv2()
    if not vision:
        resultado['problemas'].append(f'{nombre}: falta opencv para leer fotos')
        return
    cv2, numpy = vision
    imagen = datos if isinstance(datos, numpy.ndarray) else cv2.imdecode(numpy.frombuffer(datos, numpy.uint8), cv2.IMREAD_COLOR)
    if imagen is None:
        resultado['problemas'].append(f'{nombre}: la imagen no se pudo abrir')
        return
    if imagen.ndim == 2:
        imagen = cv2.cvtColor(imagen, cv2.COLOR_GRAY2BGR)
    elif imagen.shape[2] == 4:
        imagen = cv2.cvtColor(imagen, cv2.COLOR_BGRA2BGR)
    if min(imagen.shape[:2]) < 500:
        resultado['problemas'].append(f'{nombre}: la foto es muy pequeña ({imagen.shape[1]}x{imagen.shape[0]})')
    color, gris, pasos = preparar(imagen, cv2, numpy)
    valor = nitidez(cv2.cvtColor(color, cv2.COLOR_BGR2GRAY), cv2, numpy)
    resultado['nitidez'] = round(min(resultado.get('nitidez', valor), valor), 1)
    if valor < BORROSA:
        resultado['problemas'].append(f'{nombre}: la foto está borrosa')
    resultado.setdefault('preparacion', []).extend(f'{nombre}: {p}' for p in pasos)
    _codigos([imagen, gris], cv2, resultado)
    texto, problema = '', None
    ocr = _paddle()
    if ocr:
        try:
            texto = _texto_paddle(ocr, color)
            resultado['metodo'].add('paddleocr')
        except Exception as error:
            problema = f'PaddleOCR falló ({type(error).__name__}: {error})'
    if len(texto.strip()) < MINIMO_TEXTO:  # Sin PaddleOCR, o si no leyó nada: Tesseract.
        texto_t, problema_t = _ocr_tesseract(gris, cv2)
        if texto_t.strip():
            texto, problema = texto_t, None
            resultado['metodo'].add('ocr')
        else:
            problema = problema or problema_t
    resultado['texto'] += texto + '\n'
    if problema:
        resultado['problemas'].append(f'{nombre}: {problema}')


def _paginas_pdf(ruta, lector, resultado):
    """Cada página del PDF escaneado como imagen: pypdfium2 si está; si no, las imágenes que trae pypdf."""
    pdfium = _modulo('pypdfium2')
    if pdfium:
        documento = pdfium.PdfDocument(str(ruta))
        try:
            for numero in range(min(len(documento), PAGINAS_MAXIMAS)):
                pagina = documento[numero]
                escala = min(300 / 72, LADO_OCR / max(pagina.get_size()))  # Hasta 300 ppp.
                yield f'{ruta.name} p{numero + 1}', pagina.render(scale=escala).to_numpy()
        finally:
            documento.close()
        return
    for numero, pagina in enumerate(lector.pages[:PAGINAS_MAXIMAS], 1):
        try:
            for imagen in pagina.images:
                yield f'{ruta.name} p{numero} {imagen.name}', imagen.data
        except Exception as error:  # pypdf sin Pillow no puede sacar las imágenes.
            resultado['problemas'].append(f'{ruta.name} p{numero}: falta pypdfium2 o Pillow para leer el escaneo ({type(error).__name__})')
            return


def herramientas():
    """Qué herramientas tiene este equipo; va al principio del informe."""
    tesseract = _tesseract()
    idiomas = ''
    if tesseract:
        try:
            idiomas = subprocess.run([tesseract, '--list-langs'], capture_output=True, text=True, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            tesseract = None
    return {'pypdf': bool(_pypdf()), 'pypdfium2': bool(_modulo('pypdfium2')), 'opencv': bool(_cv2()),
            'zxing': bool(_modulo('zxingcpp')), 'paddleocr': bool(_paddle()), 'tesseract': bool(tesseract),
            'tesseract_espanol': 'spa' in idiomas.split(), 'tesseract_giro': 'osd' in idiomas.split(),
            **({'paddleocr_error': _PADDLE['error']} if _PADDLE.get('error') and not _PADDLE.get('ocr') else {})}


def leer(ruta):
    """Texto, QR y problemas de un archivo. Nunca lanza error: lo que falla queda en 'problemas'."""
    ruta = Path(ruta)
    resultado = {'archivo': ruta.name, 'texto': '', 'qr': [], 'metodo': set(), 'problemas': []}
    extension = ruta.suffix.lower()
    try:
        if extension in TEXTO:
            resultado['texto'] = ruta.read_text(encoding='utf-8', errors='replace')
            resultado['metodo'].add('texto')
        elif extension in PDF:
            pypdf = _pypdf()
            if not pypdf:
                resultado['problemas'].append(f'{ruta.name}: falta pypdf para leer PDF')
            else:
                lector = pypdf.PdfReader(str(ruta))
                resultado['texto'] = '\n'.join(pagina.extract_text() or '' for pagina in lector.pages)
                resultado['metodo'].add('pdf')
                if len(resultado['texto'].strip()) < MINIMO_TEXTO:  # Escaneo: leer cada página como imagen.
                    for nombre, imagen in _paginas_pdf(ruta, lector, resultado):
                        _imagen(imagen, nombre, resultado)
        elif extension in IMAGEN:
            _imagen(ruta.read_bytes(), ruta.name, resultado)
        else:
            resultado['problemas'].append(f'{ruta.name}: tipo de archivo no aceptado')
    except Exception as error:  # Un archivo dañado no detiene el expediente.
        resultado['problemas'].append(f'{ruta.name}: no se pudo leer ({type(error).__name__}: {error})')
    resultado['metodo'] = sorted(resultado['metodo'])
    return resultado


if __name__ == '__main__':  # python -m validacion.lector ARCHIVO: qué lee de un documento (se queda en la pantalla).
    import json
    import sys
    print(json.dumps(herramientas(), ensure_ascii=False))
    for archivo in sys.argv[1:]:
        lectura = leer(archivo)
        print(f'\n== {archivo}: {", ".join(lectura["metodo"]) or "sin leer"} · nitidez {lectura.get("nitidez", "-")}')
        for linea in lectura.get('preparacion', []) + lectura['problemas']:
            print(f'   {linea}')
        print(lectura['texto'].strip() or '(sin texto)')
        for codigo in lectura['qr']:
            print(f'   código: {codigo}')
