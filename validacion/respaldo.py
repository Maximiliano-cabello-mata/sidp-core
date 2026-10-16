"""La PC 4 como respaldo del servidor: una copia de todo lo que guarda SIDP-Validador.exe.

La base principal sigue en la PC del administrador (el .exe). La PC 4 guarda una copia fiel de su carpeta de datos:
las bases SQLite y los expedientes (PDF y fotos). Nada se sobrescribe: si un archivo cambió, la versión anterior se
queda en `versiones/` con la fecha. Solo viaja lo nuevo o lo que cambió (se compara por la huella sha256).

Lado del .exe: `respaldar_en_cerebro(carpeta, url, clave)`. Lado de la PC 4: `Almacen` (lo usa cerebro_red en /respaldo).
"""
import base64
import datetime
import hashlib
import json
import os
import sqlite3
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

MAXIMO_ARCHIVO = 60 * 1024 * 1024
NO_SE_RESPALDA = {'configuracion.json'}  # Trae la clave del cerebro: la PC 4 ya la tiene.


def carpeta_por_omision():
    return Path(os.environ.get('SIDP_RESPALDO') or (Path('C:/SIDP-datos/respaldo') if os.name == 'nt' else Path.home() / 'SIDP-datos' / 'respaldo'))


def ruta_segura(ruta):
    """La ruta relativa tal como llegó, sin subir de carpeta ni ser absoluta. ValueError si no es segura."""
    partes = PurePosixPath(str(ruta).replace('\\', '/')).parts
    if not partes or any(p in ('', '.', '..') or ':' in p for p in partes) or str(ruta).startswith(('/', '\\')):
        raise ValueError(f'ruta no válida: {ruta}')
    return Path(*partes)


class Almacen:
    """La carpeta de respaldo en la PC 4: actual/ (la copia al día) y versiones/ (lo que había antes)."""

    def __init__(self, carpeta=None):
        self.carpeta = Path(carpeta or carpeta_por_omision())

    def faltan(self, archivos):
        """De [{ruta, sha256}], las rutas que la PC 4 no tiene iguales."""
        faltan = []
        for archivo in archivos:
            destino = self.carpeta / 'actual' / ruta_segura(archivo['ruta'])
            if not destino.is_file() or _huella(destino.read_bytes()) != archivo['sha256']:
                faltan.append(archivo['ruta'])
        return faltan

    def guardar(self, ruta, contenido, sha256):
        """'igual', 'nuevo' o 'cambiado'. Si cambió, la copia anterior pasa a versiones/ con la fecha."""
        if _huella(contenido) != sha256:
            raise ValueError(f'{ruta}: el archivo llegó incompleto')
        relativa = ruta_segura(ruta)
        destino = self.carpeta / 'actual' / relativa
        estado = 'nuevo'
        if destino.is_file():
            if _huella(destino.read_bytes()) == sha256:
                return 'igual'
            sello = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            anterior = self.carpeta / 'versiones' / relativa.parent / f'{relativa.name}.{sello}'
            anterior.parent.mkdir(parents=True, exist_ok=True)
            destino.replace(anterior)
            estado = 'cambiado'
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + '.llegando')
        temporal.write_bytes(contenido)
        temporal.replace(destino)
        return estado

    def anotar(self, resumen):
        bitacora = self.carpeta / 'bitacora_respaldo.jsonl'
        bitacora.parent.mkdir(parents=True, exist_ok=True)
        with bitacora.open('a', encoding='utf-8') as salida:
            salida.write(json.dumps({'fecha': datetime.datetime.now().isoformat(timespec='seconds'), **resumen}, ensure_ascii=False) + '\n')

    def estado(self):
        actual = self.carpeta / 'actual'
        archivos = [p for p in actual.rglob('*') if p.is_file()] if actual.is_dir() else []
        ultimo = None
        bitacora = self.carpeta / 'bitacora_respaldo.jsonl'
        if bitacora.is_file():
            renglones = bitacora.read_text(encoding='utf-8').strip().splitlines()
            ultimo = json.loads(renglones[-1]) if renglones else None
        return {'archivos': len(archivos), 'megas': round(sum(p.stat().st_size for p in archivos) / 1024 / 1024, 1), 'ultimo': ultimo}


def _huella(contenido):
    return hashlib.sha256(contenido).hexdigest()


def _copia_sqlite(ruta):
    """Una copia consistente de una base SQLite aunque el .exe la esté usando."""
    with tempfile.TemporaryDirectory() as carpeta:
        destino = Path(carpeta) / 'copia.db'
        origen = sqlite3.connect(str(ruta))
        copia = sqlite3.connect(str(destino))
        try:
            origen.backup(copia)
        finally:
            copia.close()
            origen.close()
        return destino.read_bytes()


def archivos_de(carpeta):
    """[(ruta relativa con /, contenido)] de la carpeta de datos del .exe, sin lo que no se respalda."""
    carpeta = Path(carpeta)
    salida = []
    for ruta in sorted(carpeta.rglob('*')):
        relativa = ruta.relative_to(carpeta).as_posix()
        if not ruta.is_file() or ruta.name in NO_SE_RESPALDA or ruta.suffix in ('.llegando', '.tmp') or ruta.name.endswith(('-journal', '-wal', '-shm')):
            continue
        if ruta.stat().st_size > MAXIMO_ARCHIVO:
            continue
        salida.append((relativa, _copia_sqlite(ruta) if ruta.suffix == '.db' else ruta.read_bytes()))
    return salida


def _pedir(url, ruta, datos, clave, espera=300):
    solicitud = urllib.request.Request(url.rstrip('/') + ruta, json.dumps(datos).encode(),
                                       {'Content-Type': 'application/json', 'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return json.load(respuesta)


def respaldar_en_cerebro(carpeta, url, clave):
    """Lado del .exe: manda a la PC 4 lo nuevo o cambiado de su carpeta de datos. Devuelve cuántos y cuánto."""
    archivos = archivos_de(carpeta)
    huellas = {ruta: _huella(contenido) for ruta, contenido in archivos}
    faltan = set(_pedir(url, '/respaldo/faltan', {'archivos': [{'ruta': r, 'sha256': h} for r, h in huellas.items()]}, clave)['faltan'])
    enviados, bytes_enviados = 0, 0
    for ruta, contenido in archivos:
        if ruta not in faltan:
            continue
        _pedir(url, '/respaldo/archivo', {'ruta': ruta, 'sha256': huellas[ruta], 'contenido': base64.b64encode(contenido).decode()}, clave)
        enviados += 1
        bytes_enviados += len(contenido)
    final = _pedir(url, '/respaldo/listo', {'archivos': len(archivos), 'enviados': enviados}, clave)
    return {'archivos': len(archivos), 'enviados': enviados, 'megas_enviados': round(bytes_enviados / 1024 / 1024, 1), **final}
