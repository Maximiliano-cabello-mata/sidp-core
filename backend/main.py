import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Importaciones del motor local de la base de datos (SQLite)
from database import engine, Base

# ==========================================
# CICLO DE VIDA DEL SISTEMA (ARRANQUE Y APAGADO)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Esto se ejecuta justo antes de que el servidor empiece a recibir tráfico
    print("Comprobando integridad de la base de datos local...")
    async with engine.begin() as conn:
        # Crea el archivo sidp_nodo_local.db y las tablas si no existen
        await conn.run_sync(Base.metadata.create_all)
    print("Base de datos local en línea y lista.")
    
    yield # Aquí el sistema está corriendo normalmente y recibiendo peticiones
    
    # Esto se ejecuta cuando se cierra el sistema (Ej. Ctrl+C)
    print("Cerrando el núcleo del SIDP y guardando estado...")

# ==========================================
# INICIALIZACIÓN DEL CEREBRO
# ==========================================
app = FastAPI(
    title="SIDP - API Interna y Cerebro",
    description="Motor principal para la gestión y supervivencia del Sistema Integral Delfino Pando",
    version="0.1.0",
    lifespan=lifespan # Conectamos el ciclo de vida que acabamos de crear
)

# Configuramos CORS (permite que el frontend hable con el backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En el .exe esto se restringe a localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# RUTAS DE LA API INTERNA (MÓDULOS)
# ==========================================

@app.get("/api/salud")
async def estado_salud():
    """
    Este es el latido del sistema. El frontend y los nodos lo consultarán
    para saber si el Cerebro está vivo y en qué modo de supervivencia opera.
    """
    return JSONResponse(content={
        "estado": "vivo",
        "modo_supervivencia": "verde", # Verde, Amarillo, Naranja, Rojo
        "mensaje": "El núcleo de SIDP está operando correctamente."
    })

# Aquí iremos conectando las rutas de /api/expedientes, /api/inscripciones, etc.

# ==========================================
# SERVIDOR DE INTERFAZ (FRONTEND)
# ==========================================
# Montamos la carpeta estática. Cuando el .exe esté listo, el frontend de React
# vivirá aquí y el propio Python lo mostrará sin necesitar un servidor web extra.

RUTA_ESTATICA = os.path.join(os.path.dirname(__file__), "static")

# Solo montamos la ruta estática si la carpeta tiene contenido
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
    # Al empaquetar, este bloque es el que ejecutará el programa al hacer doble clic
    print("Iniciando el Sistema Integral Delfino Pando...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)