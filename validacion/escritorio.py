"""SIDP instalado en el servidor: doble clic y se abre en su propia ventana, sin configurar nada.

- Los datos viven en C:\\SIDP (o en SIDP_CARPETA):
    C:\\SIDP\\Expedientes\\<grado y grupo>\\<alumno>\\<documento>.pdf   lo que la escuela abre y consulta
    C:\\SIDP\\sistema\\                                                bases, configuración y registros del programa
  La primera vez, si hay datos del entorno de pruebas (~/SIDP-prueba), se copian a sistema\\ (el original no se toca).
- La plataforma trabaja en segundo plano desde que se inicia sesión (el instalador la pone en el inicio). El doble
  clic solo abre la ventana; cerrar la ventana no apaga el servidor.
- La ventana es Microsoft Edge en modo aplicación (viene con Windows): sin barra de direcciones ni pestañas.
- Busca sola a la PC 4: primero en la dirección guardada y, si cambió (la red le dio otra IP), en toda la red
  local. La clave del cerebro se escribe una sola vez. Si la PC 4 no aparece, todo sigue funcionando en esta PC y
  se reintenta cada minuto (ver docs/guias/PLAN_DE_EMERGENCIA.md).
- Se actualiza solo desde la PC 4, sin depender del repositorio (validacion/actualizar.py): cada hora pregunta si
  hay versión nueva y la pone cuando nadie la está usando.

    SIDP.exe                    abre la ventana (y arranca el servidor si no estaba)
    SIDP.exe --segundo-plano    solo el servidor (así arranca con Windows)
    SIDP.exe --apagar           apaga el servidor
"""
import argparse
import concurrent.futures
import ipaddress
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from validacion import actualizar, archivero

PUERTO_CEREBRO = 8771
CADA = 60  # Segundos entre revisiones de la conexión con la PC 4.


def raiz():
    if os.environ.get('SIDP_CARPETA'):
        return Path(os.environ['SIDP_CARPETA'])
    return Path('C:/SIDP') if os.name == 'nt' else Path.home() / 'SIDP'


def carpetas(base=None):
    """(sistema, expedientes). La primera vez copia los datos del entorno de pruebas, si los hay."""
    elegida = base or os.environ.get('SIDP_CARPETA')
    base = Path(elegida or raiz())
    sistema, expedientes = base / 'sistema', base / 'Expedientes'
    prueba = Path.home() / 'SIDP-prueba'
    if not elegida and not (sistema / 'plataforma_prueba.db').exists() and (prueba / 'plataforma_prueba.db').exists():
        shutil.copytree(prueba, sistema, dirs_exist_ok=True)
    for carpeta in (sistema, expedientes, sistema / 'registros'):
        carpeta.mkdir(parents=True, exist_ok=True)
    return sistema, expedientes


# --- Encontrar a la PC 4 -------------------------------------------------------------------------------------

def version():
    """La versión de este SIDP (la pone CI al compilar; en el código fuente es 0.0.0)."""
    from validacion.aplicacion import RAIZ
    archivo = RAIZ / 'version.txt'
    return archivo.read_text(encoding='utf-8').strip() if archivo.exists() else '0.0.0'


def es_cerebro(url, espera=1.5):
    """True si en esa dirección contesta un cerebro de SIDP (pide clave: responde 401 'clave incorrecta')."""
    try:
        urllib.request.urlopen(url.rstrip('/') + '/salud', timeout=espera).close()
    except urllib.error.HTTPError as error:
        try:
            return error.code == 401 and 'clave' in json.load(error).get('error', '')
        except Exception:
            return False
    except Exception:
        return False
    return False


def redes_locales():
    """Las redes /24 de esta PC, primero la que sale a la red; sin las de VirtualBox ni las automáticas (169.254)."""
    from validacion.cerebro_red import ip_local
    direcciones = [ip_local()]
    try:
        direcciones += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    redes = []
    for direccion in direcciones:
        if direccion.startswith(('127.', '169.254.', '192.168.56.')):
            continue
        red = ipaddress.ip_network(f'{direccion}/24', strict=False)
        if red not in redes:
            redes.append(red)
    return redes


def _abierto(ip, puerto, espera=0.4):
    try:
        with socket.create_connection((str(ip), puerto), timeout=espera):
            return True
    except OSError:
        return False


def buscar_cerebro(guardada=None, puerto=PUERTO_CEREBRO, redes=None):
    """Las direcciones donde contesta un cerebro: la guardada si sigue sirviendo; si no, se recorre la red local."""
    if guardada and es_cerebro(guardada):
        return [guardada.rstrip('/')]
    encontrados = []
    for red in (redes if redes is not None else redes_locales()):
        with concurrent.futures.ThreadPoolExecutor(64) as hilos:
            abiertos = [ip for ip, si in zip(red.hosts(), hilos.map(lambda ip: _abierto(ip, puerto), red.hosts())) if si]
        encontrados += [f'http://{ip}:{puerto}' for ip in abiertos if es_cerebro(f'http://{ip}:{puerto}')]
    return encontrados


def diagnostico(url):
    """En palabras, qué pasa con esa dirección: sirve para el plan de emergencia."""
    if not url:
        return 'No hay dirección guardada de la PC 4.'
    try:
        anfitrion = url.split('//')[-1].split(':')[0]
        puerto = int(url.rsplit(':', 1)[-1].strip('/'))
    except ValueError:
        return 'La dirección no tiene la forma http://IP:8771.'
    if not _abierto(anfitrion, puerto, 3):
        return (f'Nadie contesta en {anfitrion}:{puerto}. Revisa que la PC 4 esté encendida y en la misma red que esta PC; '
                'si la red le cambió la IP, usa "Buscar la PC 4".')
    if not es_cerebro(url, 5):
        return f'En {anfitrion}:{puerto} contesta otro programa, no el cerebro de SIDP.'
    return 'La PC 4 contesta: si no conecta, revisa la clave.'


class Vigia:
    """Cuida la conexión con la PC 4: reconecta solo y, si cambió de IP, la vuelve a encontrar."""

    def __init__(self, app, cada=CADA, redes=None, puerto=PUERTO_CEREBRO):
        self.app = app
        self.cada = cada
        self.redes, self.puerto = redes, puerto
        self.estado = {'conectado': bool(app.bandeja.cerebro), 'buscando': False, 'problema': None, 'revisado': None}

    def revisar(self):
        config = self.app.configuracion
        url, clave = config.get('cerebro_url'), config.get('cerebro_clave', '')
        if not clave:
            self.estado.update(conectado=False, problema='Falta escribir la clave del cerebro (Ajustes).')
            return self.estado
        from validacion import modelo
        problema = modelo.salud_remota(url, clave) if url else 'sin dirección'
        if problema:
            self.estado['buscando'] = True
            encontrados = buscar_cerebro(url, self.puerto, self.redes)
            self.estado['buscando'] = False
            nueva = next((u for u in encontrados if not modelo.salud_remota(u, clave)), None)
            if nueva:
                problema = self.app.configurar(nueva, clave)
            else:
                self.app.bandeja.cerebro = None
                problema = diagnostico(url) if not encontrados else 'La PC 4 contesta, pero la clave no coincide.'
        elif not self.app.bandeja.cerebro:
            problema = self.app.configurar(url, clave)
        if not problema and list(self.app.bandeja._pendientes().glob('*.json')):
            with self.app.candado:  # Lo que se escaneó mientras la PC 4 no estaba.
                self.app.bandeja.enviar_pendientes()
        self.estado.update(conectado=not problema, problema=problema, revisado=time.strftime('%H:%M'), url=self.app.configuracion.get('cerebro_url'))
        if not problema and self.app.actualizador:
            self.actualizar(self.app.configuracion.get('cerebro_url'), clave)
        return self.estado

    def actualizar(self, url, clave):
        """Versión nueva en la PC 4: se baja y, cuando nadie ha cambiado nada en un rato, se pone y SIDP se reinicia."""
        actualizador = self.app.actualizador
        try:
            actualizador.revisar(url, clave)
        except Exception as error:
            actualizador.estado['problema'] = f'{type(error).__name__}: {error}'
            return
        if not actualizador.estado['lista'] or not actualizador.quieto_ahora():
            return

        def apagar():
            with self.app.candado:  # Que no quede nada a medio guardar.
                self.app.servidor.shutdown()
                self.app.servidor.server_close()

        self.app.actualizando = True
        try:
            resultado = actualizador.aplicar(apagar)
        finally:
            self.app.actualizando = False
        if resultado:
            os._exit(0)  # Ya contesta la versión nueva (o se regresó a la anterior y ya arrancó): este proceso sobra.

    def trabajar(self):
        while True:
            try:
                self.revisar()
            except Exception as error:
                self.estado.update(conectado=False, problema=f'{type(error).__name__}: {error}')
            time.sleep(self.cada)


# --- La ventana ----------------------------------------------------------------------------------------------

def edge():
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')):
        if base and (Path(base) / 'Microsoft/Edge/Application/msedge.exe').exists():
            return Path(base) / 'Microsoft/Edge/Application/msedge.exe'
    return shutil.which('msedge')


def abrir_ventana(url, perfil):
    """Una ventana propia (Edge en modo aplicación) y su proceso; si no hay Edge, el navegador de siempre y None."""
    programa = edge()
    if programa:
        return subprocess.Popen([str(programa), f'--app={url}', f'--user-data-dir={perfil}', '--no-first-run',
                                 '--disable-features=Translate', '--window-size=1440,900'])
    webbrowser.open(url)
    return None


def ya_abierto(puerto):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{puerto}/api/hola', timeout=2) as respuesta:
            return json.load(respuesta).get('sidp') == 'servidor'
    except Exception:
        return False


def apagar(sistema, puerto):
    archivo = sistema / 'apagar.clave'
    if not archivo.exists():
        return False
    solicitud = urllib.request.Request(f'http://127.0.0.1:{puerto}/api/apagar', b'{}',
                                       {'Content-Type': 'application/json', 'X-SIDP-Apagar': archivo.read_text().strip()})
    try:
        urllib.request.urlopen(solicitud, timeout=5).close()
        return True
    except Exception:
        return False


def main(argumentos=None):
    from validacion import aplicacion
    parser = argparse.ArgumentParser(prog='SIDP')
    parser.add_argument('--segundo-plano', action='store_true', help='solo el servidor, sin abrir la ventana')
    parser.add_argument('--apagar', action='store_true')
    parser.add_argument('--carpeta', type=Path, help='por omisión C:\\SIDP')
    parser.add_argument('--puerto', type=int, default=aplicacion.PUERTO)
    args = parser.parse_args(argumentos)
    sistema, expedientes = carpetas(args.carpeta)
    if sys.stdout is None or sys.stderr is None:  # El .exe de ventana no tiene consola: todo va al registro.
        registro = open(sistema / 'registros' / 'sidp.log', 'a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stderr = registro
    panel = f'http://127.0.0.1:{args.puerto}/'
    perfil = sistema / 'ventana'
    if args.apagar:
        print('SIDP apagado.' if apagar(sistema, args.puerto) else 'SIDP no estaba encendido.')
        return 0
    if ya_abierto(args.puerto):
        if not args.segundo_plano:
            abrir_ventana(panel, perfil)
        return 0
    app = aplicacion.Aplicacion(sistema, puerto=args.puerto, expedientes=expedientes, conectar_al_abrir=False)
    clave_apagar = secrets.token_urlsafe(16)
    (sistema / 'apagar.clave').write_text(clave_apagar, encoding='utf-8')
    servidor = aplicacion.crear_servidor(app, clave_apagar=clave_apagar)
    app.servidor = servidor
    programa = actualizar.programa_instalado()
    if programa:
        app.actualizador = actualizar.Actualizador(app, programa, version())
    app.vigia = Vigia(app)
    threading.Thread(target=app.vigia.trabajar, daemon=True).start()
    threading.Thread(target=aplicacion.respaldar_seguido, args=(app,), daemon=True).start()
    if not (expedientes / archivero.INDICE).exists():  # Instalación nueva o restaurada: se arman las carpetas de alumnos.
        def armar():
            with app.candado:
                app.bandeja.archivar_todo()
        threading.Thread(target=armar, daemon=True).start()
    print(f'{time.strftime("%Y-%m-%d %H:%M")} SIDP · datos en {sistema.parent} · panel {panel}', flush=True)
    if not args.segundo_plano:
        threading.Timer(0.5, abrir_ventana, (panel, perfil)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    while getattr(app, 'actualizando', False):  # Se está poniendo la versión nueva: ese hilo termina el proceso.
        time.sleep(1)
    return 0
