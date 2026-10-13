"""Cola durable de tareas técnicas. Transacciones cortas; sin efectos externos."""
import json
import time
import uuid
from backend.base_datos import BaseDatos
from backend.modulos.mensajeria import MIGRACIONES as MIGRACIONES_MENSAJERIA, publicar
from comun.politicas import Cola
from contratos.infraestructura import PoliticaNodo, Telemetria, motivo_bloqueo

RESERVA_SEGUNDOS = 60
INTENTOS_MAXIMOS = 3
# Reparto (ADR-026): un agente cede una tarea sin destino si otro equipo disponible lleva menos.
EN_LINEA_S = 45
VENTANA_REPARTO_S = 120

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
    """ALTER TABLE dispositivos ADD COLUMN recursos INTEGER NOT NULL DEFAULT 0 CHECK(recursos IN (0,1));
    ALTER TABLE tareas ADD COLUMN iniciada REAL;
    CREATE TABLE politicas_nodo (
      dispositivo TEXT PRIMARY KEY REFERENCES dispositivos(id), revision INTEGER NOT NULL CHECK(revision>0),
      datos TEXT NOT NULL CHECK(json_valid(datos)));
    CREATE TABLE telemetria (
      dispositivo TEXT PRIMARY KEY REFERENCES dispositivos(id), recibida REAL NOT NULL,
      datos TEXT NOT NULL CHECK(json_valid(datos)));
    UPDATE tareas SET iniciada=creada WHERE estado='ejecutando';
    CREATE VIEW resumen_cola AS SELECT estado,COUNT(*) AS cantidad,MIN(creada) AS mas_antigua FROM tareas GROUP BY estado;
    CREATE INDEX tareas_reservas ON tareas(estado,vence);
    CREATE UNIQUE INDEX tarea_unica_por_agente ON tareas(dispositivo) WHERE estado='ejecutando';
    CREATE TRIGGER tarea_terminal_inmutable BEFORE UPDATE OF estado ON tareas
      WHEN OLD.estado IN ('completada','fallida') AND NEW.estado<>OLD.estado
      BEGIN SELECT RAISE(ABORT, 'Una tarea terminal no vuelve a ejecutarse'); END;""",
    # Tareas dirigidas a un agente concreto (pruebas de conectividad, periféricos locales).
    """ALTER TABLE tareas ADD COLUMN destino TEXT;""",
)


class Conflicto(ValueError):
    pass


class Saturada(ValueError):
    pass


class Almacen:
    def __init__(self, destino, politica=None):
        self.bd = destino if isinstance(destino, BaseDatos) else BaseDatos(destino)
        self.politica = politica or Cola.cargar()
        self.bd.migrar("mensajeria", MIGRACIONES_MENSAJERIA)
        self.bd.migrar("orquestacion", MIGRACIONES)
        self.ruta = self.bd.ruta

    def conexion(self):
        return self.bd.conexion()

    def evento(self, db, tipo, tarea, actor):
        db.execute("INSERT INTO eventos(tipo,tarea,actor,fecha) VALUES(?,?,?,?)",
                   (tipo, tarea, actor, time.time()))

        propietario = db.execute('SELECT actor FROM tareas WHERE id=?', (tarea,)).fetchone()[0]
        publicar(db, tipo, tarea, propietario, {'ejecutor': actor})

    def registrar(self, actor, capacidades, recursos=False):
        with self.bd.transaccion() as db:
            db.execute("INSERT INTO dispositivos(id,capacidades,ultimo,recursos) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                       "capacidades=excluded.capacidades, ultimo=excluded.ultimo, recursos=MAX(dispositivos.recursos,excluded.recursos)",
                       (actor, json.dumps(capacidades), time.time(), int(recursos)))

    def crear(self, actor, solicitud):
        with self.bd.transaccion() as db:
            anterior = db.execute("SELECT * FROM tareas WHERE actor=? AND clave=?", (actor, solicitud.clave)).fetchone()
            if anterior:
                if (anterior['mensaje'], anterior['operacion'], anterior['destino']) != (
                        solicitud.mensaje, solicitud.operacion, solicitud.destino):
                    raise Conflicto("Clave reutilizada con contenido diferente")
                return dict(anterior)
            if db.execute("SELECT COUNT(*) FROM tareas WHERE estado='pendiente'").fetchone()[0] >= self.politica.pendientes_maximos:
                raise Saturada('Cola llena; reintentar la misma clave más tarde')
            identificador = str(uuid.uuid4())
            db.execute("INSERT INTO tareas(id,actor,clave,operacion,mensaje,estado,creada,destino) "
                       "VALUES(?,?,?,?,?,'pendiente',?,?)",
                       (identificador, actor, solicitud.clave, solicitud.operacion, solicitud.mensaje, time.time(),
                        solicitud.destino))
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
            if db.execute("SELECT COUNT(*) FROM tareas WHERE estado='ejecutando'").fetchone()[0] >= self.politica.ejecuciones_maximas:
                return None
            politica = self._politica(db, actor)['politica']
            if politica.pausado:
                return None
            muestra = db.execute('SELECT * FROM telemetria WHERE dispositivo=?', (actor,)).fetchone()
            if dispositivo['recursos']:
                if not muestra or ahora - muestra['recibida'] > self.politica.telemetria_vigente_s:
                    return None
            if muestra and motivo_bloqueo(Telemetria.model_validate_json(muestra['datos']), politica):
                return None
            capacidades = json.loads(dispositivo['capacidades'])
            marcas = ",".join("?" * len(capacidades))
            tarea = db.execute(f"SELECT * FROM tareas WHERE estado='pendiente' AND operacion IN ({marcas}) "
                               "AND (destino IS NULL OR destino=?) ORDER BY creada,id LIMIT 1",
                               (*capacidades, actor)).fetchone()
            if not tarea:
                return None
            if not tarea['destino'] and self._turno_de_otro(db, actor, tarea['operacion'], ahora):
                return None
            db.execute("UPDATE tareas SET estado='ejecutando',dispositivo=?,reserva=?,vence=?,iniciada=?,intentos=intentos+1 WHERE id=?",
                       (actor, str(uuid.uuid4()), ahora + self.politica.reserva_s, ahora, tarea['id']))
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

    def _disponible(self, db, dispositivo, operacion, ahora):
        """Equipo en línea, libre, sin pausa ni sobrecarga y capaz de ejecutar la operación."""
        if ahora - dispositivo['ultimo'] > EN_LINEA_S or operacion not in json.loads(dispositivo['capacidades']):
            return False
        if db.execute("SELECT 1 FROM tareas WHERE estado='ejecutando' AND dispositivo=?", (dispositivo['id'],)).fetchone():
            return False
        politica = self._politica(db, dispositivo['id'])['politica']
        if politica.pausado:
            return False
        muestra = db.execute('SELECT * FROM telemetria WHERE dispositivo=?', (dispositivo['id'],)).fetchone()
        if dispositivo['recursos'] and (not muestra or ahora - muestra['recibida'] > self.politica.telemetria_vigente_s):
            return False
        return not (muestra and motivo_bloqueo(Telemetria.model_validate_json(muestra['datos']), politica))

    def _turno_de_otro(self, db, actor, operacion, ahora):
        """Reparto justo: el equipo más cercano al servidor no se queda con todo el trabajo."""
        desde = ahora - VENTANA_REPARTO_S

        def recientes(dispositivo):
            return db.execute("SELECT COUNT(*) FROM eventos WHERE tipo='tarea.reclamada' AND actor=? AND fecha>=?",
                              (dispositivo, desde)).fetchone()[0]
        propias = recientes(actor)
        if not propias:
            return False
        otros = db.execute('SELECT * FROM dispositivos WHERE id<>?', (actor,)).fetchall()
        return any(recientes(otro['id']) < propias for otro in otros if self._disponible(db, otro, operacion, ahora))

    def equipos(self):
        """Qué equipos están unidos, si están en línea, qué ofrecen y cuánto trabajo hicieron."""
        ahora = time.time()
        with self.bd.conexion() as db:
            filas = db.execute('SELECT d.*, t.datos AS telemetria FROM dispositivos d '
                               'LEFT JOIN telemetria t ON t.dispositivo=d.id ORDER BY d.id').fetchall()
            resultado = []
            for fila in filas:
                hechas = db.execute("SELECT COUNT(*) FROM eventos WHERE tipo='tarea.completada' AND actor=?",
                                    (fila['id'],)).fetchone()[0]
                resultado.append({'id': fila['id'], 'en_linea': ahora - fila['ultimo'] <= EN_LINEA_S,
                                  'hace_s': int(ahora - fila['ultimo']), 'capacidades': json.loads(fila['capacidades']),
                                  'recursos': json.loads(fila['telemetria']) if fila['telemetria'] else None,
                                  'pausado': self._politica(db, fila['id'])['politica'].pausado,
                                  'tareas_completadas': hechas})
            return resultado

    @staticmethod
    def _politica(db, actor):
        fila = db.execute('SELECT * FROM politicas_nodo WHERE dispositivo=?', (actor,)).fetchone()
        return {'revision': fila['revision'] if fila else 0,
                'politica': PoliticaNodo.model_validate_json(fila['datos']) if fila else PoliticaNodo()}

    def politica_nodo(self, actor):
        with self.bd.conexion() as db:
            return self._politica(db, actor)

    def cambiar_politica(self, actor, dispositivo, cambio):
        with self.bd.transaccion() as db:
            if not db.execute('SELECT 1 FROM dispositivos WHERE id=?', (dispositivo,)).fetchone():
                raise Conflicto('Dispositivo no registrado')
            actual = self._politica(db, dispositivo)
            if actual['revision'] != cambio.revision_esperada:
                raise Conflicto('Configuración modificada por otro operador; recargar')
            revision = actual['revision'] + 1
            db.execute('INSERT INTO politicas_nodo VALUES(?,?,?) ON CONFLICT(dispositivo) DO UPDATE SET revision=excluded.revision,datos=excluded.datos',
                       (dispositivo, revision, cambio.politica.model_dump_json()))
            publicar(db, 'dispositivo.configurado', dispositivo, actor, {'revision': revision})
            return {'revision': revision, 'politica': cambio.politica}

    def latido(self, actor, telemetria):
        with self.bd.transaccion() as db:
            if not db.execute('SELECT 1 FROM dispositivos WHERE id=?', (actor,)).fetchone():
                raise Conflicto('Registre el dispositivo primero')
            db.execute('UPDATE dispositivos SET recursos=1, ultimo=? WHERE id=?', (time.time(), actor))
            db.execute('INSERT INTO telemetria VALUES(?,?,?) ON CONFLICT(dispositivo) DO UPDATE SET recibida=excluded.recibida,datos=excluded.datos',
                       (actor, time.time(), telemetria.model_dump_json()))
            return self._politica(db, actor)

    def renovar(self, actor, identificador, reserva):
        with self.bd.transaccion() as db:
            tarea = db.execute('SELECT * FROM tareas WHERE id=?', (identificador,)).fetchone()
            ahora = time.time()
            if (not tarea or tarea['dispositivo'] != actor or tarea['reserva'] != reserva
                    or tarea['estado'] != 'ejecutando' or tarea['vence'] <= ahora):
                raise Conflicto('Reserva vencida, ajena o reemplazada')
            limite = (tarea['iniciada'] or tarea['creada']) + self.politica.duracion_maxima_s
            if limite <= ahora:
                raise Conflicto('Duración máxima del intento agotada')
            vence = min(ahora + self.politica.reserva_s, limite)
            db.execute('UPDATE tareas SET vence=? WHERE id=?', (vence, identificador))
            return {'vence': vence, 'reserva': reserva}

    def consultar(self, actor, identificador):
        with self.bd.conexion() as db:
            tarea = db.execute("SELECT * FROM tareas WHERE id=?", (identificador,)).fetchone()
        if not tarea or (actor['rol'] != 'admin' and tarea['actor'] != actor['id']):
            raise Conflicto("Tarea inexistente o ajena")
        return dict(tarea)

    def listar(self, actor):
        with self.bd.conexion() as db:
            if actor['rol'] == 'admin':
                filas = db.execute("SELECT * FROM tareas ORDER BY creada DESC LIMIT 100").fetchall()
            else:
                filas = db.execute("SELECT * FROM tareas WHERE actor=? ORDER BY creada DESC LIMIT 100", (actor['id'],)).fetchall()
            return [dict(f) for f in filas]

