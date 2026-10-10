import os
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from backend.seguridad import identidad, permitir
from backend.tareas import Almacen, Conflicto
from contratos.v1 import Dispositivo, NuevaTarea, Resultado

router = APIRouter(prefix="/api/v1", tags=["orquestación"])


@lru_cache
def almacen():
    return Almacen(Path(os.environ.get("SIDP_DATA_DIR", "datos")) / "orquestacion.db")


def ejecutar(funcion, *args):
    try:
        return funcion(*args)
    except Conflicto as error:
        raise HTTPException(409, str(error)) from error


@router.post("/dispositivos/registro")
def registrar(datos: Dispositivo, actor=Depends(identidad)):
    permitir(actor, "agente")
    almacen().registrar(actor['id'], datos.capacidades)
    return {"id": actor['id'], "estado": "registrado"}


@router.post("/tareas")
def crear(datos: NuevaTarea, actor=Depends(identidad)):
    permitir(actor, "admin", "cerebro")
    return ejecutar(almacen().crear, actor['id'], datos)


@router.get("/tareas")
def listar(actor=Depends(identidad)):
    permitir(actor, "admin", "cerebro")
    return almacen().listar(actor)


@router.post("/tareas/reclamar")
def reclamar(actor=Depends(identidad)):
    permitir(actor, "agente")
    return ejecutar(almacen().reclamar, actor['id'])


@router.post("/tareas/{identificador}/resultado")
def completar(identificador: str, datos: Resultado, actor=Depends(identidad)):
    permitir(actor, "agente")
    return ejecutar(almacen().completar, actor['id'], identificador, datos)
