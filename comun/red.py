"""Clientes HTTP hacia la plataforma con certificado fijado (pinning)."""
import os
import ssl
import tempfile
import httpx
from comun import configuracion


def contexto_tls(certificado_pem):
    """Confía solo en el certificado de la instalación, sin depender del nombre o IP."""
    contexto = ssl.create_default_context()
    with tempfile.NamedTemporaryFile('w', suffix='.pem', delete=False) as archivo:
        archivo.write(certificado_pem)
    try:
        contexto.load_verify_locations(archivo.name)
    finally:
        os.unlink(archivo.name)
    contexto.check_hostname = False  # Las IP de la LAN cambian; la confianza es el certificado.
    contexto.verify_mode = ssl.CERT_REQUIRED
    return contexto


def verificacion(paquete):
    return contexto_tls(paquete.certificado) if paquete and paquete.certificado else True


def cliente(url, token=None, paquete=None, timeout=10):
    cabeceras = {'Authorization': 'Bearer ' + token} if token else {}
    # trust_env=False: el tráfico de la LAN nunca pasa por proxies configurados en el sistema.
    return httpx.Client(base_url=url, headers=cabeceras, timeout=timeout, verify=verificacion(paquete),
                        trust_env=False)


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
