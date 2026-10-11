"""Módulo orquestación: cola de tareas técnicas entre cerebro, operador y agentes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from backend.modulos import Modulo
from backend.modulos.orquestacion.almacen import MIGRACIONES, Almacen, Conflicto
from backend.seguridad import requiere
from contratos.v1 import Dispositivo, NuevaTarea, Resultado

rutas = APIRouter(prefix="/api/v1", tags=["orquestación"])


def almacen(request: Request) -> Almacen:
    return request.app.state.almacen


def ejecutar(funcion, *args):
    try:
        return funcion(*args)
    except Conflicto as error:
        raise HTTPException(409, str(error)) from error


@rutas.post("/dispositivos/registro")
def registrar(datos: Dispositivo, actor=Depends(requiere("agente")), cola=Depends(almacen)):
    cola.registrar(actor['id'], datos.capacidades)
    return {"id": actor['id'], "estado": "registrado"}


@rutas.post("/tareas")
def crear(datos: NuevaTarea, actor=Depends(requiere("admin", "cerebro")), cola=Depends(almacen)):
    return ejecutar(cola.crear, actor['id'], datos)


@rutas.get("/tareas")
def listar(actor=Depends(requiere("admin", "cerebro")), cola=Depends(almacen)):
    return cola.listar(actor)


@rutas.post("/tareas/reclamar")
def reclamar(actor=Depends(requiere("agente")), cola=Depends(almacen)):
    return ejecutar(cola.reclamar, actor['id'])


@rutas.post("/tareas/{identificador}/resultado")
def completar(identificador: str, datos: Resultado, actor=Depends(requiere("agente")), cola=Depends(almacen)):
    return ejecutar(cola.completar, actor['id'], identificador, datos)


def iniciar(app, ctx):
    app.state.almacen = Almacen(ctx.bd)


MODULO = Modulo("orquestacion", "1.0", "Cola durable de tareas técnicas", MIGRACIONES, rutas,
                depende=("identidad",), al_iniciar=iniciar)
