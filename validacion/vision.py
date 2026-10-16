"""El modelo que ve: un modelo de visión en Ollama (PC 4) que lee la hoja como la leería una persona.

Sirve para lo que el OCR no puede: letra a mano (fea u horrible), sellos, casillas marcadas y formularios
llenados a pluma. Corre solo en la PC 4, con Ollama en 127.0.0.1; la imagen nunca sale de esa PC.

Es lento en una PC sin tarjeta de video (en la PC 4, qwen2.5vl:3b tarda de 1 a 2 minutos por hoja), así que se
usa solo en las hojas que lo necesitan y en una fila que trabaja sola. Casi todo el tiempo se va en "ver" la imagen
(tokens de la imagen), no en escribir: por eso la hoja se achica a LADO píxeles y el modelo no "piensa" en voz alta
(qwen3-vl lo hace por omisión y tardaba 9 minutos por hoja). Nunca decide: lo que lee es una propuesta con su
nivel de confianza, y lo dudoso lo confirma una persona.

Ajustes (en la PC 4 van en C:\\SIDP-datos\\servicios\\ajustes.ps1):
    SIDP_MODELO_VISION   el modelo a usar (por omisión, el primero instalado de PREFERIDOS)
    SIDP_LADO_VISION     píxeles del lado mayor de la hoja (por omisión 1280)

    python -m validacion.vision modelos                    # cuáles modelos de visión hay instalados
    python -m validacion.vision prueba HOJA.jpg            # cuánto tarda en leer una hoja (solo números)
"""
import argparse
import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from validacion import modelo

# En orden de preferencia: el primero instalado es el que se usa. qwen3-vl lee mejor la letra a mano, pero en una PC
# sin tarjeta de video es lento: en la PC 4 el ajuste SIDP_MODELO_VISION fija qwen2.5vl:3b (Tarea 012).
PREFERIDOS = ('qwen3-vl:8b', 'qwen2.5vl:7b', 'qwen3-vl:4b', 'qwen2.5vl:3b', 'minicpm-v:8b')
# Píxeles del lado mayor. Los tokens de la imagen crecen con el área: 1600 daba unos 3,000 (103 s en la PC 4);
# 1280, unos 1,900; 960, unos 1,100. Menos es más rápido, pero la letra chica se pierde: se mide con medir_lectura.
LADO = int(os.environ.get('SIDP_LADO_VISION') or 1280)
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
    hay = instalados(url)
    if pedido:  # Pedido a mano (--modelo): ese o ninguno, para no medir otro sin darse cuenta.
        return pedido if pedido in hay or f'{pedido}:latest' in hay else None
    ajuste = os.environ.get('SIDP_MODELO_VISION')
    if ajuste and (ajuste in hay or f'{ajuste}:latest' in hay):
        return ajuste
    return next((m for m in PREFERIDOS if m in hay), None)  # El del ajuste no está instalado: el mejor que haya.


def preparar(contenido, lado=None):
    """La hoja como JPEG derecho (según la foto), en color y de tamaño legible."""
    from PIL import Image, ImageOps
    lado = lado or LADO
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


def _pedir(url, cuerpo, espera):
    solicitud = urllib.request.Request(url, json.dumps(cuerpo).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return (json.load(respuesta).get('message') or {}).get('content', '')


def cargar(nombre_modelo, url=modelo.URL, espera=900):
    """Sube el modelo a la memoria antes de medir (desde un disco mecánico tarda minutos). Segundos que tardó."""
    inicio = time.monotonic()
    try:
        _pedir(url, {'model': nombre_modelo, 'messages': [], 'keep_alive': '30m'}, espera)
    except Exception:
        pass  # Si no se pudo, la primera hoja tardará más; no es un error.
    return round(time.monotonic() - inicio, 1)


def preguntar(imagenes, pregunta, esquema=None, nombre_modelo=None, url=modelo.URL, espera=900):
    """(respuesta, segundos). Con esquema, la respuesta es el JSON que pide el esquema."""
    nombre_modelo = nombre_modelo or elegir(url)
    if not nombre_modelo:
        raise ErrorVision('No hay modelo de visión en la PC 4 (ollama pull qwen2.5vl:3b).')
    # La imagen va antes que la pregunta: en la segunda lectura de la misma hoja Ollama reusa lo que ya vio.
    cuerpo = {
        'model': nombre_modelo, 'stream': False, 'keep_alive': '30m', 'think': False,
        'options': {'temperature': 0, 'num_ctx': CONTEXTO},
        'messages': [{'role': 'user', 'content': pregunta,
                      'images': [base64.b64encode(preparar(i)).decode() for i in imagenes]}],
    }
    if esquema:
        cuerpo['format'] = esquema
    inicio = time.monotonic()
    try:
        texto = _pedir(url, cuerpo, espera)
    except urllib.error.HTTPError as error:
        if error.code != 400 or 'think' not in error.read().decode(errors='replace'):
            raise ErrorVision(f'El modelo de visión no respondió: HTTP {error.code}') from error
        cuerpo.pop('think')  # Un Ollama o un modelo que no conoce "think": se pide sin él.
        try:
            texto = _pedir(url, cuerpo, espera)
        except Exception as otro:
            raise ErrorVision(f'El modelo de visión no respondió: {type(otro).__name__}: {otro}') from otro
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
    global LADO
    parser = argparse.ArgumentParser(prog='python -m validacion.vision')
    parser.add_argument('accion', choices=('modelos', 'prueba'))
    parser.add_argument('archivo', nargs='?', type=Path)
    parser.add_argument('--modelo', help='por omisión, el primero instalado de: ' + ', '.join(PREFERIDOS))
    parser.add_argument('--lado', type=int, help=f'píxeles del lado mayor de la hoja (por omisión {LADO})')
    parser.add_argument('--mostrar', action='store_true', help='imprime lo leído (solo con documentos inventados)')
    args = parser.parse_args(argumentos)
    LADO = args.lado or LADO
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
