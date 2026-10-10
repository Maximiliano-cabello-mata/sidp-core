from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class AlumnoBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    apellido_paterno: str = Field(..., max_length=100)
    apellido_materno: Optional[str] = Field(None, max_length=100)
    curp: Optional[str] = Field(None, max_length=18)

class AlumnoCrear(AlumnoBase):
    pass

class AlumnoRespuesta(AlumnoBase):
    id: int
    activo: bool

    model_config = ConfigDict(from_attributes=True)
