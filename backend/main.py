"""Composición de la plataforma a partir de los módulos registrados.

Laboratorio: python -m uvicorn backend.main:app (identidades por SIDP_IDENTIDADES).
Instalación: sidp plataforma (TLS, descubrimiento y enrolamiento).
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend import VERSION
from backend.base_datos import BaseDatos
from backend.contexto import Contexto
from backend.modulos import registrados
from comun import configuracion, rutas

registro = logging.getLogger("sidp.plataforma")
RUTA_ESTATICA = Path(__file__).parent / "static"


def preparar(directorio=None, paquete=None, modulos=None):
    """Abre la base y aplica migraciones de todos los módulos. Sin servidor HTTP."""
    modulos = modulos or registrados()
    directorio = Path(directorio) if directorio else rutas.datos_plataforma()
    bd = BaseDatos(directorio / "plataforma.db", modulos)
    return Contexto(bd=bd, paquete=paquete, modulos=modulos)


def crear_app(modulos=None):
    modulos = modulos or registrados()

    @asynccontextmanager
    async def ciclo_de_vida(app):
        ctx = preparar(paquete=configuracion.cargar_paquete(), modulos=modulos)
        app.state.contexto = ctx
        for modulo in modulos:
            if modulo.al_iniciar:
                modulo.al_iniciar(app, ctx)
        registro.info("Plataforma lista: %s, módulos %s", ctx.bd.ruta, [m.nombre for m in modulos])
        yield
        registro.info("Plataforma detenida")

    app = FastAPI(title="SIDP - Plataforma", version=VERSION, lifespan=ciclo_de_vida,
                  description="Sistema Integral Delfino Pando: autoridad de datos y permisos")
    app.add_middleware(CORSMiddleware, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                       allow_origins=os.environ.get("SIDP_ORIGINS", "http://localhost:8000").split(","))
    for modulo in modulos:
        if modulo.rutas:
            app.include_router(modulo.rutas)

    if RUTA_ESTATICA.exists() and any(p.name != ".gitkeep" for p in RUTA_ESTATICA.iterdir()):
        app.mount("/", StaticFiles(directory=RUTA_ESTATICA, html=True), name="interfaz")
    else:
        @app.get("/")
        def inicio():
            return {"mensaje": "SIDP API activa. Interfaz gráfica no compilada aún."}
    return app


app = crear_app()
