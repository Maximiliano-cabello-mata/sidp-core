"""Convierte el ejemplo inventado en fotos de celular y escaneos, para medir la lectura.

Cada documento de texto se dibuja como hoja y se le pone lo que tienen las fotos reales:
mesa de fondo, perspectiva, giro de 90°, sombra, poca resolución o escaneo en PDF. Los datos
siguen siendo inventados, así que el resultado se puede subir al repositorio como números.
La carpeta de salida debe quedar fuera del repositorio.

    python -m validacion.ejemplo.fotos C:\\Users\\<usuario>\\SIDP-fotos
    python -m validacion.prueba C:\\Users\\<usuario>\\SIDP-fotos --hoy 2026-10-14 --sin-modelo
"""
import argparse
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
VARIANTES = ('derecha', 'perspectiva', 'girada', 'sombra', 'escaneo', 'chica')


def fuente(tamano):
    from PIL import ImageFont
    for nombre in ('arial.ttf', 'DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                   '/System/Library/Fonts/Supplemental/Arial.ttf'):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default(size=tamano)


def hoja(texto):
    """El texto del documento dibujado en una hoja carta a unos 200 ppp."""
    from PIL import Image, ImageDraw
    imagen = Image.new('RGB', (1700, 2200), 'white')
    dibujo, letra, titulo = ImageDraw.Draw(imagen), fuente(36), fuente(48)
    y = 120
    for numero, renglon in enumerate(texto.splitlines()):
        if renglon.strip():
            dibujo.text((120, y), renglon, fill=(25, 25, 25), font=titulo if numero == 0 else letra)
        y += 70 if numero == 0 else 52
    return imagen


def deformar(imagen, variante, cv2, numpy):
    """La hoja como la tomaría un celular (o un escáner)."""
    pagina = cv2.cvtColor(numpy.array(imagen), cv2.COLOR_RGB2BGR)
    if variante in ('escaneo', 'derecha'):
        return pagina
    if variante == 'chica':
        return cv2.resize(pagina, None, fx=0.35, fy=0.35, interpolation=cv2.INTER_AREA)
    alto, ancho = pagina.shape[:2]
    mesa = numpy.full((alto + 700, ancho + 900, 3), (60, 75, 95), numpy.uint8)  # Mesa de madera oscura.
    origen = numpy.float32([[0, 0], [ancho, 0], [ancho, alto], [0, alto]])
    destino = numpy.float32([[520, 380], [ancho + 380, 260], [ancho + 470, alto + 470], [380, alto + 350]])
    matriz = cv2.getPerspectiveTransform(origen, destino)
    foto = cv2.warpPerspective(pagina, matriz, (mesa.shape[1], mesa.shape[0]), dst=mesa, borderMode=cv2.BORDER_TRANSPARENT)
    if variante in ('sombra', 'girada'):
        degradado = numpy.linspace(0.45, 1.0, foto.shape[1], dtype=numpy.float32)[None, :, None]
        foto = (foto.astype(numpy.float32) * degradado).astype(numpy.uint8)
    if variante == 'girada':
        foto = cv2.rotate(foto, cv2.ROTATE_90_COUNTERCLOCKWISE)
    foto = cv2.GaussianBlur(foto, (3, 3), 0)
    return cv2.resize(foto, None, fx=0.75, fy=0.75, interpolation=cv2.INTER_AREA)


def generar(destino):
    try:
        import cv2
        import numpy
        from PIL import Image
    except ImportError:
        print('Hace falta opencv y Pillow: python -m pip install -r validacion/requisitos.txt', file=sys.stderr)
        raise SystemExit(2)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy(AQUI / 'etiquetas.csv', destino / 'etiquetas.csv')
    cuenta = 0
    for carpeta in sorted((AQUI / 'expedientes').iterdir()):
        salida = destino / 'expedientes' / carpeta.name
        if salida.exists():
            shutil.rmtree(salida)
        salida.mkdir(parents=True)
        shutil.copy(carpeta / 'captura.json', salida / 'captura.json')
        for documento in sorted(carpeta.glob('*.txt')):
            variante = VARIANTES[cuenta % len(VARIANTES)]
            cuenta += 1
            foto = deformar(hoja(documento.read_text(encoding='utf-8')), variante, cv2, numpy)
            if variante == 'escaneo':  # PDF sin texto, solo la imagen: como sale de un escáner.
                Image.fromarray(cv2.cvtColor(foto, cv2.COLOR_BGR2RGB)).save(salida / f'{documento.stem}.pdf', resolution=200)
            else:
                cv2.imwrite(str(salida / f'{documento.stem}.jpg'), foto, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return cuenta


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.ejemplo.fotos')
    parser.add_argument('destino', type=Path, help='Carpeta fuera del repositorio')
    args = parser.parse_args(argumentos)
    print(f'{generar(args.destino)} documentos convertidos en fotos y escaneos en {args.destino}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
