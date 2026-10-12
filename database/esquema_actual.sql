-- Generado por python -m herramientas.exportar_esquema. Para bases nuevas, no migrar existentes con este archivo.
PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE alumnos (
     id INTEGER PRIMARY KEY, curp VARCHAR(18) UNIQUE, nombre VARCHAR(100) NOT NULL,
     apellido_paterno VARCHAR(100) NOT NULL, apellido_materno VARCHAR(100), activo BOOLEAN NOT NULL DEFAULT 1);
CREATE TABLE auditoria (
     secuencia INTEGER PRIMARY KEY AUTOINCREMENT, fecha REAL NOT NULL, actor TEXT NOT NULL,
     accion TEXT NOT NULL, objeto TEXT NOT NULL, detalle TEXT);
CREATE TABLE ciclos_escolares (
     id INTEGER PRIMARY KEY, nombre VARCHAR(50) NOT NULL UNIQUE, fecha_inicio DATE NOT NULL,
     fecha_fin DATE NOT NULL, activo BOOLEAN NOT NULL DEFAULT 1);
CREATE TABLE dispositivos (
     id TEXT PRIMARY KEY, capacidades TEXT NOT NULL, ultimo REAL NOT NULL, recursos INTEGER NOT NULL DEFAULT 0 CHECK(recursos IN (0,1)));
CREATE TABLE esquema(modulo TEXT PRIMARY KEY, version INTEGER NOT NULL);
CREATE TABLE eventos (
     secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
     tipo TEXT NOT NULL, tarea TEXT NOT NULL, actor TEXT NOT NULL, fecha REAL NOT NULL);
CREATE TABLE identidades (
     id TEXT PRIMARY KEY, equipo TEXT NOT NULL,
     rol TEXT NOT NULL CHECK(rol IN ('admin','cerebro','agente')),
     token_resumen TEXT NOT NULL UNIQUE,
     estado TEXT NOT NULL CHECK(estado IN ('pendiente','aprobada','revocada')),
     origen TEXT NOT NULL, creada REAL NOT NULL, aprobada REAL, ultimo REAL);
CREATE TABLE invitaciones (
     codigo_resumen TEXT PRIMARY KEY, rol TEXT NOT NULL, creada REAL NOT NULL, vence REAL NOT NULL,
     actor TEXT NOT NULL, usada REAL, identidad TEXT);
CREATE TABLE politicas_nodo (
      dispositivo TEXT PRIMARY KEY REFERENCES dispositivos(id), revision INTEGER NOT NULL CHECK(revision>0),
      datos TEXT NOT NULL CHECK(json_valid(datos)));
CREATE TABLE salida_eventos (
        secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL UNIQUE, version INTEGER NOT NULL CHECK(version=1),
        tipo TEXT NOT NULL, correlacion TEXT NOT NULL, propietario TEXT NOT NULL,
        fecha REAL NOT NULL, datos TEXT NOT NULL CHECK(json_valid(datos)));
CREATE TABLE tareas (
     id TEXT PRIMARY KEY, actor TEXT NOT NULL, clave TEXT NOT NULL,
     operacion TEXT NOT NULL, mensaje TEXT NOT NULL,
     estado TEXT NOT NULL CHECK(estado IN ('pendiente','ejecutando','completada','fallida')),
     dispositivo TEXT, reserva TEXT, vence REAL, intentos INTEGER NOT NULL DEFAULT 0,
     resultado TEXT, creada REAL NOT NULL, iniciada REAL, UNIQUE(actor, clave));
CREATE TABLE telemetria (
      dispositivo TEXT PRIMARY KEY REFERENCES dispositivos(id), recibida REAL NOT NULL,
      datos TEXT NOT NULL CHECK(json_valid(datos)));
CREATE INDEX auditoria_fecha ON auditoria(fecha);
CREATE INDEX salida_propietario ON salida_eventos(propietario,secuencia);
CREATE UNIQUE INDEX tarea_unica_por_agente ON tareas(dispositivo) WHERE estado='ejecutando';
CREATE INDEX tareas_estado ON tareas(estado, creada);
CREATE INDEX tareas_reservas ON tareas(estado,vence);
CREATE VIEW resumen_cola AS SELECT estado,COUNT(*) AS cantidad,MIN(creada) AS mas_antigua FROM tareas GROUP BY estado;
CREATE TRIGGER tarea_terminal_inmutable BEFORE UPDATE OF estado ON tareas
      WHEN OLD.estado IN ('completada','fallida') AND NEW.estado<>OLD.estado
      BEGIN SELECT RAISE(ABORT, 'Una tarea terminal no vuelve a ejecutarse'); END;
INSERT INTO esquema VALUES('escolar',1);
INSERT INTO esquema VALUES('identidad',1);
INSERT INTO esquema VALUES('mensajeria',1);
INSERT INTO esquema VALUES('orquestacion',3);
INSERT INTO esquema VALUES('sistema',1);
COMMIT;
