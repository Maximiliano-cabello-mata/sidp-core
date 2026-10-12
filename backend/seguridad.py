"""Autenticación de identidades técnicas.

Fuentes: identidades enroladas en la base (producción) y SIDP_IDENTIDADES (laboratorio
y pruebas). Sin ninguna identidad configurada el acceso queda cerrado (503).
No sustituye el futuro login del personal escolar.
"""
import json
import os
import secrets
import time
from fastapi import Depends, Header, HTTPException, Request
from comun.firma import resumen_token


def _token(authorization):
    return authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""


def _laboratorio():
    return json.loads(os.environ.get("SIDP_IDENTIDADES", "{}"))


def buscar(bd, token):
    """Fila de identidad para el token (en cualquier estado) o None."""
    with bd.conexion() as db:
        return db.execute("SELECT * FROM identidades WHERE token_resumen=?", (resumen_token(token),)).fetchone()


def identidad(request: Request, authorization: str = Header(default="")):
    token = _token(authorization)
    laboratorio = _laboratorio()
    for nombre, datos in laboratorio.items():
        esperado = datos.get("token", "")
        if esperado and token and secrets.compare_digest(token, esperado):
            return {"id": nombre, "rol": datos["rol"], "equipo": nombre}
    bd = request.app.state.contexto.bd
    fila = buscar(bd, token) if token else None
    if fila and fila["estado"] == "aprobada":
        ahora = time.time()
        if not fila["ultimo"] or fila["ultimo"] < ahora - 60:  # Latido sin escribir en cada petición.
            with bd.conexion() as db:
                db.execute("UPDATE identidades SET ultimo=? WHERE id=?", (ahora, fila["id"]))
        return {"id": fila["id"], "rol": fila["rol"], "equipo": fila["equipo"]}
    if not laboratorio:
        with bd.conexion() as db:
            if not db.execute("SELECT 1 FROM identidades WHERE estado='aprobada' LIMIT 1").fetchone():
                raise HTTPException(503, "Sin identidades configuradas; acceso cerrado por defecto")
    raise HTTPException(401, "Credencial inválida, pendiente o revocada")


def permitir(actor, *roles):
    if actor["rol"] not in roles:
        raise HTTPException(403, "Operación no autorizada")


def requiere(*roles):
    def dependencia(actor=Depends(identidad)):
        permitir(actor, *roles)
        return actor
    return dependencia


administrador = requiere("admin")
