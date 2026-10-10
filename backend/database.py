import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# ==========================================
# CONFIGURACIÓN DE LA BASE DE DATOS LOCAL
# ==========================================
# La base de datos vivirá en la misma carpeta que este código (y el futuro .exe).
BASE_DIR = os.environ.get("SIDP_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "sidp_nodo_local.db")

# Cadena de conexión para SQLite asíncrono
SQLALCHEMY_DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# El "Engine" mantiene la conexión viva con el archivo .db
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, 
    echo=False, # Imprime las consultas en la terminal para facilitar el diagnóstico
    connect_args={"check_same_thread": False} 
)

# Generador de sesiones
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para definir las tablas (expedientes, alumnos, etc.)
Base = declarative_base()

# ==========================================
# INYECCIÓN DE DEPENDENCIA PARA FASTAPI
# ==========================================
async def obtener_bd():
    """
    Entrega una sesión de base de datos a las rutas de FastAPI
    y se asegura de cerrarla pase lo que pase.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()
