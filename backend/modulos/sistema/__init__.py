"""Módulo sistema: salud, información de la instalación y bitácora común."""
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from backend import VERSION
from backend.contexto import contexto
from backend.modulos import Modulo
from backend.seguridad import administrador, identidad

MIGRACIONES = (
    """CREATE TABLE auditoria (
     secuencia INTEGER PRIMARY KEY AUTOINCREMENT, fecha REAL NOT NULL, actor TEXT NOT NULL,
     accion TEXT NOT NULL, objeto TEXT NOT NULL, detalle TEXT);
    CREATE INDEX auditoria_fecha ON auditoria(fecha);""",
)
DISCO_MINIMO = 200 * 1024 * 1024

rutas = APIRouter(tags=["sistema"])


@rutas.get("/api/v1/sistema/latido")
def latido():
    """Público y sin datos: permite verificar que la URL corresponde a una plataforma SIDP."""
    return {"sidp": True, "estado": "vivo"}


@rutas.get("/api/salud", dependencies=[Depends(identidad)])
def salud(ctx=Depends(contexto)):
    """Comprueba base y disco reales; un fallo no se informa como éxito."""
    libre = shutil.disk_usage(Path(ctx.bd.ruta).parent).free
    try:
        with ctx.bd.conexion() as db:
            db.execute("SELECT 1").fetchone()
    except Exception as error:
        raise HTTPException(503, f"Base de datos no disponible: {error}") from error
    estado = "verde" if libre >= DISCO_MINIMO else "amarillo"
    return {"estado": "vivo", "modo_supervivencia": estado, "disco_libre_mb": libre // 2**20,
            "mensaje": "Plataforma operando" if estado == "verde" else "Espacio en disco bajo"}


@rutas.get("/api/v1/sistema", dependencies=[Depends(administrador)])
def informacion(ctx=Depends(contexto)):
    return {"version": VERSION,
            "instalacion": ctx.paquete.nombre if ctx.paquete else None,
            "modo": "instalacion" if ctx.paquete else "laboratorio",
            "modulos": [{"nombre": m.nombre, "version": m.version, "esquema": ctx.bd.version(m.nombre)}
                        for m in ctx.modulos]}


MODULO = Modulo("sistema", "1.0", "Salud, información y auditoría", MIGRACIONES, rutas)
