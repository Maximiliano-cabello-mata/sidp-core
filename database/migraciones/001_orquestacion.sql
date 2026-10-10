CREATE TABLE IF NOT EXISTS dispositivos (
 id TEXT PRIMARY KEY, capacidades TEXT NOT NULL, ultimo REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tareas (
 id TEXT PRIMARY KEY, actor TEXT NOT NULL, clave TEXT NOT NULL,
 operacion TEXT NOT NULL, mensaje TEXT NOT NULL,
 estado TEXT NOT NULL CHECK(estado IN ('pendiente','ejecutando','completada','fallida')),
 dispositivo TEXT, reserva TEXT, vence REAL, intentos INTEGER NOT NULL DEFAULT 0,
 resultado TEXT, creada REAL NOT NULL, UNIQUE(actor, clave)
);
CREATE TABLE IF NOT EXISTS eventos (
 secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
 tipo TEXT NOT NULL, tarea TEXT NOT NULL, actor TEXT NOT NULL, fecha REAL NOT NULL
);
