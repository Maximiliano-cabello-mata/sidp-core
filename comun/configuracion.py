"""Configuración del nodo en archivos JSON pequeños, escritos de forma atómica.

Orden de precedencia: argumentos > variables de entorno > archivos en SIDP_HOME >
paquete de instalación incrustado en el ejecutable.
"""
import json
import os
import socket
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from comun import rutas

FORMATO = 1
PUERTO_PLATAFORMA = 8443
PUERTO_DESCUBRIMIENTO = 47800
ROLES = ('plataforma', 'agente', 'cerebro')
PERFILES = {'servidor': ['plataforma', 'agente'], 'estacion': ['agente'], 'coordinador': ['agente', 'cerebro']}


def escribir_json(ruta, datos, privado=False):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + '.tmp')
    temporal.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding='utf-8')
    if privado and os.name != 'nt':
        os.chmod(temporal, 0o600)
    os.replace(temporal, ruta)


def leer_json(ruta):
    ruta = Path(ruta)
    if not ruta.exists():
        return None
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    if datos.get('formato', FORMATO) > FORMATO:
        raise RuntimeError(f'{ruta} usa un formato más nuevo que este programa')
    return datos


@dataclass
class Paquete:
    """Paquete confidencial: contiene secreto compartido. Nunca publicar ni subir a Git."""
    instalacion: str
    nombre: str
    secreto: str
    certificado: str | None = None
    puerto: int = PUERTO_PLATAFORMA
    puerto_descubrimiento: int = PUERTO_DESCUBRIMIENTO
    url: str | None = None
    perfil: str = 'estacion'
    formato: int = FORMATO

    @property
    def esquema(self):
        return 'https' if self.certificado else 'http'

    def guardar(self, ruta):
        escribir_json(ruta, asdict(self), privado=True)

    @classmethod
    def desde(cls, datos):
        return cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__})


def ruta_paquete():
    return rutas.hogar() / 'instalacion.json'


def cargar_paquete(explicito=None):
    """Busca el paquete: ruta explícita, SIDP_HOME, junto al .exe o incrustado."""
    candidatos = [Path(explicito)] if explicito else []
    candidatos.append(ruta_paquete())
    if rutas.congelado():
        candidatos.append(Path(sys.executable).parent / 'instalacion.json')
    incrustado = rutas.recurso_empaquetado('instalacion.json')
    if incrustado:
        candidatos.append(incrustado)
    for candidato in candidatos:
        datos = leer_json(candidato)
        if datos:
            return Paquete.desde(datos)
    return None


@dataclass
class Nodo:
    """Qué roles ejecuta este equipo y dónde vio por última vez a la plataforma."""
    equipo: str = field(default_factory=lambda: nombre_equipo())
    roles: list = field(default_factory=lambda: ['agente'])
    url: str | None = None
    formato: int = FORMATO

    def guardar(self):
        escribir_json(rutas.hogar() / 'nodo.json', asdict(self))

    @classmethod
    def cargar(cls):
        datos = leer_json(rutas.hogar() / 'nodo.json')
        return cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__}) if datos else None


@dataclass
class Credencial:
    """Identidad técnica de un proceso. Una por rol y equipo."""
    identidad: str
    token: str
    url: str | None = None
    formato: int = FORMATO

    def guardar(self, rol):
        escribir_json(rutas.hogar() / 'credenciales' / f'{rol}.json', asdict(self), privado=True)

    @classmethod
    def cargar(cls, rol):
        datos = leer_json(rutas.hogar() / 'credenciales' / f'{rol}.json')
        return cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__}) if datos else None


def nombre_equipo():
    # Solo ASCII: el contrato exige [a-z0-9-] (un "Aula-Música" se vuelve "aula-m-sica").
    nombre = ''.join(c if c.isascii() and c.isalnum() else '-' for c in socket.gethostname().lower()).strip('-')
    return (nombre or 'equipo')[:40]

