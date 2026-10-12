"""Registros con rotación acotada: no llenar discos pequeños."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from comun import rutas


def configurar(rol, nivel=logging.INFO):
    raiz = logging.getLogger()
    if getattr(raiz, '_sidp', False):
        return logging.getLogger(f'sidp.{rol}')
    formato = logging.Formatter(f'%(asctime)s {rol} %(levelname)s %(name)s: %(message)s')
    consola = logging.StreamHandler(sys.stderr)
    consola.setFormatter(formato)
    raiz.addHandler(consola)
    try:
        archivo = RotatingFileHandler(rutas.carpeta('registros') / f'{rol}.log',
                                      maxBytes=1_000_000, backupCount=3, encoding='utf-8')
        archivo.setFormatter(formato)
        raiz.addHandler(archivo)
    except OSError:
        raiz.warning('Sin registro en archivo; solo consola')
    raiz.setLevel(nivel)
    for ruidoso in ('httpx', 'httpcore'):  # Una línea por petición llenaría el disco.
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    raiz._sidp = True
    return logging.getLogger(f'sidp.{rol}')
