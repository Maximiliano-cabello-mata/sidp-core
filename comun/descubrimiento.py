"""Descubrimiento de la plataforma en la LAN por difusión UDP.

Solo responde la plataforma que conoce el secreto de la instalación, así un equipo
nunca se une a otra escuela ni a un impostor. Si la red bloquea la difusión, se usa
la URL fija del paquete o de nodo.json.
"""
import json
import logging
import secrets
import socket
import threading
import time
from comun import firma

TAMANO = 1024
registro = logging.getLogger('sidp.descubrimiento')


def _datos_respuesta(instalacion, reto, esquema, puerto):
    return {'instalacion': instalacion, 'reto': reto, 'esquema': esquema, 'puerto': puerto}


def responder(paquete, mensaje):
    """Respuesta firmada a una búsqueda válida de esta instalación, o None."""
    try:
        solicitud = json.loads(mensaje)
    except ValueError:
        return None
    if (not isinstance(solicitud, dict) or solicitud.get('sidp') != 'buscar'
            or solicitud.get('instalacion') != paquete.instalacion):
        return None
    reto = str(solicitud.get('reto', ''))[:64]
    datos = _datos_respuesta(paquete.instalacion, reto, paquete.esquema, paquete.puerto)
    return json.dumps({'sidp': 'plataforma', **datos, 'prueba': firma.firmar(paquete.secreto, datos)}).encode()


def validar(paquete, reto, mensaje, origen, cualquier_esquema=False):
    """URL de la plataforma si la respuesta está firmada por la instalación.

    cualquier_esquema: el equipo aún no tiene el certificado (alta por clave de escuela).
    """
    try:
        respuesta = json.loads(mensaje)
        datos = _datos_respuesta(paquete.instalacion, reto, respuesta['esquema'], int(respuesta['puerto']))
    except (ValueError, KeyError, TypeError):
        return None
    if ((datos['esquema'] != paquete.esquema and not cualquier_esquema)
            or datos['esquema'] not in ('http', 'https') or not 1 <= datos['puerto'] <= 65535
            or respuesta.get('instalacion') != paquete.instalacion
            or respuesta.get('sidp') != 'plataforma'
            or not firma.verificar(paquete.secreto, datos, respuesta.get('prueba'))):
        return None
    return f"{datos['esquema']}://{origen}:{datos['puerto']}"


def direcciones_locales():
    """IPv4 de las tarjetas de red de este equipo (Wi-Fi, cable y adaptadores virtuales)."""
    direcciones = set()
    try:
        for *_, (ip, _) in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            direcciones.add(ip)
    except OSError:
        pass
    try:  # La tarjeta de la ruta predeterminada, aunque el nombre del equipo no la resuelva.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as prueba:
            prueba.connect(('192.0.2.1', 9))
            direcciones.add(prueba.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in direcciones if not ip.startswith(('127.', '169.254.')))


def destinos_lan():
    """Difusión por cada red del equipo.

    Windows envía 255.255.255.255 por una sola tarjeta: con un adaptador virtual
    (VirtualBox, Hyper-V) la búsqueda podía no salir por la red de la escuela. La difusión
    dirigida (x.y.z.255) sale por la tarjeta de esa red. Se supone /24, lo habitual en una LAN.
    """
    dirigidas = [ip.rsplit('.', 1)[0] + '.255' for ip in direcciones_locales()]
    return ('255.255.255.255', *dirigidas, '127.0.0.1')


def buscar(paquete, espera=3.0, destinos=None, cualquier_esquema=False):
    destinos = destinos_lan() if destinos is None else destinos
    reto = secrets.token_hex(16)
    solicitud = json.dumps({'sidp': 'buscar', 'instalacion': paquete.instalacion, 'reto': reto}).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexion:
        conexion.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        conexion.settimeout(0.5)
        for destino in destinos:
            try:
                conexion.sendto(solicitud, (destino, paquete.puerto_descubrimiento))
            except OSError as error:
                registro.debug('Sin difusión hacia %s: %s', destino, error)
        limite = time.monotonic() + espera
        while time.monotonic() < limite:
            try:
                mensaje, (origen, _) = conexion.recvfrom(TAMANO)
            except socket.timeout:
                continue
            except OSError:
                break
            url = validar(paquete, reto, mensaje, origen, cualquier_esquema)
            if url:
                return url
    return None


class Respondedor(threading.Thread):
    """Hilo ligero dentro del proceso de plataforma."""

    def __init__(self, paquete, anfitrion='0.0.0.0'):
        super().__init__(name='descubrimiento', daemon=True)
        self.paquete = paquete
        self.conexion = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.conexion.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.conexion.bind((anfitrion, paquete.puerto_descubrimiento))
        self.conexion.settimeout(1.0)
        self.alto = threading.Event()

    def run(self):
        while not self.alto.is_set():
            try:
                mensaje, origen = self.conexion.recvfrom(TAMANO)
            except socket.timeout:
                continue
            except OSError:
                return
            respuesta = responder(self.paquete, mensaje)
            if respuesta:
                try:
                    self.conexion.sendto(respuesta, origen)
                except OSError as error:
                    registro.warning('No se pudo responder a %s: %s', origen, error)

    def detener(self):
        self.alto.set()
        self.join(timeout=2)
        self.conexion.close()

