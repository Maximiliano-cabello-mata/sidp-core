"""Consumidor durable: inbox y cursor se confirman juntos, sin acceso a BD del servidor."""
import json
import sqlite3
from contratos.infraestructura import LoteEventos


class Observador:
    def __init__(self, ruta, flujo):
        self.ruta, self.flujo = str(ruta), flujo
        with sqlite3.connect(self.ruta) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cursores(flujo TEXT PRIMARY KEY, secuencia INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS recibidos(flujo TEXT NOT NULL, id TEXT NOT NULL, evento TEXT NOT NULL,
                    PRIMARY KEY(flujo,id));
            ''')

    def cursor(self):
        with sqlite3.connect(self.ruta) as db:
            fila = db.execute('SELECT secuencia FROM cursores WHERE flujo=?', (self.flujo,)).fetchone()
            return fila[0] if fila else 0

    def incorporar(self, datos):
        lote = LoteEventos.model_validate(datos)
        secuencias = [e.secuencia for e in lote.eventos]
        if secuencias != sorted(set(secuencias)) or (secuencias and lote.siguiente != secuencias[-1]):
            raise ValueError('Lote fuera de orden o cursor inconsistente')
        with sqlite3.connect(self.ruta) as db:
            db.execute('BEGIN IMMEDIATE')
            fila = db.execute('SELECT secuencia FROM cursores WHERE flujo=?', (self.flujo,)).fetchone()
            actual = fila[0] if fila else 0
            if not secuencias and lote.siguiente > actual:
                raise ValueError('Un lote vacío no puede saltar eventos')
            for evento in lote.eventos:
                anterior = db.execute('SELECT evento FROM recibidos WHERE flujo=? AND id=?', (self.flujo, evento.id)).fetchone()
                texto = evento.model_dump_json()
                if anterior and anterior[0] != texto:
                    raise ValueError('Mismo evento con otro contenido')
                db.execute('INSERT OR IGNORE INTO recibidos VALUES(?,?,?)', (self.flujo, evento.id, texto))
            db.execute('INSERT INTO cursores VALUES(?,?) ON CONFLICT(flujo) DO UPDATE SET secuencia=excluded.secuencia',
                       (self.flujo, max(actual, lote.siguiente)))

    def ciclo(self, cliente):
        respuesta = cliente.get('/api/v1/eventos', params={'despues': self.cursor(), 'limite': 100})
        respuesta.raise_for_status()
        self.incorporar(respuesta.json())
        return len(respuesta.json()['eventos'])
