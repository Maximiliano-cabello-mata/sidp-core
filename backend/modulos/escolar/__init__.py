"""Módulo escolar (núcleo heredado): alumnos y ciclos escolares."""
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend.auditoria import anotar
from backend.contexto import contexto
from backend.modulos import Modulo
from backend.seguridad import administrador

# Mismo esquema que el prototipo SQLAlchemy, para poder importar datos de laboratorio.
MIGRACIONES = (
    """CREATE TABLE alumnos (
     id INTEGER PRIMARY KEY, curp VARCHAR(18) UNIQUE, nombre VARCHAR(100) NOT NULL,
     apellido_paterno VARCHAR(100) NOT NULL, apellido_materno VARCHAR(100), activo BOOLEAN NOT NULL DEFAULT 1);
    CREATE TABLE ciclos_escolares (
     id INTEGER PRIMARY KEY, nombre VARCHAR(50) NOT NULL UNIQUE, fecha_inicio DATE NOT NULL,
     fecha_fin DATE NOT NULL, activo BOOLEAN NOT NULL DEFAULT 1);""",
)


class AlumnoCrear(BaseModel):
    nombre: str = Field(..., max_length=100)
    apellido_paterno: str = Field(..., max_length=100)
    apellido_materno: Optional[str] = Field(None, max_length=100)
    curp: Optional[str] = Field(None, max_length=18)


class AlumnoRespuesta(AlumnoCrear):
    id: int
    activo: bool


rutas = APIRouter(tags=["escolar"], dependencies=[Depends(administrador)])


@rutas.post("/api/alumnos", response_model=AlumnoRespuesta)
def registrar_alumno(alumno: AlumnoCrear, actor=Depends(administrador), ctx=Depends(contexto)):
    """Registra un alumno; CURP duplicada se rechaza. Auditoría en la misma transacción."""
    try:
        with ctx.bd.transaccion() as db:
            cursor = db.execute("INSERT INTO alumnos(curp,nombre,apellido_paterno,apellido_materno) VALUES(?,?,?,?)",
                                (alumno.curp, alumno.nombre, alumno.apellido_paterno, alumno.apellido_materno))
            anotar(db, actor["id"], "alumno.registrado", cursor.lastrowid)
            fila = db.execute("SELECT * FROM alumnos WHERE id=?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as error:
        raise HTTPException(400, "Esta CURP ya está registrada en el sistema.") from error
    return dict(fila)


@rutas.get("/api/alumnos", response_model=list[AlumnoRespuesta])
def listar_alumnos(ctx=Depends(contexto)):
    with ctx.bd.conexion() as db:
        return [dict(f) for f in db.execute("SELECT * FROM alumnos WHERE activo=1 ORDER BY id")]


@rutas.get("/api/validar-curp/{curp}")
def verificar_curp(curp: str):
    raise HTTPException(501, "Validación documental fuera de alcance; conector existente es una simulación")


MODULO = Modulo("escolar", "0.1", "Alumnos y ciclos escolares", MIGRACIONES, rutas, depende=("sistema",))
