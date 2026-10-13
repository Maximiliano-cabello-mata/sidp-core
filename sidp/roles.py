"""Arranque de cada rol como proceso independiente."""
import logging
import os
import sys
import uvicorn
from comun import configuracion, descubrimiento, registros, rutas

registro = logging.getLogger('sidp.plataforma')


def plataforma(anfitrion=None, puerto=None):
    registros.configurar('plataforma')
    paquete = configuracion.cargar_paquete()
    opciones = {}
    if paquete:
        tls = rutas.datos_plataforma() / 'tls'
        if paquete.certificado:
            opciones = {'ssl_certfile': str(tls / 'certificado.pem'), 'ssl_keyfile': str(tls / 'clave.pem')}
        anfitrion = anfitrion or os.environ.get('SIDP_ANFITRION', '0.0.0.0')
        puerto = puerto or paquete.puerto
        try:
            descubrimiento.Respondedor(paquete).start()
        except OSError as error:
            registro.warning('Descubrimiento desactivado (puerto %s ocupado): %s', paquete.puerto_descubrimiento, error)
    else:
        registro.warning('Sin instalación: modo laboratorio en loopback, identidades por SIDP_IDENTIDADES')
        anfitrion, puerto = anfitrion or '127.0.0.1', puerto or 8000
    from sidp import puertos
    if paquete and puertos.ocupado(puerto, anfitrion):  # Otro programa lo tomó: el supervisor espera y reintenta.
        registro.error(puertos.mensaje(puerto).replace('\n', ' '))
        sys.exit(3)
    from backend.main import app
    # Un solo proceso, sin recarga ni extras: huella mínima en equipos modestos.
    uvicorn.run(app, host=anfitrion, port=puerto, workers=1, access_log=False,
                limit_concurrency=64, timeout_keep_alive=30, log_config=None, **opciones)


def agente():
    from agente.__main__ import main
    main()


def cerebro(argumentos):
    from cerebro.__main__ import main
    main(argumentos)
