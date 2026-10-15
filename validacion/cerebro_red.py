"""El cerebro de la PC 4 escuchando por IP (entorno de pruebas).

SIDP-Validador.exe, en la PC del administrador, le manda cada expediente nuevo. Aquí se
procesa completo: el lector saca el texto (PDF, QR, OCR), los procesos revisan y llama opina
en la zona gris. El resultado regresa al .exe, que es el que guarda. La PC 4 no guarda nada:
los archivos viven en una carpeta temporal que se borra al terminar cada expediente.

Ollama sigue escuchando solo en 127.0.0.1; lo único abierto a la red es este servicio, y pide
la clave que muestra al arrancar (sin ella responde 401).

En la PC 4, desde la raíz del repositorio:
    python -m validacion.cerebro_red              # puerto 8771, modelo sidp-revisor-2
Windows pregunta si permite el acceso en la red: elegir solo "redes privadas".
"""
import argparse
import base64
import datetime
import json
import secrets
import socket
import tempfile
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from validacion import expediente, lector, modelo

PUERTO = 8771
MAXIMO = 4096  # Una pregunta son dos textos cortos; nada más grande pasa.
MAXIMO_EXPEDIENTE = 80 * 1024 * 1024  # Fotos de un expediente completo, en base64.
TIPOS = ('nombre', 'domicilio')


def clave_guardada(archivo):
    """La clave se crea una vez y se guarda junto al puente, para no cambiarla en cada arranque."""
    archivo = Path(archivo)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    if archivo.exists() and archivo.read_text(encoding='utf-8').strip():
        return archivo.read_text(encoding='utf-8').strip()
    clave = secrets.token_hex(8)
    archivo.write_text(clave, encoding='utf-8')
    return clave


def ip_local():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as prueba:
        try:
            prueba.connect(('192.168.1.1', 9))  # No envía nada: solo elige la interfaz de la red local.
            return prueba.getsockname()[0]
        except OSError:
            return '127.0.0.1'


def validar(pedido, nombre_modelo=modelo.MODELO, url=modelo.URL):
    """Revisa un expediente completo en una carpeta temporal que se borra al terminar."""
    hoy = datetime.date.fromisoformat(pedido['hoy'])
    with tempfile.TemporaryDirectory(prefix='sidp-') as temporal:
        carpeta = Path(temporal) / pedido.get('id', 'expediente')
        carpeta.mkdir()
        (carpeta / 'captura.json').write_text(json.dumps(pedido['captura'], ensure_ascii=False), encoding='utf-8')
        for archivo in pedido['archivos']:
            nombre = Path(archivo['nombre']).name  # Nunca una ruta: solo el nombre.
            (carpeta / nombre).write_bytes(base64.b64decode(archivo['contenido']))
        resultado = expediente.revisar(carpeta, hoy, True, nombre_modelo, url)
    resultado['procesado_en'] = f'cerebro ({socket.gethostname()})'
    return resultado


def validar_en_cerebro(carpeta, hoy, url, clave, espera=900):
    """Lado del .exe: manda la carpeta de un expediente al cerebro y devuelve su resultado."""
    carpeta = Path(carpeta)
    archivos = [{'nombre': a.name, 'contenido': base64.b64encode(a.read_bytes()).decode()}
                for a in sorted(carpeta.iterdir()) if a.is_file() and a.suffix != '.json' and not a.name.startswith('.')]
    captura = json.loads((carpeta / 'captura.json').read_text(encoding='utf-8'))
    cuerpo = json.dumps({'id': carpeta.name, 'hoy': hoy.isoformat(), 'captura': captura, 'archivos': archivos}).encode()
    solicitud = urllib.request.Request(url.rstrip('/') + '/validar', cuerpo,
                                       {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return json.load(respuesta)


def leer(pedido):
    """Solo lectura (expedientes escaneados): el texto y los códigos de cada archivo, sin revisar nada."""
    salida = []
    with tempfile.TemporaryDirectory(prefix='sidp-') as temporal:
        for numero, archivo in enumerate(pedido['archivos']):
            nombre = Path(archivo['nombre']).name  # Nunca una ruta: solo el nombre.
            ruta = Path(temporal) / f'{numero:03d}_{nombre}'
            ruta.write_bytes(base64.b64decode(archivo['contenido']))
            lectura = lector.leer(ruta)
            salida.append({'nombre': nombre, 'texto': lectura['texto'], 'qr': lectura['qr'], 'metodo': lectura['metodo'],
                           'problemas': [p.replace(ruta.name, nombre) for p in lectura['problemas']]})
    return {'paginas': salida, 'procesado_en': f'cerebro ({socket.gethostname()})'}


def leer_en_cerebro(archivos, url, clave, espera=900):
    """Lado del .exe: archivos [(nombre, contenido)] -> lo que leyó el cerebro de cada uno."""
    cuerpo = json.dumps({'archivos': [{'nombre': n, 'contenido': base64.b64encode(c).decode()} for n, c in archivos]}).encode()
    solicitud = urllib.request.Request(url.rstrip('/') + '/leer', cuerpo, {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return json.load(respuesta)


def crear_servidor(clave, puerto=PUERTO, nombre_modelo=modelo.MODELO, url=modelo.URL, anfitrion='0.0.0.0'):
    class Puente(BaseHTTPRequestHandler):
        def _responder(self, codigo, datos):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _autorizado(self):
            if secrets.compare_digest(self.headers.get('X-SIDP-Clave', ''), clave):
                return True
            self._responder(401, {'error': 'clave incorrecta'})
            return False

        def do_GET(self):
            if self.path != '/salud':
                return self._responder(404, {'error': 'no existe'})
            if self._autorizado():
                self._responder(200, {'ok': True, 'modelo': nombre_modelo, 'herramientas': lector.herramientas()})

        def do_POST(self):
            if self.path not in ('/opinar', '/validar', '/leer'):
                return self._responder(404, {'error': 'no existe'})
            if not self._autorizado():
                return
            largo = int(self.headers.get('Content-Length') or 0)
            if self.path in ('/validar', '/leer'):
                if not 0 < largo <= MAXIMO_EXPEDIENTE:
                    return self._responder(413, {'error': 'expediente demasiado grande'})
                try:
                    pedido = json.loads(self.rfile.read(largo))
                    if self.path == '/leer':
                        return self._responder(200, leer(pedido))
                    return self._responder(200, validar(pedido, nombre_modelo, url))
                except (ValueError, KeyError, TypeError) as error:
                    return self._responder(400, {'error': f'expediente mal formado: {error}'})
            if not 0 < largo <= MAXIMO:
                return self._responder(413, {'error': 'pregunta demasiado grande'})
            try:
                pedido = json.loads(self.rfile.read(largo))
                gris = {'tipo': pedido['tipo'], 'a': str(pedido['a'])[:300], 'b': str(pedido['b'])[:300]}
                if gris['tipo'] not in TIPOS:
                    raise ValueError(gris['tipo'])
            except (ValueError, KeyError, TypeError):
                return self._responder(400, {'error': 'se espera {"tipo": "nombre" o "domicilio", "a": ..., "b": ...}'})
            self._responder(200, modelo.opinar(gris, nombre_modelo, url))

        def log_message(self, formato, *args):  # Solo quién preguntó, nunca los textos.
            print(f'{self.client_address[0]} {formato % args}', flush=True)

    return ThreadingHTTPServer((anfitrion, puerto), Puente)


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.cerebro_red')
    parser.add_argument('--puerto', type=int, default=PUERTO)
    parser.add_argument('--modelo', default=modelo.MODELO)
    parser.add_argument('--ollama', default=modelo.URL, help='Ollama local (no cambiar: sigue en 127.0.0.1)')
    # Fuera del repositorio, que es público: la clave nunca debe subirse.
    parser.add_argument('--clave', type=Path, default=Path.home() / '.sidp' / 'clave_cerebro.txt')
    args = parser.parse_args(argumentos)
    clave = clave_guardada(args.clave)
    servidor = crear_servidor(clave, args.puerto, args.modelo, args.ollama)
    print(f'Cerebro escuchando en http://{ip_local()}:{args.puerto}  (modelo {args.modelo})')
    print(f'Clave para SIDP-Validador.exe: {clave}')
    print('Cierra esta ventana para apagarlo.', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
