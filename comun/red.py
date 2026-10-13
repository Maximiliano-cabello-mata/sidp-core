"""Clientes HTTP hacia la plataforma con certificado fijado (pinning)."""
import os
import ssl
import httpx
from comun import configuracion
from comun.politicas import Transporte


def contexto_tls(certificado_pem):
    """Confía solo en el certificado de la instalación, sin depender del nombre o IP."""
    # No cargar autoridades del SO: la instalación es la única raíz de confianza.
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2
    contexto.load_verify_locations(cadata=certificado_pem)
    contexto.check_hostname = False  # Las IP de la LAN cambian; la confianza es el certificado.
    contexto.verify_mode = ssl.CERT_REQUIRED
    return contexto


def verificacion(paquete):
    return contexto_tls(paquete.certificado) if paquete and paquete.certificado else True


def cliente(url, token=None, paquete=None, timeout=None):
    destino = httpx.URL(url)
    if destino.scheme not in ('http', 'https') or not destino.host or destino.userinfo:
        raise ValueError('URL de plataforma inválida')
    if paquete and paquete.certificado and destino.scheme != 'https':
        raise ValueError('Una instalación TLS no admite degradación a HTTP')
    politica = Transporte.cargar()
    cabeceras = {'Authorization': 'Bearer ' + token} if token else {}
    # trust_env=False: el tráfico de la LAN nunca pasa por proxies configurados en el sistema.
    limites = httpx.Limits(max_connections=politica.conexiones, max_keepalive_connections=politica.conexiones)
    plazo = timeout if timeout is not None else httpx.Timeout(politica.lectura_s, connect=politica.conexion_s)
    return httpx.Client(base_url=url, headers=cabeceras, timeout=plazo, verify=verificacion(paquete),
                        limits=limites, follow_redirects=False, trust_env=False)


def causa(error):
    """Por qué no se llegó a la plataforma, en palabras del usuario (sin ocultar el detalle técnico)."""
    texto = str(error) or type(error).__name__
    if 'CERTIFICATE' in texto.upper():
        return ('el certificado del servidor no es el que guardó este equipo; '
                'si el servidor se reinstaló, vuelva a unir este equipo')
    if isinstance(error, httpx.TimeoutException):
        return f'el servidor no contesta ({texto}): revise que esté encendido, el cortafuegos y que la red sea Privada'
    if any(clave in texto.lower() for clave in ('refused', 'rechaz', '10061', '[errno 111]')):
        return f'el servidor rechazó la conexión ({texto}): SIDP-Servidor no está abierto en esa dirección'
    return texto


def resolver(rol, paquete=None):
    """URL y token del proceso: entorno (laboratorio) o credencial enrolada."""
    credencial = configuracion.Credencial.cargar(rol)
    nodo = configuracion.Nodo.cargar()
    token = os.environ.get('SIDP_TOKEN') or (credencial.token if credencial else None)
    url = (os.environ.get('SIDP_URL') or (nodo.url if nodo else None)
           or (credencial.url if credencial else None) or 'http://127.0.0.1:8000')
    if not token:
        raise SystemExit(f'Sin credencial para {rol}: ejecute "sidp unirse" o defina SIDP_TOKEN')
    return url, token

