"""Snapshot SQLite consistente mediante Backup API; solo para operador local."""
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path


def crear(bd, destino):
    destino = Path(destino).resolve()
    manifiesto_ruta = destino.with_suffix(destino.suffix + '.json')
    if destino == Path(bd.ruta).resolve() or destino.exists() or manifiesto_ruta.exists():
        raise ValueError('El destino debe ser nuevo y distinto de la base activa')
    destino.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(prefix='sidp-respaldo-', suffix='.db', dir=destino.parent)
    os.close(descriptor)
    try:
        with bd.conexion() as origen, closing(sqlite3.connect(temporal)) as copia:
            origen.backup(copia, pages=128, sleep=0.05)
            if copia.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('La copia no pasó quick_check')
            esquemas = dict(copia.execute('SELECT modulo,version FROM esquema'))
        # Creación exclusiva evita sobrescribir copias de otro operador concurrente.
        with open(temporal, 'rb') as entrada, destino.open('xb') as salida:
            if os.name != 'nt':
                os.chmod(destino, 0o600)
            resumen = hashlib.sha256()
            while bloque := entrada.read(1024 * 1024):
                salida.write(bloque)
                resumen.update(bloque)
            salida.flush()
            os.fsync(salida.fileno())
        manifiesto = {'formato': 1, 'fecha': time.time(), 'sha256': resumen.hexdigest(),
                      'esquemas': esquemas, 'archivo': destino.name}
        with manifiesto_ruta.open('x', encoding='utf-8') as salida:
            salida.write(json.dumps(manifiesto, indent=2))
        return manifiesto
    finally:
        Path(temporal).unlink(missing_ok=True)
