"""El cerebro de la PC 4 escuchando por IP (entorno de pruebas).

SIDP-Validador.exe, en la PC del administrador, le manda cada expediente nuevo. Aquí se
procesa completo: el lector saca el texto (PDF, QR, OCR), los procesos revisan y llama opina
en la zona gris. El resultado regresa al .exe, que es el que guarda. La PC 4 no guarda nada:
los archivos viven en una carpeta temporal que se borra al terminar cada expediente.

Ollama sigue escuchando solo en 127.0.0.1; lo único abierto a la red es este servicio, y pide
la clave que muestra al arrancar (sin ella responde 401).

La base de datos del cerebro (PostgreSQL, también solo en 127.0.0.1) guarda el padrón de alumnos que
manda el .exe en /padron; con él, /leer propone al alumno correcto aunque la CURP o el nombre se hayan
leído con errores. Sin PostgreSQL todo funciona igual, sin esas propuestas (ver validacion/base_cerebro.py).

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

from validacion import base_cerebro, expediente, lector, modelo

PUERTO = 8771
MAXIMO = 4096  # Una pregunta son dos textos cortos; nada más grande pasa.
MAXIMO_EXPEDIENTE = 80 * 1024 * 1024  # Fotos de un expediente completo, en base64.
MAXIMO_PADRON = 4 * 1024 * 1024  # Toda la escuela: unos cientos de alumnos.
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
        resultado = expediente.revisar(carpeta, hoy, True, nombre_modelo, url, plantillas=pedido.get('plantillas'))
    resultado['procesado_en'] = f'cerebro ({socket.gethostname()})'
    return resultado


def validar_en_cerebro(carpeta, hoy, url, clave, espera=900, plantillas=None):
    """Lado del .exe: manda la carpeta de un expediente al cerebro y devuelve su resultado."""
    carpeta = Path(carpeta)
    archivos = [{'nombre': a.name, 'contenido': base64.b64encode(a.read_bytes()).decode()}
                for a in sorted(carpeta.iterdir()) if a.is_file() and a.suffix != '.json' and not a.name.startswith('.')]
    captura = json.loads((carpeta / 'captura.json').read_text(encoding='utf-8'))
    cuerpo = json.dumps({'id': carpeta.name, 'hoy': hoy.isoformat(), 'captura': captura, 'archivos': archivos,
                         'plantillas': plantillas}).encode()
    solicitud = urllib.request.Request(url.rstrip('/') + '/validar', cuerpo,
                                       {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return json.load(respuesta)


def leer(pedido, base=None):
    """Solo lectura (expedientes escaneados): el texto y los códigos de cada archivo, sin revisar nada.

    Con la base de datos, cada página trae además las sugerencias del padrón (alumnos cuya CURP o nombre
    se parecen a lo leído).
    """
    salida = []
    with tempfile.TemporaryDirectory(prefix='sidp-') as temporal:
        for numero, archivo in enumerate(pedido['archivos']):
            nombre = Path(archivo['nombre']).name  # Nunca una ruta: solo el nombre.
            ruta = Path(temporal) / f'{numero:03d}_{nombre}'
            ruta.write_bytes(base64.b64decode(archivo['contenido']))
            lectura = lector.leer(ruta)
            pagina = {'nombre': nombre, 'texto': lectura['texto'], 'qr': lectura['qr'], 'metodo': lectura['metodo'],
                      'problemas': [p.replace(ruta.name, nombre) for p in lectura['problemas']]}
            if base:
                try:
                    pagina['sugerencias'] = base.sugerir(pagina['texto'] + '\n' + '\n'.join(pagina['qr']))
                    base.anotar(pagina['metodo'], pagina['texto'], pagina['sugerencias'])
                except Exception as error:  # La base nunca detiene la lectura.
                    print(f'base de datos: {type(error).__name__}: {error}', flush=True)
            salida.append(pagina)
    return {'paginas': salida, 'procesado_en': f'cerebro ({socket.gethostname()})'}


def leer_en_cerebro(archivos, url, clave, espera=900):
    """Lado del .exe: archivos [(nombre, contenido)] -> lo que leyó el cerebro de cada uno."""
    cuerpo = json.dumps({'archivos': [{'nombre': n, 'contenido': base64.b64encode(c).decode()} for n, c in archivos]}).encode()
    solicitud = urllib.request.Request(url.rstrip('/') + '/leer', cuerpo, {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return json.load(respuesta)


def padron_a_cerebro(ciclo, alumnos, url, clave, espera=60):
    """Lado del .exe: manda el padrón (los alumnos de las listas) a la base del cerebro."""
    cuerpo = json.dumps({'ciclo': ciclo, 'alumnos': alumnos}, ensure_ascii=False).encode()
    solicitud = urllib.request.Request(url.rstrip('/') + '/padron', cuerpo, {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return json.load(respuesta)


def crear_servidor(clave, puerto=PUERTO, nombre_modelo=modelo.MODELO, url=modelo.URL, anfitrion='0.0.0.0', base=None):
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
                try:
                    datos_base = base.resumen() if base else None
                except Exception as error:
                    datos_base = {'error': f'{type(error).__name__}: {error}'}
                self._responder(200, {'ok': True, 'modelo': nombre_modelo, 'herramientas': lector.herramientas(), 'base': datos_base})

        def do_POST(self):
            if self.path not in ('/opinar', '/validar', '/leer', '/padron'):
                return self._responder(404, {'error': 'no existe'})
            if not self._autorizado():
                return
            largo = int(self.headers.get('Content-Length') or 0)
            if self.path == '/padron':
                if not base:
                    return self._responder(503, {'error': 'el cerebro no tiene base de datos (PostgreSQL)'})
                if not 0 < largo <= MAXIMO_PADRON:
                    return self._responder(413, {'error': 'padrón demasiado grande'})
                try:
                    pedido = json.loads(self.rfile.read(largo))
                    cargados = base.cargar(str(pedido['ciclo']), list(pedido['alumnos']))
                except (ValueError, KeyError, TypeError) as error:
                    return self._responder(400, {'error': f'padrón mal formado: {error}'})
                except Exception as error:
                    return self._responder(500, {'error': f'la base de datos falló: {type(error).__name__}'})
                return self._responder(200, {'ok': True, 'cargados': cargados, **base.resumen()})
            if self.path in ('/validar', '/leer'):
                if not 0 < largo <= MAXIMO_EXPEDIENTE:
                    return self._responder(413, {'error': 'expediente demasiado grande'})
                try:
                    pedido = json.loads(self.rfile.read(largo))
                    if self.path == '/leer':
                        return self._responder(200, leer(pedido, base))
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
    parser.add_argument('--base', type=Path, default=base_cerebro.ARCHIVO, help='archivo con la dirección de PostgreSQL')
    args = parser.parse_args(argumentos)
    clave = clave_guardada(args.clave)
    base, problema = base_cerebro.abrir(args.base)
    servidor = crear_servidor(clave, args.puerto, args.modelo, args.ollama, base=base)
    print(f'Cerebro escuchando en http://{ip_local()}:{args.puerto}  (modelo {args.modelo})')
    if base:
        resumen = base.resumen()
        print(f'Base de datos: {resumen["motor"]} con {resumen["alumnos"]} alumnos en el padrón.')
    else:
        print(f'Sin base de datos ({problema}): funciona igual, sin comparar contra el padrón.')
    print(f'Clave para SIDP-Validador.exe: {clave}')
    print('Cierra esta ventana para apagarlo.', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
