import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Importaciones del motor local, modelos y conectores
from backend.database import engine, Base, obtener_bd
from backend.api.orquestacion import router
from backend.seguridad import identidad, administrador
from backend import modelos
from backend import esquemas


# ==========================================
# CICLO DE VIDA DEL SISTEMA (ARRANQUE Y APAGADO)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Comprobando integridad de la base de datos local...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Base de datos local en línea y lista.")
    yield
    print("Cerrando el núcleo del SIDP y guardando estado...")

# ==========================================
# INICIALIZACIÓN DE LA PLATAFORMA
# ==========================================
app = FastAPI(
    title="SIDP - Plataforma",
    description="Motor principal para la gestión y supervivencia del Sistema Integral Delfino Pando",
    version="0.1.0",
    dependencies=[Depends(identidad)],
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("SIDP_ORIGINS", "http://localhost:8000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# RUTAS DE DIAGNÓSTICO Y SALUD
# ==========================================
@app.get("/api/salud")
async def estado_salud():
    """Latido del sistema y estado de supervivencia."""
    return JSONResponse(content={
        "estado": "vivo",
        "modo_supervivencia": "verde",
        "mensaje": "El núcleo de SIDP está operando correctamente."
    })

# ==========================================
# RUTAS DE INTEGRACIÓN OFICIAL (RENAPO)
# ==========================================
@app.get("/api/validar-curp/{curp}", dependencies=[Depends(administrador)])
async def verificar_curp(curp: str):
    """
    Consulta la CURP en RENAPO. Si está disponible, devuelve los datos
    para autocompletar el formulario de inscripción.
    """
    raise HTTPException(501, "Validación documental fuera de alcance; conector existente es una simulación")

# ==========================================
# RUTAS DE ALUMNOS (EXPEDIENTE)
# ==========================================
@app.post("/api/alumnos", response_model=esquemas.AlumnoRespuesta, dependencies=[Depends(administrador)])
async def registrar_alumno(alumno: esquemas.AlumnoCrear, db: AsyncSession = Depends(obtener_bd)):
    """Registra un alumno validando que la CURP no esté duplicada."""
    if alumno.curp:
        query = select(modelos.Alumno).where(modelos.Alumno.curp == alumno.curp)
        resultado = await db.execute(query)
        if resultado.scalars().first():
            raise HTTPException(status_code=400, detail="Esta CURP ya está registrada en el sistema.")
    
    nuevo_alumno = modelos.Alumno(**alumno.model_dump())
    
    db.add(nuevo_alumno)
    await db.commit()
    await db.refresh(nuevo_alumno)
    
    return nuevo_alumno

@app.get("/api/alumnos", response_model=list[esquemas.AlumnoRespuesta], dependencies=[Depends(administrador)])
async def listar_alumnos(db: AsyncSession = Depends(obtener_bd)):
    """Devuelve la lista de alumnos activos."""
    query = select(modelos.Alumno).where(modelos.Alumno.activo == True)
    resultado = await db.execute(query)
    return resultado.scalars().all()

# ==========================================
# SERVIDOR DE INTERFAZ (FRONTEND)
# ==========================================
app.include_router(router)

RUTA_ESTATICA = os.path.join(os.path.dirname(__file__), "static")

if os.path.exists(RUTA_ESTATICA) and os.listdir(RUTA_ESTATICA):
    app.mount("/", StaticFiles(directory=RUTA_ESTATICA, html=True), name="frontend")
else:
    @app.get("/")
    async def index_placeholder():
        return {"mensaje": "SIDP API activa. Interfaz gráfica no compilada aún."}

# ==========================================
# PUNTO DE ENTRADA PARA EL .EXE
# ==========================================
if __name__ == "__main__":
    print("Iniciando el Sistema Integral Delfino Pando...")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)
