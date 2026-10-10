"""Identidades técnicas de laboratorio. No sustituye el futuro login escolar."""
import json
import os
import secrets
from fastapi import Depends
from fastapi import Header, HTTPException


def identidad(authorization: str = Header(default="")):
    configuracion = json.loads(os.environ.get("SIDP_IDENTIDADES", "{}"))
    if not configuracion:
        raise HTTPException(503, "Configure SIDP_IDENTIDADES; acceso cerrado por defecto")
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    for nombre, datos in configuracion.items():
        esperado = datos.get("token", "")
        if esperado and token and secrets.compare_digest(token, esperado):
            return {"id": nombre, "rol": datos["rol"]}
    raise HTTPException(401, "Credencial inválida")


def permitir(actor, *roles):
    if actor["rol"] not in roles:
        raise HTTPException(403, "Operación no autorizada")


def administrador(actor=Depends(identidad)):
    permitir(actor, "admin")
    return actor
