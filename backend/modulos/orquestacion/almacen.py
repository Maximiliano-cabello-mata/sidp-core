"""Cola durable de tareas técnicas. Transacciones cortas; sin efectos externos."""
import json
import time
import uuid
from backend.base_datos import BaseDatos

RESERVA_SEGUNDOS = 60
INTENTOS_MAXIMOS = 3

MIGRACIONES = (
    """CREATE TABLE IF NOT EXISTS dispositivos (
     id TEXT PRIMARY KEY, capacidades TEXT NOT NULL, ultimo REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS tareas (
     id TEXT PRIMARY KEY, actor TEXT NOT NULL, clave TEXT NOT NULL,
     operacion TEXT NOT NULL, mensaje TEXT NOT NULL,
     estado TEXT NOT NULL CHECK(estado IN ('pendiente','ejecutando','completada','fallida')),
     dispositivo TEXT, reserva TEXT, vence REAL, intentos INTEGER NOT NULL DEFAULT 0,
     resultado TEXT, creada REAL NOT NULL, UNIQUE(actor, clave));
    CREATE TABLE IF NOT EXISTS eventos (
     secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
     tipo TEXT NOT NULL, tarea TEXT NOT NULL, actor TEXT NOT NULL, fecha REAL NOT NULL);""",
    """CREATE INDEX IF NOT EXISTS tareas_estado ON tareas(estado, creada);""",
)


class Conflicto(ValueError):
    pass


class Almacen:
    def __init__(self, destino):
        self.bd = destino if isinstance(destino, BaseDatos) else BaseDatos(destino)
        self.bd.migrar("orquestacion", MIGRACIONES)
        self.ruta = self.bd.ruta

    def conexion(self):
        return self.bd.conexion()

    def evento(self, db, tipo, tarea, actor):
        db.execute("INSERT INTO eventos(tipo,tarea,actor,fecha) VALUES(?,?,?,?)",
                   (tipo, tarea, actor, time.time()))

    def registrar(self, actor, capacidades):
        with self.bd.transaccion() as db:
            db.execute("INSERT INTO dispositivos VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET "
                       "capacidades=excluded.capacidades, ultimo=excluded.ultimo",
                       (actor, json.dumps(capacidades), time.time()))

    def crear(self, actor, solicitud):
        with self.bd.transaccion() as db:
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
        with self.bd.transaccion() as db:
            dispositivo = db.execute("SELECT * FROM dispositivos WHERE id=?", (actor,)).fetchone()
            if not dispositivo:
                raise Conflicto("Registre el dispositivo primero")
            ahora = time.time()
            db.execute("UPDATE dispositivos SET ultimo=? WHERE id=?", (ahora, actor))
            for tarea in db.execute("SELECT * FROM tareas WHERE estado='ejecutando' AND vence<=?", (ahora,)).fetchall():
                estado = 'fallida' if tarea['intentos'] >= INTENTOS_MAXIMOS else 'pendiente'
                db.execute("UPDATE tareas SET estado=?, reserva=NULL, dispositivo=NULL WHERE id=?", (estado, tarea['id']))
                self.evento(db, "reserva.vencida", tarea['id'], actor)
            # Una tarea simultánea por agente: equipos modestos no se saturan.
            if db.execute("SELECT 1 FROM tareas WHERE estado='ejecutando' AND dispositivo=?", (actor,)).fetchone():
                return None
            capacidades = json.loads(dispositivo['capacidades'])
            marcas = ",".join("?" * len(capacidades))
            tarea = db.execute(f"SELECT * FROM tareas WHERE estado='pendiente' AND operacion IN ({marcas}) "
                               "ORDER BY creada,id LIMIT 1", capacidades).fetchone()
            if not tarea:
                return None
            db.execute("UPDATE tareas SET estado='ejecutando',dispositivo=?,reserva=?,vence=?,intentos=intentos+1 WHERE id=?",
                       (actor, str(uuid.uuid4()), ahora + RESERVA_SEGUNDOS, tarea['id']))
            self.evento(db, "tarea.reclamada", tarea['id'], actor)
            return dict(db.execute("SELECT * FROM tareas WHERE id=?", (tarea['id'],)).fetchone())

    def completar(self, actor, identificador, resultado):
        with self.bd.transaccion() as db:
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
        with self.bd.conexion() as db:
            if actor['rol'] == 'admin':
                filas = db.execute("SELECT * FROM tareas ORDER BY creada DESC LIMIT 100").fetchall()
            else:
                filas = db.execute("SELECT * FROM tareas WHERE actor=? ORDER BY creada DESC LIMIT 100", (actor['id'],)).fetchall()
            return [dict(f) for f in filas]
