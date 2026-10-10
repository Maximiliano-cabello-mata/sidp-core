"""Cola durable local. Transacciones cortas; solo tareas técnicas sin efectos externos."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Conflicto(ValueError):
    pass


class Almacen:
    def __init__(self, ruta):
        self.ruta = str(ruta)
        Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        with self.conexion() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("Base de orquestación más nueva que esta aplicación")
            if version == 0:
                sql = Path(__file__).parents[1] / "database/migraciones/001_orquestacion.sql"
                db.executescript("BEGIN IMMEDIATE;\n" + sql.read_text() + "\nPRAGMA user_version=1; COMMIT;")

    @contextmanager
    def conexion(self):
        db = sqlite3.connect(self.ruta, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def evento(self, db, tipo, tarea, actor):
        db.execute("INSERT INTO eventos(tipo,tarea,actor,fecha) VALUES(?,?,?,?)",
                   (tipo, tarea, actor, time.time()))

    def registrar(self, actor, capacidades):
        with self.conexion() as db:
            db.execute("INSERT INTO dispositivos VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET capacidades=excluded.capacidades, ultimo=excluded.ultimo",
                       (actor, json.dumps(capacidades), time.time()))

    def crear(self, actor, solicitud):
        with self.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            anterior = db.execute("SELECT * FROM tareas WHERE actor=? AND clave=?", (actor, solicitud.clave)).fetchone()
            if anterior:
                if anterior['mensaje'] != solicitud.mensaje or anterior['operacion'] != solicitud.operacion:
                    raise Conflicto("Clave reutilizada con contenido diferente")
                return dict(anterior)
            identificador = str(uuid.uuid4())
            db.execute("INSERT INTO tareas(id,actor,clave,operacion,mensaje,estado,creada) VALUES(?,?,?,?,?,'pendiente',?)",
                       (identificador, actor, solicitud.clave, solicitud.operacion, solicitud.mensaje, time.time()))
            self.evento(db, "tarea.creada", identificador, actor)
            return dict(db.execute("SELECT * FROM tareas WHERE id=?", (identificador,)).fetchone())

    def reclamar(self, actor):
        with self.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            dispositivo = db.execute("SELECT * FROM dispositivos WHERE id=?", (actor,)).fetchone()
            if not dispositivo:
                raise Conflicto("Registre el dispositivo primero")
            ahora = time.time()
            vencidas = db.execute("SELECT * FROM tareas WHERE estado='ejecutando' AND vence<=?", (ahora,)).fetchall()
            for tarea in vencidas:
                estado = 'fallida' if tarea['intentos'] >= 3 else 'pendiente'
                db.execute("UPDATE tareas SET estado=?, reserva=NULL, dispositivo=NULL WHERE id=?", (estado, tarea['id']))
                self.evento(db, "reserva.vencida", tarea['id'], actor)
            # Una tarea simultánea por agente en esta primera versión.
            if db.execute("SELECT 1 FROM tareas WHERE estado='ejecutando' AND dispositivo=?", (actor,)).fetchone():
                return None
            capacidades = json.loads(dispositivo['capacidades'])
            filas = db.execute("SELECT * FROM tareas WHERE estado='pendiente' ORDER BY creada,id").fetchall()
            tarea = next((t for t in filas if t['operacion'] in capacidades), None)
            if not tarea:
                return None
            db.execute("UPDATE tareas SET estado='ejecutando',dispositivo=?,reserva=?,vence=?,intentos=intentos+1 WHERE id=?",
                       (actor, str(uuid.uuid4()), ahora + 60, tarea['id']))
            self.evento(db, "tarea.reclamada", tarea['id'], actor)
            return dict(db.execute("SELECT * FROM tareas WHERE id=?", (tarea['id'],)).fetchone())

    def completar(self, actor, identificador, resultado):
        with self.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            tarea = db.execute("SELECT * FROM tareas WHERE id=?", (identificador,)).fetchone()
            if not tarea or tarea['dispositivo'] != actor or tarea['reserva'] != resultado.reserva:
                raise Conflicto("Reserva ajena o reemplazada")
            if tarea['estado'] == 'completada' and tarea['resultado'] == resultado.mensaje:
                return dict(tarea)
            if tarea['estado'] != 'ejecutando' or tarea['vence'] <= time.time():
                raise Conflicto("Reserva vencida o tarea terminada")
            if resultado.mensaje != tarea['mensaje']:
                raise Conflicto("El diagnóstico echo no coincide con la entrada")
            db.execute("UPDATE tareas SET estado='completada',resultado=? WHERE id=?", (resultado.mensaje, identificador))
            self.evento(db, "tarea.completada", identificador, actor)
            return dict(db.execute("SELECT * FROM tareas WHERE id=?", (identificador,)).fetchone())

    def listar(self, actor):
        with self.conexion() as db:
            if actor['rol'] == 'admin':
                filas = db.execute("SELECT * FROM tareas ORDER BY creada DESC LIMIT 100").fetchall()
            else:
                filas = db.execute("SELECT * FROM tareas WHERE actor=? ORDER BY creada DESC LIMIT 100", (actor['id'],)).fetchall()
            return [dict(f) for f in filas]
