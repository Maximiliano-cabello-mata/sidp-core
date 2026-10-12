"""Módulo orquestación: cola de tareas técnicas entre cerebro, operador y agentes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from backend.modulos import Modulo
from backend.modulos.orquestacion.almacen import MIGRACIONES, Almacen, Conflicto, Saturada
from backend.seguridad import requiere
from contratos.infraestructura import CambiarPolitica, Renovacion, Telemetria
from contratos.v1 import Dispositivo, NuevaTarea, Resultado

rutas = APIRouter(prefix="/api/v1", tags=["orquestación"])


def obtener_almacen(request: Request) -> Almacen:
    return request.app.state.almacen


def ejecutar(funcion, *args):
    try:
        return funcion(*args)
    except Saturada as error:
        raise HTTPException(429, str(error), headers={'Retry-After': '10'}) from error
    except Conflicto as error:
        raise HTTPException(409, str(error)) from error


@rutas.post("/dispositivos/registro")
def registrar(datos: Dispositivo, actor=Depends(requiere("agente")), cola=Depends(obtener_almacen)):
    cola.registrar(actor['id'], datos.capacidades, datos.protocolo_recursos)
    return {"id": actor['id'], "estado": "registrado"}


@rutas.post("/tareas")
def crear(datos: NuevaTarea, actor=Depends(requiere("admin", "cerebro")), cola=Depends(obtener_almacen)):
    return ejecutar(cola.crear, actor['id'], datos)


@rutas.get("/tareas")
def listar(actor=Depends(requiere("admin", "cerebro")), cola=Depends(obtener_almacen)):
    return cola.listar(actor)


@rutas.post("/tareas/reclamar")
def reclamar(actor=Depends(requiere("agente")), cola=Depends(obtener_almacen)):
    return ejecutar(cola.reclamar, actor['id'])


@rutas.post("/tareas/{identificador}/resultado")
def completar(identificador: str, datos: Resultado, actor=Depends(requiere("agente")), cola=Depends(obtener_almacen)):
    return ejecutar(cola.completar, actor['id'], identificador, datos)


@rutas.post('/dispositivos/latido')
def latido(datos: Telemetria, actor=Depends(requiere('agente')), cola=Depends(obtener_almacen)):
    return ejecutar(cola.latido, actor['id'], datos)


@rutas.get('/dispositivos/politica')
def politica(actor=Depends(requiere('agente')), cola=Depends(obtener_almacen)):
    return cola.politica_nodo(actor['id'])


@rutas.get('/dispositivos')
def dispositivos(actor=Depends(requiere('admin')), cola=Depends(obtener_almacen)):
    with cola.bd.conexion() as db:
        equipos = db.execute('SELECT id,ultimo,recursos FROM dispositivos ORDER BY id').fetchall()
        return [{**dict(equipo), **cola._politica(db, equipo['id'])} for equipo in equipos]


@rutas.get('/tareas/resumen')
def resumen(actor=Depends(requiere('admin')), cola=Depends(obtener_almacen)):
    with cola.bd.conexion() as db:
        return {'estados': [dict(f) for f in db.execute('SELECT * FROM resumen_cola')],
                'limites': cola.politica.model_dump()}


@rutas.put('/dispositivos/{dispositivo}/politica')
def configurar(dispositivo: str, datos: CambiarPolitica, actor=Depends(requiere('admin')), cola=Depends(obtener_almacen)):
    return ejecutar(cola.cambiar_politica, actor['id'], dispositivo, datos)


@rutas.post('/tareas/{identificador}/renovar')
def renovar(identificador: str, datos: Renovacion, actor=Depends(requiere('agente')), cola=Depends(obtener_almacen)):
    return ejecutar(cola.renovar, actor['id'], identificador, datos.reserva)


def iniciar(app, ctx):
    app.state.almacen = Almacen(ctx.bd)


MODULO = Modulo("orquestacion", "1.0", "Cola durable de tareas técnicas", MIGRACIONES, rutas,
                depende=("identidad", "mensajeria"), al_iniciar=iniciar)

