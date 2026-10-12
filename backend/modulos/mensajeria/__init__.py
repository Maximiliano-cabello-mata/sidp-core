"""Outbox transaccional: diario durable reproducible, sin broker externo."""
import json
import time
import uuid
from fastapi import APIRouter, Depends, Query
from backend.contexto import contexto
from backend.modulos import Modulo
from backend.seguridad import requiere
from contratos.infraestructura import LoteEventos

MIGRACIONES = (
    """CREATE TABLE salida_eventos (
        secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL UNIQUE, version INTEGER NOT NULL CHECK(version=1),
        tipo TEXT NOT NULL, correlacion TEXT NOT NULL, propietario TEXT NOT NULL,
        fecha REAL NOT NULL, datos TEXT NOT NULL CHECK(json_valid(datos)));
    CREATE INDEX salida_propietario ON salida_eventos(propietario,secuencia);""",
)


def publicar(db, tipo, correlacion, propietario, datos):
    """El llamador proporciona SU transacción: no abrir otra conexión aquí."""
    if not db.in_transaction:
        raise RuntimeError('Publicar requiere la transacción del cambio de dominio')
    identificador = str(uuid.uuid4())
    db.execute('INSERT INTO salida_eventos(id,version,tipo,correlacion,propietario,fecha,datos) VALUES(?,1,?,?,?,?,?)',
               (identificador, tipo, correlacion, propietario, time.time(), json.dumps(datos)))
    return identificador


def leer(bd, actor, despues=0, limite=100):
    with bd.conexion() as db:
        if actor['rol'] == 'admin':
            filas = db.execute('SELECT * FROM salida_eventos WHERE secuencia>? ORDER BY secuencia LIMIT ?',
                               (despues, limite)).fetchall()
        else:
            filas = db.execute('SELECT * FROM salida_eventos WHERE propietario=? AND secuencia>? ORDER BY secuencia LIMIT ?',
                               (actor['id'], despues, limite)).fetchall()
    eventos = [{**dict(f), 'datos': json.loads(f['datos'])} for f in filas]
    return {'version': 1, 'eventos': eventos, 'siguiente': eventos[-1]['secuencia'] if eventos else despues}


rutas = APIRouter(prefix='/api/v1', tags=['mensajería'])


@rutas.get('/eventos', response_model=LoteEventos)
def eventos(despues: int = Query(default=0, ge=0), limite: int = Query(default=100, ge=1, le=200),
            actor=Depends(requiere('admin', 'cerebro')), ctx=Depends(contexto)):
    return leer(ctx.bd, actor, despues, limite)


MODULO = Modulo('mensajeria', '1.0', 'Diario transaccional de eventos', MIGRACIONES, rutas, depende=('sistema',))
