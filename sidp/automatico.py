"""Alta automática con clave de escuela (ADR-025): el mismo sidp.exe en todos los equipos.

Primer arranque de un equipo sin configuración:
  1. Deriva identificador y secreto de la instalación a partir de la clave.
  2. Busca por difusión UDP una plataforma de esa instalación (respuesta firmada).
  3. Si la encuentra, descarga los datos públicos del paquete (certificado incluido),
     comprueba su firma y se une como agente, aprobado al instante.
  4. Si no hay ninguna, este equipo crea la instalación y queda como servidor.
"""
import random
import time
import httpx
from comun import configuracion, descubrimiento, firma
from comun.configuracion import Paquete
from sidp import instalacion
from sidp.errores import ErrorInstalacion

NOMBRE_PREDETERMINADO = 'SIDP'
RONDAS = 2  # Dos búsquedas separadas al azar: dos equipos encendidos a la vez no crean dos instalaciones.


def buscar(clave, espera=3.0, rondas=RONDAS, puerto_descubrimiento=configuracion.PUERTO_DESCUBRIMIENTO,
           destinos=('255.255.255.255', '127.0.0.1')):
    identificador, secreto = firma.derivar_clave(clave)
    provisional = Paquete(instalacion=identificador, nombre='', secreto=secreto, por_clave=True,
                          puerto_descubrimiento=puerto_descubrimiento)
    for ronda in range(rondas):
        url = descubrimiento.buscar(provisional, espera, destinos, cualquier_esquema=True)
        if url:
            return url, provisional
        if ronda + 1 < rondas:
            time.sleep(random.uniform(1, 4))
    return None, provisional


def descargar_paquete(url, provisional):
    """Datos públicos firmados con el secreto: sin la clave correcta no hay paquete válido."""
    # Sin verificar TLS en esta única petición: aún no hay certificado; la confianza la da la firma.
    with httpx.Client(base_url=url, verify=False, timeout=10, trust_env=False, follow_redirects=False) as cliente:
        respuesta = cliente.get('/api/v1/enrolamiento/paquete')
    if respuesta.status_code != 200:
        raise ErrorInstalacion(f'La plataforma en {url} no acepta clave de escuela ({respuesta.status_code})')
    datos = respuesta.json()
    prueba = datos.pop('prueba', None)
    if datos.get('instalacion') != provisional.instalacion or not firma.verificar(provisional.secreto, datos, prueba):
        raise ErrorInstalacion(f'{url} no pertenece a la instalación de esta clave')
    return Paquete.desde({**datos, 'secreto': provisional.secreto, 'por_clave': True})


def preparar(clave, nombre=None, puerto=configuracion.PUERTO_PLATAFORMA, aviso=None, espera=3.0, rondas=RONDAS,
             puerto_descubrimiento=configuracion.PUERTO_DESCUBRIMIENTO, destinos=('255.255.255.255', '127.0.0.1'),
             cortafuegos=True, url=None):
    """Deja el equipo configurado y devuelve 'servidor' o 'estacion'.

    url: dirección del servidor cuando la red bloquea la difusión UDP; entonces no se busca ni se crea nada.
    """
    aviso = aviso or (lambda texto: print(texto, flush=True))
    if url:
        url, provisional = url, buscar(clave, rondas=0)[1]
    else:
        aviso('Buscando otras computadoras de la escuela en la red...')
        url, provisional = buscar(clave, espera, rondas, puerto_descubrimiento, destinos)
    if url:
        paquete = descargar_paquete(url, provisional)
        paquete.guardar(configuracion.ruta_paquete())
        instalacion.unirse(paquete, ['agente'], url=url, aviso=aviso)
        return 'estacion'
    aviso('No hay otra computadora con esta clave: esta será el servidor de la escuela.')
    resultado = instalacion.crear(nombre or NOMBRE_PREDETERMINADO, puerto, clave=clave,
                                  puerto_descubrimiento=puerto_descubrimiento)
    aviso(f'Instalación "{resultado["paquete"].nombre}" creada. Las demás computadoras se unirán con la misma clave.')
    if cortafuegos:
        from sidp import conectividad
        conectividad.abrir_cortafuegos_automatico(resultado['paquete'], aviso)
    return 'servidor'
