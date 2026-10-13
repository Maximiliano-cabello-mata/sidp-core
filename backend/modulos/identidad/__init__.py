"""Módulo identidad: alta de equipos (enrolamiento), aprobación y revocación."""
from dataclasses import asdict
from fastapi import APIRouter, Depends, Header, HTTPException
from backend.contexto import contexto
from backend.modulos import Modulo
from backend.modulos.identidad import servicio
from backend.seguridad import administrador, buscar
from comun import firma
from contratos.v1 import NuevaInvitacion, SolicitudIngreso

MIGRACIONES = (
    """CREATE TABLE identidades (
     id TEXT PRIMARY KEY, equipo TEXT NOT NULL,
     rol TEXT NOT NULL CHECK(rol IN ('admin','cerebro','agente')),
     token_resumen TEXT NOT NULL UNIQUE,
     estado TEXT NOT NULL CHECK(estado IN ('pendiente','aprobada','revocada')),
     origen TEXT NOT NULL, creada REAL NOT NULL, aprobada REAL, ultimo REAL);
    CREATE TABLE invitaciones (
     codigo_resumen TEXT PRIMARY KEY, rol TEXT NOT NULL, creada REAL NOT NULL, vence REAL NOT NULL,
     actor TEXT NOT NULL, usada REAL, identidad TEXT);""",
)

rutas = APIRouter(prefix="/api/v1", tags=["identidad"])


def ejecutar(funcion, *args):
    try:
        return funcion(*args)
    except servicio.Rechazo as error:
        raise HTTPException(error.codigo, str(error)) from error


@rutas.post("/enrolamiento/solicitud")
def solicitar(datos: SolicitudIngreso, ctx=Depends(contexto)):
    """Público: la autenticidad la da la prueba HMAC del paquete de instalación."""
    return ejecutar(servicio.solicitar, ctx.bd, ctx.paquete, datos)


@rutas.get("/enrolamiento/paquete")
def paquete_publico(ctx=Depends(contexto)):
    """Instalación por clave (ADR-025): datos públicos del paquete, sin el secreto, firmados con él.

    El equipo nuevo, que derivó el secreto de la clave de escuela, comprueba la firma y así
    confía en el certificado sin haber recibido instalacion.json.
    """
    if not ctx.paquete or not getattr(ctx.paquete, "por_clave", False):
        raise HTTPException(404, "Instalación sin clave de escuela: use instalacion.json o una invitación")
    datos = {k: v for k, v in asdict(ctx.paquete).items() if k not in ("secreto", "url")}
    return {**datos, "prueba": firma.firmar(ctx.paquete.secreto, datos)}


@rutas.get("/enrolamiento/estado")
def estado(authorization: str = Header(default=""), ctx=Depends(contexto)):
    """Un equipo pendiente consulta si ya fue aprobado usando su propio token."""
    fila = buscar(ctx.bd, authorization.removeprefix("Bearer ")) if authorization.startswith("Bearer ") else None
    if not fila:
        raise HTTPException(401, "Token desconocido")
    return {"id": fila["id"], "estado": fila["estado"]}


@rutas.get("/identidades", dependencies=[Depends(administrador)])
def listar(ctx=Depends(contexto)):
    return servicio.listar(ctx.bd)


@rutas.post("/identidades/{identificador}/aprobar")
def aprobar(identificador: str, actor=Depends(administrador), ctx=Depends(contexto)):
    return ejecutar(servicio.cambiar, ctx.bd, identificador, "aprobada", actor["id"])


@rutas.post("/identidades/{identificador}/revocar")
def revocar(identificador: str, actor=Depends(administrador), ctx=Depends(contexto)):
    return ejecutar(servicio.cambiar, ctx.bd, identificador, "revocada", actor["id"])


@rutas.post("/invitaciones")
def invitar(datos: NuevaInvitacion, actor=Depends(administrador), ctx=Depends(contexto)):
    return servicio.invitar(ctx.bd, datos.rol, datos.horas, actor["id"])


MODULO = Modulo("identidad", "1.0", "Enrolamiento y permisos de equipos", MIGRACIONES, rutas, depende=("sistema",))
