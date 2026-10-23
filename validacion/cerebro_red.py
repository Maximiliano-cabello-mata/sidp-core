"""El cerebro de la PC 4 escuchando por IP (entorno de pruebas).

SIDP-Validador.exe, en la PC del administrador, le manda cada expediente nuevo. Aquí se
procesa completo: el lector saca el texto (PDF, QR, OCR), los procesos revisan y llama opina
en la zona gris. El resultado regresa al .exe, que es el que guarda. La PC 4 no guarda nada:
los archivos viven en una carpeta temporal que se borra al terminar cada expediente.

Además, la PC 4 es el respaldo del servidor: en /respaldo recibe una copia de la carpeta de datos del .exe
(validacion/respaldo.py) y guarda una copia diaria de su base con pg_dump. En /inventario lleva el inventario
de la escuela y en /analisis hace el análisis de datos con pandas (validacion/analisis_datos.py).

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
import os
import secrets
import socket
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from validacion import actualizar, base_cerebro, biblioteca, campos, documentos, estandar, expediente, extraer, lector, modelo, respaldo
from validacion import taller as taller_mod, vision

PUERTO = 8771
MAXIMO = 4096  # Una pregunta son dos textos cortos; nada más grande pasa.
MAXIMO_EXPEDIENTE = 80 * 1024 * 1024  # Fotos de un expediente completo, en base64.
MAXIMO_PADRON = 4 * 1024 * 1024  # Toda la escuela: unos cientos de alumnos.
MAXIMO_RESPALDO = 90 * 1024 * 1024  # Un archivo de respaldo (hasta 60 MB) en base64.
MAXIMO_INVENTARIO = 256 * 1024
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
    return pedir_a_cerebro(url, clave, '/padron', {'ciclo': ciclo, 'alumnos': alumnos}, espera)


def bajar_de_cerebro(url, clave, ruta, espera=600):
    """Lado del .exe: un archivo (bytes) del cerebro, por ejemplo la versión nueva de SIDP.exe."""
    solicitud = urllib.request.Request(url.rstrip('/') + ruta, headers={'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return respuesta.read()


def pedir_a_cerebro(url, clave, ruta, datos=None, espera=120):
    """Lado del .exe: GET (sin datos) o POST con JSON a una ruta del cerebro. Un error del cerebro sube con su mensaje."""
    cuerpo = None if datos is None else json.dumps(datos, ensure_ascii=False).encode()
    solicitud = urllib.request.Request(url.rstrip('/') + ruta, cuerpo, {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
    try:
        with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as error:
        try:
            mensaje = json.load(error).get('error')
        except Exception:
            mensaje = None
        raise ErrorCerebro(mensaje or f'el cerebro respondió {error.code}', error.code) from None


class ErrorCerebro(Exception):
    def __init__(self, mensaje, codigo=None):
        super().__init__(mensaje)
        self.code = codigo


def alumnos_de_cerebro(url, clave, espera=60):
    """Lado del .exe: los alumnos inscritos en la base de la PC 4, por grupo. Un error sube con lo que dijo la PC 4."""
    return pedir_a_cerebro(url, clave, '/alumnos', espera=espera)


def senas(vistas):
    """Las señas que propuso la IA para una plantilla, solo las que pueden ser texto impreso fijo (sin números ni CURP)."""
    salida, vistas_ya = [], set()
    for sena in vistas or []:
        sena = ' '.join(str(sena).split()).strip(' .:,;')
        clave = extraer.mayusculas(sena)
        if 4 <= len(sena) <= 60 and not any(c.isdigit() for c in sena) and clave not in vistas_ya:
            salida.append(sena)
            vistas_ya.add(clave)
    return salida[:6]


def crear_servidor(clave, puerto=PUERTO, nombre_modelo=modelo.MODELO, url=modelo.URL, anfitrion='0.0.0.0', base=None, taller=None,
                   almacen=None, carpeta_respaldos=None, actualizaciones=None, estudio=None):
    almacen = almacen or respaldo.Almacen()
    actualizaciones = Path(actualizaciones or actualizar.carpeta_pc4())
    carpeta_respaldos = Path(carpeta_respaldos or base_cerebro.CARPETA_RESPALDOS)

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
            ruta, _, consulta = self.path.partition('?')
            if ruta not in ('/salud', '/alumnos', '/inventario', '/analisis', '/respaldo', '/trabajos', '/alumno', '/por_confirmar',
                            '/actualizacion', '/actualizacion/programa', '/documentos', '/registros') and not ruta.startswith('/biblioteca'):
                return self._responder(404, {'error': 'no existe'})
            if not self._autorizado():
                return
            if ruta.startswith('/actualizacion'):  # La versión de SIDP.exe que guarda la PC 4 (validacion/actualizar.py).
                ofrece = actualizar.disponible(actualizaciones)
                if ruta == '/actualizacion':
                    return self._responder(200, ofrece or {'version': None})
                if not ofrece:
                    return self._responder(404, {'error': 'la PC 4 no tiene ninguna versión guardada'})
                archivo = actualizaciones / ofrece['archivo']
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(archivo.stat().st_size))
                self.end_headers()
                with open(archivo, 'rb') as entrada:
                    while trozo := entrada.read(1024 * 1024):
                        self.wfile.write(trozo)
                return
            if ruta == '/salud':
                try:
                    datos_base = base.resumen() if base else None
                except Exception as error:
                    datos_base = {'error': f'{type(error).__name__}: {error}'}
                return self._responder(200, {'ok': True, 'modelo': nombre_modelo, 'herramientas': lector.herramientas(), 'base': datos_base})
            if ruta == '/respaldo':
                return self._responder(200, almacen.estado())
            if not base:
                return self._responder(503, {'error': 'el cerebro no tiene base de datos (PostgreSQL)'})
            try:
                if ruta == '/alumnos':
                    return self._responder(200, base.alumnos())
                if ruta == '/inventario':
                    return self._responder(200, base.inventario())
                if ruta == '/trabajos':
                    return self._responder(200, taller.estado() if taller else {'trabajos': {}, 'sin_taller': True})
                if ruta == '/por_confirmar':
                    return self._responder(200, {'datos': base.por_confirmar()})
                if ruta in ('/documentos', '/registros'):  # El motor de documentos (validacion/documentos.py).
                    from urllib.parse import parse_qs
                    ciclo, registros = estandar.registros(base)
                    if ruta == '/documentos':
                        return self._responder(200, {'ciclo': ciclo, 'alumnos': len(registros), 'documentos': documentos.catalogo(),
                                                     'faltan': estandar.faltan(registros)})
                    pedido = parse_qs(consulta)
                    grado, letra = pedido.get('grado', [''])[0], pedido.get('letra', [''])[0]
                    elegidos = [r for r in registros if (not grado or str(r['grado']) == grado) and (not letra or r['letra'] == letra)]
                    return self._responder(200, {'ciclo': ciclo, 'columnas': estandar.columnas_911(),
                                                 'alumnos': [{k: r.get(k) for k in estandar.PARA_COMPLETAR} for r in elegidos]})
                if ruta.startswith('/biblioteca'):
                    from urllib.parse import parse_qs
                    return self._responder(200, biblioteca.consultar(base, ruta, parse_qs(consulta)))
                if ruta == '/alumno':
                    from urllib.parse import parse_qs
                    try:
                        return self._responder(200, base.expediente_alumno(parse_qs(consulta).get('curp', [''])[0]))
                    except base_cerebro.ErrorBase as error:
                        return self._responder(404, {'error': str(error)})
                from validacion import analisis_datos
                try:
                    resultado = analisis_datos.analizar(base)
                except ImportError:
                    return self._responder(503, {'error': 'falta pandas en la PC 4 (python -m pip install pandas)'})
                if 'ia=1' in consulta.split('&'):  # Estudio nuevo ahora mismo (si contesta, queda guardado como el último).
                    resultado['ia'] = estudio.hacer(resultado) if estudio else analisis_datos.redactar(resultado, url)
                resultado['estudio'] = estudio.guardado() if estudio else None
                return self._responder(200, resultado)
            except biblioteca.ErrorBiblioteca as error:
                return self._responder(400, {'error': str(error)})
            except Exception as error:
                return self._fallo_base(error)

        def _fallo_base(self, error):
            traceback.print_exc()  # Queda en cerebro.error.log de la PC 4.
            detalle = ' '.join(str(error).split())[:160]
            return self._responder(500, {'error': f'la base de datos falló: {type(error).__name__}' + (f' ({detalle})' if detalle else '')})

        def _leer_json(self, maximo):
            largo = int(self.headers.get('Content-Length') or 0)
            if not 0 < largo <= maximo:
                self._responder(413, {'error': 'pedido demasiado grande o vacío'})
                return None
            try:
                return json.loads(self.rfile.read(largo))
            except ValueError:
                self._responder(400, {'error': 'no es JSON'})
                return None

        def _respaldo(self, ruta):
            pedido = self._leer_json(MAXIMO_RESPALDO)
            if pedido is None:
                return
            try:
                if ruta == '/respaldo/faltan':
                    return self._responder(200, {'faltan': almacen.faltan(pedido['archivos'])})
                if ruta == '/respaldo/archivo':
                    contenido = base64.b64decode(pedido['contenido'], validate=True)
                    return self._responder(200, {'estado': almacen.guardar(pedido['ruta'], contenido, pedido['sha256'])})
            except (ValueError, KeyError, TypeError) as error:
                return self._responder(400, {'error': f'respaldo mal formado: {error}'})
            copia_base = None
            if base and not list(carpeta_respaldos.glob(f'sidp_cerebro_{datetime.date.today():%Y%m%d}_*.dump')):
                try:  # Una copia de la base de la PC 4 por día, junto con la del .exe.
                    copia_base = base.respaldar(carpeta_respaldos)
                except Exception as error:
                    copia_base = {'error': str(error)[:200]}
            almacen.anotar({'archivos': pedido.get('archivos'), 'enviados': pedido.get('enviados'), 'copia_base': copia_base})
            return self._responder(200, {'ok': True, **almacen.estado(), 'copia_base': copia_base})

        def _inventario(self, ruta):
            if not base:
                return self._responder(503, {'error': 'el cerebro no tiene base de datos (PostgreSQL)'})
            pedido = self._leer_json(MAXIMO_INVENTARIO)
            if pedido is None:
                return
            try:
                if ruta == '/inventario/alta':
                    hecho = base.inventario_alta(pedido.get('categoria'), pedido.get('nombre'), pedido.get('caracteristicas'),
                                                 pedido.get('cantidad'), pedido.get('ubicacion'), pedido.get('series'), pedido.get('actor'))
                else:
                    hecho = base.inventario_cambiar(pedido.get('codigo'), pedido.get('estado'), pedido.get('ubicacion'),
                                                    pedido.get('notas'), pedido.get('actor'))
            except base_cerebro.ErrorBase as error:
                return self._responder(400, {'error': str(error)})
            except Exception as error:  # Las reglas de la base (pieza que no existe, baja sin motivo) llegan aquí.
                mensaje = getattr(error, 'args', [None])[0]
                detalle = mensaje.get('M') if isinstance(mensaje, dict) else str(error)
                return self._responder(400, {'error': detalle[:300]})
            return self._responder(200, {'ok': True, 'hecho': hecho, **base.inventario()})

        def _vision(self, ruta):
            """El modelo que ve, sin base de datos: los campos y señas de una plantilla, o qué documento parece una hoja."""
            pedido = self._leer_json(MAXIMO_EXPEDIENTE)
            if pedido is None:
                return
            try:
                if ruta == '/plantilla/campos':
                    hojas = vision.paginas(base64.b64decode(pedido['contenido']), pedido.get('nombre', ''))[:2]
                    vistos, segundos = vision.preguntar(hojas, campos.PROPONER, campos.ESQUEMA_PROPONER, url=url)
                    etiquetas = [e for e in dict.fromkeys(str(x).strip() for x in vistos.get('campos', [])) if e][:40]
                    return self._responder(200, {'campos': [campos.proponer(e) for e in etiquetas], 'senas': senas(vistos.get('senas')),
                                                 'titulo': str(vistos.get('titulo') or '').strip()[:80], 'segundos': segundos})
                tipos = [{'clave': str(t['clave'])[:40], 'nombre': str(t.get('nombre') or t['clave'])[:80],
                          'senas': [str(s)[:60] for s in (t.get('senas') or [])][:5]} for t in pedido['tipos'][:40]]
                if not tipos:
                    raise ValueError('faltan los tipos')
                hojas = vision.paginas(base64.b64decode(pedido['contenido']), pedido.get('nombre', ''))[:1]
                visto, segundos = vision.preguntar(hojas, campos.clasificar(tipos), campos.esquema_clasificar(tipos), url=url, espera=300)
                tipo = visto.get('tipo') if visto.get('tipo') in {t['clave'] for t in tipos} else 'otro'
                return self._responder(200, {'tipo': tipo, 'titulo': str(visto.get('titulo') or '').strip()[:80],
                                             'motivo': str(visto.get('motivo') or '').strip()[:160], 'segundos': segundos})
            except vision.ErrorVision as error:
                return self._responder(503, {'error': str(error)})
            except (ValueError, KeyError, TypeError) as error:
                return self._responder(400, {'error': f'pedido mal formado: {error}'})

        def _expediente(self, ruta):
            """Trabajos de extracción, datos del alumno y su baja: todo en la base de la PC 4."""
            if not base:
                return self._responder(503, {'error': 'el cerebro no tiene base de datos (PostgreSQL)'})
            pedido = self._leer_json(MAXIMO_EXPEDIENTE if ruta == '/trabajo' else MAXIMO_INVENTARIO)
            if pedido is None:
                return
            try:
                if ruta == '/trabajo':
                    if not taller:
                        return self._responder(503, {'error': 'el taller de la PC 4 no está trabajando'})
                    return self._responder(200, {'trabajo': taller.encargar(pedido)})
                persona = pedido.get('persona') or 'administrador'
                if ruta == '/dato/confirmar':
                    hecho = base.confirmar_dato(pedido['id'], pedido.get('valor'), persona, pedido.get('descartar'))
                elif ruta == '/dato/agregar':
                    hecho = base.agregar_dato(pedido['curp'], pedido['categoria'], pedido['campo'], pedido['valor'], persona,
                                              {'de': pedido['de']} if pedido.get('de') else None)
                elif ruta == '/dato/varios':  # «Completar datos del 911»: lo que la escuela anota de un grupo, de una vez.
                    hecho = base.agregar_varios(pedido['datos'], persona)
                elif ruta == '/alumno/baja':
                    hecho = base.dar_baja_alumno(pedido['curp'], pedido.get('motivo'), persona)
                else:
                    hecho = base.borrar_alumno(pedido['curp'], pedido.get('motivo'), persona)
                return self._responder(200, {'ok': True, 'hecho': hecho})
            except vision.ErrorVision as error:
                return self._responder(503, {'error': str(error)})
            except (LookupError, base_cerebro.ErrorBase) as error:
                return self._responder(409, {'error': str(error)})
            except (ValueError, KeyError, TypeError) as error:
                return self._responder(400, {'error': f'pedido mal formado: {error}'})
            except Exception as error:  # Las reglas de la base (motivo vacío, dato que no existe) llegan aquí.
                mensaje = getattr(error, 'args', [None])[0]
                detalle = mensaje.get('M') if isinstance(mensaje, dict) else str(error)
                return self._responder(400, {'error': detalle[:300]})

        def _documento(self):
            """Un documento oficial armado aquí con la base de todos los alumnos; los datos de la escuela llegan con el pedido."""
            if not base:
                return self._responder(503, {'error': 'el cerebro no tiene base de datos (PostgreSQL)'})
            pedido = self._leer_json(MAXIMO_INVENTARIO)
            if pedido is None:
                return
            try:
                ciclo, registros = estandar.registros(base)
                nombre, contenido, tipo = documentos.generar(pedido['clave'], pedido['formato'], registros, pedido.get('escuela'), ciclo or '',
                                                             grado=pedido.get('grado'), letra=pedido.get('letra'), curp=pedido.get('curp'))
            except documentos.ErrorDocumento as error:
                return self._responder(400, {'error': str(error)})
            except (ValueError, KeyError, TypeError) as error:
                return self._responder(400, {'error': f'pedido mal formado: {error}'})
            except Exception as error:
                return self._fallo_base(error)
            return self._responder(200, {'nombre': nombre, 'tipo': tipo, 'contenido': base64.b64encode(contenido).decode()})

        def _biblioteca(self, ruta):
            if not base:
                return self._responder(503, {'error': 'el cerebro no tiene base de datos (PostgreSQL)'})
            pedido = self._leer_json(MAXIMO_EXPEDIENTE if ruta == '/biblioteca/identificar' else MAXIMO_INVENTARIO)
            if pedido is None:
                return
            try:
                return self._responder(200, biblioteca.hacer(base, ruta, pedido, url))
            except biblioteca.ErrorBiblioteca as error:
                return self._responder(400, {'error': str(error)})
            except (ValueError, KeyError, TypeError) as error:
                return self._responder(400, {'error': f'pedido mal formado: {error}'})
            except Exception as error:
                mensaje = getattr(error, 'args', [None])[0]
                if isinstance(mensaje, dict):  # Una regla de la base (código que no existe, libro ya prestado).
                    return self._responder(400, {'error': str(mensaje.get('M'))[:300]})
                return self._fallo_base(error)

        def do_POST(self):
            if self.path not in ('/opinar', '/validar', '/leer', '/padron', '/inventario/alta', '/inventario/cambiar',
                                 '/respaldo/faltan', '/respaldo/archivo', '/respaldo/listo', '/trabajo', '/plantilla/campos',
                                 '/clasificar', '/dato/confirmar', '/dato/agregar', '/dato/varios', '/alumno/baja', '/alumno/borrar',
                                 '/documento') and self.path not in biblioteca.RUTAS_POST:
                return self._responder(404, {'error': 'no existe'})
            if not self._autorizado():
                return
            if self.path == '/documento':
                return self._documento()
            if self.path in biblioteca.RUTAS_POST:
                return self._biblioteca(self.path)
            if self.path in ('/plantilla/campos', '/clasificar'):
                return self._vision(self.path)
            if self.path in ('/trabajo', '/dato/confirmar', '/dato/agregar', '/dato/varios', '/alumno/baja', '/alumno/borrar'):
                return self._expediente(self.path)
            if self.path.startswith('/respaldo/'):
                return self._respaldo(self.path)
            if self.path.startswith('/inventario/'):
                return self._inventario(self.path)
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
                    return self._fallo_base(error)
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
    # Arranque sin monitor (cerebro/pc4/instalar_servicios.ps1): PostgreSQL puede tardar en levantarse y la
    # clave no se escribe en el registro, que se queda en el disco.
    parser.add_argument('--esperar-base', type=int, default=0, help='segundos que espera a PostgreSQL al arrancar')
    parser.add_argument('--sin-mostrar-clave', action='store_true')
    # Como servicio: sin base no arranca (sale con 3) y su lanzador lo vuelve a intentar; así nunca se queda
    # contestando sin base hasta que alguien lo reinicie a mano.
    parser.add_argument('--exigir-base', action='store_true', help='si PostgreSQL no contesta, salir en vez de seguir sin base')
    parser.add_argument('--actualizaciones', type=Path, default=actualizar.carpeta_pc4(),
                        help='dónde guarda la PC 4 las versiones de SIDP.exe que toma el servidor')
    # Si el servidor también es el cerebro (Tarea 019), SIDP_CEREBRO_ANFITRION=127.0.0.1: nadie de la red llega al 8771.
    parser.add_argument('--anfitrion', default=os.environ.get('SIDP_CEREBRO_ANFITRION') or '0.0.0.0',
                        help='0.0.0.0 = toda la red (PC 4 aparte); 127.0.0.1 = solo esta PC')
    args = parser.parse_args(argumentos)
    clave = clave_guardada(args.clave)
    base, problema = base_cerebro.abrir(args.base)
    limite = time.monotonic() + args.esperar_base
    while base is None and time.monotonic() < limite:
        time.sleep(5)
        base, problema = base_cerebro.abrir(args.base)
    if base is None and args.exigir_base:
        print(f'Sin base de datos ({problema}): salgo para que el lanzador lo vuelva a intentar.', flush=True)
        return 3
    taller = taller_mod.arrancar(base, url=args.ollama) if base else None  # Saca los datos de lo escaneado, en fila.
    estudio = None
    if base:  # El estudio de la IA se rehace solo cuando hay datos nuevos y el taller no está leyendo.
        from validacion import analisis_datos
        estudio = analisis_datos.Estudio(base, args.ollama, ocupado=lambda: bool(taller and (taller.ahora or base._uno(
            "SELECT count(*) FROM sidp.trabajo WHERE estado = 'pendiente'"))))
        threading.Thread(target=estudio.vigilar, daemon=True).start()
    servidor = crear_servidor(clave, args.puerto, args.modelo, args.ollama, anfitrion=args.anfitrion, base=base, taller=taller,
                              actualizaciones=args.actualizaciones, estudio=estudio)
    if os.environ.get('SIDP_ACTUALIZAR_GITHUB', '1') != '0':  # Cada hora baja de GitHub la versión nueva de SIDP.exe.
        threading.Thread(target=actualizar.vigilar_github, args=(args.actualizaciones,), daemon=True).start()
    print(f'Cerebro escuchando en http://{ip_local() if args.anfitrion == "0.0.0.0" else args.anfitrion}:{args.puerto}  (modelo {args.modelo})')
    if base:
        resumen = base.resumen()
        print(f'Base de datos: {resumen["motor"]} con {resumen["alumnos"]} alumnos inscritos.')
    else:
        print(f'Sin base de datos ({problema}): funciona igual, sin comparar contra el padrón.')
    if args.sin_mostrar_clave:
        print(f'Clave para SIDP-Validador.exe: guardada en {args.clave}', flush=True)
    else:
        print(f'Clave para SIDP-Validador.exe: {clave}')
        print('Cierra esta ventana para apagarlo.', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
