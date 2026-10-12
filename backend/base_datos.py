"""Una base SQLite por instalación, en modo WAL, con migraciones por módulo.

Cada módulo es dueño de sus tablas y de su lista ordenada de migraciones. Al compartir
archivo, un cambio escolar y su registro de auditoría caben en la misma transacción.
Las migraciones viven en código (no en archivos .sql) para que el ejecutable las incluya.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class BaseDatos:
    def __init__(self, ruta, modulos=()):
        self.ruta = str(ruta)
        Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        with self.conexion() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS esquema(modulo TEXT PRIMARY KEY, version INTEGER NOT NULL)")
            self._adoptar_legado(db)
        for modulo in modulos:
            self.migrar(modulo.nombre, modulo.migraciones)

    @contextmanager
    def conexion(self):
        db = sqlite3.connect(self.ruta, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")  # Confirmado significa escrito en disco.
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaccion(self):
        """Transacción de escritura corta; BEGIN IMMEDIATE evita bloqueos a mitad de camino."""
        with self.conexion() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    def version(self, modulo):
        with self.conexion() as db:
            fila = db.execute("SELECT version FROM esquema WHERE modulo=?", (modulo,)).fetchone()
            return fila[0] if fila else 0

    def migrar(self, modulo, migraciones):
        # Leer versión DENTRO del bloqueo: CLI y servidor pueden arrancar a la vez.
        with self.transaccion() as db:
            fila = db.execute('SELECT version FROM esquema WHERE modulo=?', (modulo,)).fetchone()
            actual = fila[0] if fila else 0
            if actual > len(migraciones):
                raise RuntimeError(f"Base de {modulo} (v{actual}) más nueva que esta aplicación (v{len(migraciones)})")
            for numero, sql in enumerate(migraciones[actual:], start=actual + 1):
                sentencia = ''
                for caracter in sql:
                    sentencia += caracter
                    if caracter == ';' and sqlite3.complete_statement(sentencia):
                        db.execute(sentencia)
                        sentencia = ''
                if sentencia.strip():
                    raise ValueError('Migración incompleta: terminar cada sentencia con punto y coma')
                db.execute('INSERT INTO esquema VALUES(?,?) ON CONFLICT(modulo) DO UPDATE SET version=excluded.version',
                           (modulo, numero))

    @staticmethod
    def _adoptar_legado(db):
        # La cola de laboratorio marcaba su esquema con user_version=1.
        if db.execute("PRAGMA user_version").fetchone()[0] == 1 and db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='tareas'").fetchone():
            db.execute("INSERT OR IGNORE INTO esquema VALUES('orquestacion',1)")

