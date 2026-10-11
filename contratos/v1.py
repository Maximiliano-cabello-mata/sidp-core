"""Contratos públicos v1. Campos adicionales y versiones desconocidas se rechazan."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

# Catálogo cerrado de capacidades. Agregar una capacidad es un cambio de contrato.
Capacidad = Literal["diagnostico.echo"]
Rol = Literal["agente", "cerebro"]
NOMBRE = r"^[a-z0-9][a-z0-9-]{0,39}$"


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1


class Dispositivo(Contrato):
    protocolo_recursos: bool = False
    capacidades: list[Capacidad] = Field(min_length=1, max_length=16)


class NuevaTarea(Contrato):
    clave: str = Field(min_length=1, max_length=120)
    operacion: Capacidad = "diagnostico.echo"
    mensaje: str = Field(default="SIDP operativo", max_length=500)


class Resultado(Contrato):
    reserva: str
    mensaje: str = Field(max_length=500)


class SolicitudIngreso(Contrato):
    """Un proceso pide identidad. La prueba HMAC demuestra que tiene el paquete de instalación."""
    instalacion: str = Field(max_length=64)
    equipo: str = Field(pattern=NOMBRE)
    rol: Rol
    token_resumen: str = Field(pattern=r"^[0-9a-f]{64}$")
    sello: int
    invitacion: str | None = Field(default=None, max_length=64)
    prueba: str = Field(pattern=r"^[0-9a-f]{64}$")

    def firmable(self):
        return self.model_dump(exclude={"prueba"})


class NuevaInvitacion(Contrato):
    rol: Rol = "agente"
    horas: int = Field(default=24, ge=1, le=168)

