"""SIDP-Biblioteca.exe: la computadora de la biblioteca, con cámara para las portadas y lector de código de barras.

La biblioteca vive en el servidor (SIDP.exe, puerto 8770) y en la base de la PC 4. Este programa abre su pantalla en una
ventana propia a través de esta misma computadora (http://127.0.0.1:8772): el navegador solo deja usar la cámara en
páginas seguras o locales, y así la cámara sirve para fotografiar las portadas. Todo pasa tal cual al servidor; aquí no
se guarda ningún dato de los alumnos. Se entra con una cuenta de Ajustes > Cuentas (Apoyo, Secretaría o Dirección).

- La primera vez busca el servidor en la red de la escuela y lo recuerda (o se le dice con --servidor).
- Al cerrar la ventana, el programa termina.

    SIDP-Biblioteca.exe
    SIDP-Biblioteca.exe --servidor http://192.168.1.20:8770
"""
import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PUERTO = 8772
PUERTO_SERVIDOR = 8770
PASAN = ('Content-Type', 'X-SIDP-Token', 'X-SIDP-Nombre')  # Lo que el panel manda y el servidor necesita.
REGRESAN = ('Content-Type', 'Content-Disposition', 'Cache-Control', 'X-Content-Type-Options')
MAXIMO = 100 * 1024 * 1024


def carpeta():
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.sidp')
    destino = base / 'SIDP' / 'biblioteca'
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def es_servidor(url, espera=1.5):
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/api/hola', timeout=espera) as respuesta:
            return json.load(respuesta).get('sidp') == 'servidor'
    except Exception:
        return False


def buscar_servidor(guardado=None, redes=None):
    """La dirección del servidor de la escuela: la guardada si contesta; si no, se recorre la red local."""
    if guardado and es_servidor(guardado):
        return guardado.rstrip('/')
    from validacion import escritorio
    for red in (redes if redes is not None else escritorio.redes_locales()):
        with concurrent.futures.ThreadPoolExecutor(64) as hilos:
            abiertos = [ip for ip, si in zip(red.hosts(), hilos.map(lambda ip: escritorio._abierto(ip, PUERTO_SERVIDOR), red.hosts())) if si]
        for ip in abiertos:
            if es_servidor(f'http://{ip}:{PUERTO_SERVIDOR}'):
                return f'http://{ip}:{PUERTO_SERVIDOR}'
    return None


def crear_puente(servidor, puerto=PUERTO):
    """Lo que pide la ventana pasa al servidor de la escuela y su respuesta regresa igual."""

    class Puente(BaseHTTPRequestHandler):
        def _pasar(self):
            largo = int(self.headers.get('Content-Length') or 0)
            if not 0 <= largo <= MAXIMO:
                return self._responder(413, json.dumps({'error': 'El envío es demasiado grande'}).encode(), 'application/json; charset=utf-8')
            cuerpo = self.rfile.read(largo) if largo else None
            cabeceras = {k: self.headers[k] for k in PASAN if self.headers.get(k)}
            solicitud = urllib.request.Request(servidor + self.path, cuerpo, cabeceras, method=self.command)
            try:
                with urllib.request.urlopen(solicitud, timeout=360) as respuesta:
                    return self._responder(respuesta.status, respuesta.read(), headers=respuesta.headers)
            except urllib.error.HTTPError as error:
                return self._responder(error.code, error.read(), headers=error.headers)
            except OSError as error:
                mensaje = {'error': f'No contesta el servidor de la escuela ({servidor}). Revisa que esté encendido y en la misma red.',
                           'tecnico': f'{type(error).__name__}: {error}'}
                return self._responder(502, json.dumps(mensaje, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

        def _responder(self, codigo, cuerpo, tipo=None, headers=None):
            self.send_response(codigo)
            for nombre in REGRESAN:
                valor = headers.get(nombre) if headers is not None else None
                if nombre == 'Content-Type' and tipo:
                    valor = tipo
                if valor:
                    self.send_header(nombre, valor)
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        do_GET = do_POST = _pasar

        def log_message(self, formato, *args):  # Sin datos en ninguna parte.
            pass

    return ThreadingHTTPServer(('127.0.0.1', puerto), Puente)


def _perfil_en_uso(perfil):
    """Edge tiene abierto el candado de su perfil mientras alguna ventana sigue abierta: así no se puede borrar."""
    try:
        (perfil / 'lockfile').unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return False


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='SIDP-Biblioteca.exe', description='La biblioteca de la escuela, con cámara y lector.')
    parser.add_argument('--servidor', help='dirección del servidor de la escuela, por ejemplo http://192.168.1.20:8770')
    parser.add_argument('--puerto', type=int, default=PUERTO)
    args = parser.parse_args(argumentos)
    archivo = carpeta() / 'servidor.json'
    guardado = args.servidor or (json.loads(archivo.read_text(encoding='utf-8')).get('servidor') if archivo.exists() else None)
    servidor = buscar_servidor(guardado)
    if not servidor:
        print('No se encontró el servidor de la escuela. Revisa que SIDP esté abierto en el servidor y vuelve a intentar, '
              'o escribe su dirección: SIDP-Biblioteca.exe --servidor http://IP-del-servidor:8770', file=sys.stderr)
        return 2
    archivo.write_text(json.dumps({'servidor': servidor}), encoding='utf-8')
    from validacion import escritorio
    try:
        puente = crear_puente(servidor, args.puerto)
    except OSError:  # Ya está abierto: solo otra ventana.
        escritorio.abrir_ventana(f'http://127.0.0.1:{args.puerto}/#biblioteca', carpeta() / 'ventana')
        return 0
    threading.Thread(target=puente.serve_forever, daemon=True).start()
    ventana = escritorio.abrir_ventana(f'http://127.0.0.1:{args.puerto}/#biblioteca', carpeta() / 'ventana')
    if ventana is None:  # Sin Edge: el navegador de siempre; el puente sigue hasta apagar la computadora.
        threading.Event().wait()
    ventana.wait()  # Edge ya abierto con este perfil regresa enseguida: se espera a que se cierre su última ventana.
    while _perfil_en_uso(carpeta() / 'ventana'):
        time.sleep(2)
    puente.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
