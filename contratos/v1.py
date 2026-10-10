from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1


class Dispositivo(Contrato):
    capacidades: list[Literal["diagnostico.echo"]] = Field(min_length=1, max_length=1)


class NuevaTarea(Contrato):
    clave: str = Field(min_length=1, max_length=120)
    operacion: Literal["diagnostico.echo"] = "diagnostico.echo"
    mensaje: str = Field(default="SIDP operativo", max_length=500)


class Resultado(Contrato):
    reserva: str
    mensaje: str = Field(max_length=500)
