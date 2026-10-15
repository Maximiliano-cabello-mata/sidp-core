"""Opinión del modelo local (Ollama) sobre una comparación en zona gris.

El modelo solo recibe dos textos y el tipo (nombre o domicilio), nunca el
documento ni la ficha completa. Si no responde, la respuesta es "duda": el
caso sigue en revisión manual y nada se detiene.
"""
import json
import time
import urllib.request

URL = 'http://127.0.0.1:11434/api/chat'
MODELO = 'sidp-revisor-2'  # Mejor resultado en la tarea 002.
ESQUEMA = {
    'type': 'object',
    'properties': {
        'misma': {'type': 'string', 'enum': ['si', 'no', 'duda']},
        'motivo': {'type': 'string'},
    },
    'required': ['misma', 'motivo'],
}


def pregunta(gris):
    cosa = 'la misma persona' if gris['tipo'] == 'nombre' else 'el mismo domicilio'
    return (f'¿Estos dos textos se refieren a {cosa}?\n'
            f'Texto A: {json.dumps(gris["a"], ensure_ascii=False)}\n'
            f'Texto B: {json.dumps(gris["b"], ensure_ascii=False)}')


def opinar(gris, modelo=MODELO, url=URL, espera=120):
    cuerpo = json.dumps({
        'model': modelo, 'stream': False, 'format': ESQUEMA,
        'options': {'temperature': 0},
        'messages': [{'role': 'user', 'content': pregunta(gris)}],
    }).encode()
    inicio = time.monotonic()
    try:
        solicitud = urllib.request.Request(url, cuerpo, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
            datos = json.load(respuesta)
        opinion = json.loads(datos['message']['content'])
        if opinion.get('misma') not in ('si', 'no', 'duda'):
            raise ValueError(f'respuesta fuera del formato: {opinion}')
    except Exception as error:  # Sin modelo, el caso sigue en revisión manual.
        opinion = {'misma': 'duda', 'motivo': f'sin respuesta del modelo: {error}'}
    opinion['segundos'] = round(time.monotonic() - inicio, 1)
    return opinion


def opinar_remoto(gris, url, clave, espera=150):
    """Opinión del cerebro de otra PC, por IP, a través de validacion/cerebro_red.py. Sin respuesta: "duda"."""
    inicio = time.monotonic()
    cuerpo = json.dumps({'tipo': gris['tipo'], 'a': gris['a'], 'b': gris['b']}).encode()
    try:
        solicitud = urllib.request.Request(url.rstrip('/') + '/opinar', cuerpo,
                                           {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
        with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
            opinion = json.load(respuesta)
        if opinion.get('misma') not in ('si', 'no', 'duda'):
            raise ValueError(f'respuesta fuera del formato: {opinion}')
    except Exception as error:  # Sin cerebro, el caso sigue en revisión manual.
        opinion = {'misma': 'duda', 'motivo': f'sin respuesta del cerebro: {error}'}
    opinion['segundos'] = round(time.monotonic() - inicio, 1)
    return opinion


def salud_remota(url, clave, espera=5):
    """None si el cerebro responde con esa clave; si no, el motivo."""
    try:
        solicitud = urllib.request.Request(url.rstrip('/') + '/salud', headers={'X-SIDP-Clave': clave})
        with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
            return None if json.load(respuesta).get('ok') else 'respuesta inesperada'
    except Exception as error:
        return str(error)

