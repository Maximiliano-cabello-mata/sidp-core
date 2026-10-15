"""Lector de documentos con procesos fijos: texto del PDF, QR y OCR clásico. Sin IA.

Cada herramienta es opcional. Si un equipo no la tiene, el documento queda como
"no se pudo leer" y lo revisa el administrador. Nada sale del equipo: Tesseract
corre local y los archivos temporales se borran al terminar.

Herramientas (ver validacion/requisitos.txt):
- pypdf: texto de los PDF descargados (actas de gob.mx, recibos de CFE).
- opencv: QR y calidad de la foto (qué tan borrosa está).
- Tesseract con idioma español: texto de fotos y escaneos.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TEXTO = {'.txt'}  # Documentos que ya vienen en texto: pruebas y capturas.
PDF = {'.pdf'}
IMAGEN = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
MINIMO_TEXTO = 40  # Con menos caracteres, un PDF se trata como escaneo.
BORROSA = 60.0  # Nitidez mínima (varianza del laplaciano); debajo, la foto está borrosa.
TESSERACT_WINDOWS = Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')


def _pypdf():
    try:
        import pypdf
        return pypdf
    except ImportError:
        return None


def _cv2():
    try:
        import cv2
        import numpy
        return cv2, numpy
    except ImportError:
        return None


def _tesseract():
    ruta = os.environ.get('SIDP_TESSERACT') or shutil.which('tesseract')
    if not ruta and TESSERACT_WINDOWS.exists():
        ruta = str(TESSERACT_WINDOWS)
    return ruta


def herramientas():
    """Qué herramientas tiene este equipo; va al principio del informe."""
    tesseract = _tesseract()
    idiomas = ''
    if tesseract:
        try:
            idiomas = subprocess.run([tesseract, '--list-langs'], capture_output=True, text=True, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            tesseract = None
    return {'pypdf': bool(_pypdf()), 'opencv': bool(_cv2()), 'tesseract': bool(tesseract),
            'tesseract_espanol': 'spa' in idiomas.split()}


def _ocr(ruta):
    tesseract = _tesseract()
    if not tesseract:
        return '', 'falta Tesseract para leer fotos'
    try:
        salida = subprocess.run([tesseract, str(ruta), 'stdout', '-l', 'spa'], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=180)
    except (OSError, subprocess.SubprocessError) as error:
        return '', f'Tesseract falló: {error}'
    if salida.returncode != 0:  # Sin el idioma español, intenta con el que tenga.
        salida = subprocess.run([tesseract, str(ruta), 'stdout'], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=180)
    return salida.stdout, None if salida.returncode == 0 else 'Tesseract no pudo leer la imagen'


def _imagen(datos, nombre, resultado):
    """QR, nitidez y OCR de una imagen (bytes)."""
    vision = _cv2()
    if vision:
        cv2, numpy = vision
        imagen = cv2.imdecode(numpy.frombuffer(datos, numpy.uint8), cv2.IMREAD_GRAYSCALE)
        if imagen is None:
            resultado['problemas'].append(f'{nombre}: la imagen no se pudo abrir')
            return
        nitidez = float(cv2.Laplacian(imagen, cv2.CV_64F).var())
        resultado['nitidez'] = min(resultado.get('nitidez', nitidez), nitidez)
        if nitidez < BORROSA:
            resultado['problemas'].append(f'{nombre}: la foto está borrosa')
        ok, textos, _, _ = cv2.QRCodeDetector().detectAndDecodeMulti(imagen)
        resultado['qr'] += [t for t in (textos if ok else ()) if t]
    else:
        resultado['problemas'].append(f'{nombre}: falta opencv para leer QR y medir la foto')
    with tempfile.TemporaryDirectory() as carpeta:  # Tesseract necesita un archivo; se borra al salir.
        temporal = Path(carpeta) / f'pagina{Path(nombre).suffix or ".png"}'
        temporal.write_bytes(datos)
        texto, problema = _ocr(temporal)
    resultado['texto'] += texto + '\n'
    if problema:
        resultado['problemas'].append(f'{nombre}: {problema}')
    resultado['metodo'].add('ocr')


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
                if len(resultado['texto'].strip()) < MINIMO_TEXTO:  # Escaneo: leer las imágenes de cada página.
                    for numero, pagina in enumerate(lector.pages, 1):
                        for imagen in pagina.images:
                            _imagen(imagen.data, f'{ruta.name} p{numero} {imagen.name}', resultado)
        elif extension in IMAGEN:
            _imagen(ruta.read_bytes(), ruta.name, resultado)
        else:
            resultado['problemas'].append(f'{ruta.name}: tipo de archivo no aceptado')
    except Exception as error:  # Un archivo dañado no detiene el expediente.
        resultado['problemas'].append(f'{ruta.name}: no se pudo leer ({type(error).__name__}: {error})')
    resultado['metodo'] = sorted(resultado['metodo'])
    return resultado
