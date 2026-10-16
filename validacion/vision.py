"""El modelo que ve: un modelo de visión en Ollama (PC 4) que lee la hoja como la leería una persona.

Sirve para lo que el OCR no puede: letra a mano (fea u horrible), sellos, casillas marcadas y formularios
llenados a pluma. Corre solo en la PC 4, con Ollama en 127.0.0.1; la imagen nunca sale de esa PC.

Es lento en una PC sin tarjeta de video (de 30 segundos a 2 minutos por hoja), así que se usa para las hojas
que lo necesitan y en una fila que trabaja sola. Nunca decide: lo que lee es una propuesta con su nivel de
confianza, y lo dudoso lo confirma una persona.

    python -m validacion.vision modelos                    # cuáles modelos de visión hay instalados
    python -m validacion.vision prueba HOJA.jpg            # cuánto tarda en leer una hoja (solo números)
"""
import argparse
import base64
import io
import json
import os
import time
import urllib.request
from pathlib import Path

from validacion import modelo

# En orden de preferencia: el primero instalado es el que se usa. qwen3-vl lee mejor la letra a mano.
PREFERIDOS = ('qwen3-vl:8b', 'qwen2.5vl:7b', 'qwen3-vl:4b', 'qwen2.5vl:3b', 'minicpm-v:8b')
LADO = 1600  # Píxeles del lado mayor: legible para el modelo sin volverlo más lento.
CONTEXTO = 16384


class ErrorVision(Exception):
    """El modelo de visión no está o no respondió; el mensaje es para la persona."""


def _base(url=modelo.URL):
    return url.split('/api/')[0]


def instalados(url=modelo.URL, espera=10):
    """Los nombres de los modelos que tiene Ollama; [] si no responde."""
    try:
        with urllib.request.urlopen(_base(url) + '/api/tags', timeout=espera) as respuesta:
            return [m['name'] for m in json.load(respuesta).get('models', [])]
    except Exception:
        return []


def elegir(url=modelo.URL, pedido=None):
    """El modelo de visión a usar: el que se pidió (SIDP_MODELO_VISION) o el primero instalado de PREFERIDOS."""
    pedido = pedido or os.environ.get('SIDP_MODELO_VISION')
    hay = instalados(url)
    if pedido:
        return pedido if pedido in hay or f'{pedido}:latest' in hay else None
    return next((m for m in PREFERIDOS if m in hay), None)


def preparar(contenido, lado=LADO):
    """La hoja como JPEG derecho (según la foto), en color y de tamaño legible."""
    from PIL import Image, ImageOps
    imagen = Image.open(io.BytesIO(contenido))
    imagen = ImageOps.exif_transpose(imagen).convert('RGB')
    imagen.thumbnail((lado, lado))
    salida = io.BytesIO()
    imagen.save(salida, 'JPEG', quality=88)
    return salida.getvalue()


def paginas(contenido, nombre=''):
    """Cada hoja de un archivo como imagen (bytes): un PDF da una por página; una foto, una sola."""
    if contenido[:5] == b'%PDF-' or nombre.lower().endswith('.pdf'):
        import pypdfium2
        documento = pypdfium2.PdfDocument(contenido)
        salida = []
        for pagina in documento:
            imagen = pagina.render(scale=200 / 72).to_pil()
            memoria = io.BytesIO()
            imagen.save(memoria, 'PNG')
            salida.append(memoria.getvalue())
        return salida
    return [contenido]


def preguntar(imagenes, pregunta, esquema=None, nombre_modelo=None, url=modelo.URL, espera=900):
    """(respuesta, segundos). Con esquema, la respuesta es el JSON que pide el esquema."""
    nombre_modelo = nombre_modelo or elegir(url)
    if not nombre_modelo:
        raise ErrorVision('No hay modelo de visión en la PC 4 (ollama pull qwen3-vl:8b).')
    cuerpo = {
        'model': nombre_modelo, 'stream': False, 'keep_alive': '30m',
        'options': {'temperature': 0, 'num_ctx': CONTEXTO},
        'messages': [{'role': 'user', 'content': pregunta,
                      'images': [base64.b64encode(preparar(i)).decode() for i in imagenes]}],
    }
    if esquema:
        cuerpo['format'] = esquema
    inicio = time.monotonic()
    try:
        solicitud = urllib.request.Request(url, json.dumps(cuerpo).encode(), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
            texto = json.load(respuesta)['message']['content']
    except Exception as error:
        raise ErrorVision(f'El modelo de visión no respondió: {type(error).__name__}: {error}') from error
    segundos = round(time.monotonic() - inicio, 1)
    if not esquema:
        return texto, segundos
    try:
        return json.loads(texto), segundos
    except json.JSONDecodeError as error:
        raise ErrorVision('El modelo de visión no devolvió datos en orden.') from error


TRANSCRIBIR = ('Transcribe todo el texto de esta hoja, renglón por renglón, tal como está escrito, incluida la letra a '
               'mano. Si una palabra no se entiende, escribe [ilegible]. No expliques nada.')


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.vision')
    parser.add_argument('accion', choices=('modelos', 'prueba'))
    parser.add_argument('archivo', nargs='?', type=Path)
    parser.add_argument('--modelo', help='por omisión, el primero instalado de: ' + ', '.join(PREFERIDOS))
    parser.add_argument('--mostrar', action='store_true', help='imprime lo leído (solo con documentos inventados)')
    args = parser.parse_args(argumentos)
    if args.accion == 'modelos':
        hay = instalados()
        print('Modelos en Ollama: ' + (', '.join(hay) if hay else 'Ollama no respondió'))
        print(f'Modelo de visión que se usará: {elegir(pedido=args.modelo) or "ninguno (falta instalarlo)"}')
        return 0
    if not args.archivo or not args.archivo.is_file():
        print('Falta la hoja: python -m validacion.vision prueba HOJA.jpg')
        return 1
    hoja = paginas(args.archivo.read_bytes(), args.archivo.name)[0]
    try:
        texto, segundos = preguntar([hoja], TRANSCRIBIR, nombre_modelo=elegir(pedido=args.modelo))
    except ErrorVision as error:
        print(error)
        return 1
    print(f'Leyó la hoja en {segundos} s: {len(texto)} caracteres, {len(texto.splitlines())} renglones, '
          f'{texto.count("[ilegible]")} partes ilegibles.')
    if args.mostrar:
        print(texto)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
