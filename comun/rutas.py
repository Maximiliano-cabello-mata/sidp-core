"""Ubicación de datos del nodo. Una sola carpeta por equipo, fuera del ejecutable."""
import os
import sys
from pathlib import Path


def congelado():
    """True cuando corre como ejecutable empaquetado (PyInstaller)."""
    return bool(getattr(sys, 'frozen', False))


def hogar():
    """Carpeta raíz del nodo: SIDP_HOME, o la ubicación estándar del sistema."""
    if os.environ.get('SIDP_HOME'):
        return Path(os.environ['SIDP_HOME'])
    if os.name == 'nt':
        return Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'SIDP'
    return Path.home() / '.sidp'


def carpeta(*partes):
    ruta = hogar().joinpath(*partes)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def datos_plataforma():
    # SIDP_DATA_DIR se conserva por compatibilidad con el laboratorio.
    if os.environ.get('SIDP_DATA_DIR'):
        ruta = Path(os.environ['SIDP_DATA_DIR'])
        ruta.mkdir(parents=True, exist_ok=True)
        return ruta
    return carpeta('plataforma')


def datos_agente():
    if os.environ.get('SIDP_AGENTE_DIR'):
        ruta = Path(os.environ['SIDP_AGENTE_DIR'])
        ruta.mkdir(parents=True, exist_ok=True)
        return ruta
    return carpeta('agente')


def recurso_empaquetado(nombre):
    """Archivo incrustado en el ejecutable, o None si no existe."""
    base = getattr(sys, '_MEIPASS', None)
    if base and (Path(base) / nombre).exists():
        return Path(base) / nombre
    return None
