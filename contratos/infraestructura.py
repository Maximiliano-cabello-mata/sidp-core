"""Contratos de infraestructura aditivos v1. Sin dependencias de red o persistencia."""
from typing import Literal
from pydantic import Field
from contratos.v1 import Contrato


class Telemetria(Contrato):
    cpu_porcentaje: float = Field(ge=0, le=100, allow_inf_nan=False)
    memoria_disponible_mb: int = Field(ge=0)
    disco_libre_mb: int = Field(ge=0)


class PoliticaNodo(Contrato):
    pausado: bool = False
    cpu_maxima: float = Field(default=85, ge=1, le=100, allow_inf_nan=False)
    memoria_minima_mb: int = Field(default=256, ge=0, le=1048576)
    disco_minimo_mb: int = Field(default=200, ge=0, le=1048576)


class CambiarPolitica(Contrato):
    revision_esperada: int = Field(ge=0)
    politica: PoliticaNodo


class Renovacion(Contrato):
    reserva: str = Field(min_length=1, max_length=64)


class Evento(Contrato):
    id: str
    secuencia: int = Field(gt=0)
    tipo: str
    correlacion: str
    propietario: str
    fecha: float
    datos: dict


class LoteEventos(Contrato):
    eventos: list[Evento]
    siguiente: int = Field(ge=0)


def motivo_bloqueo(telemetria: Telemetria, politica: PoliticaNodo):
    if politica.pausado:
        return 'pausado'
    if telemetria.cpu_porcentaje >= politica.cpu_maxima:
        return 'cpu'
    if telemetria.memoria_disponible_mb < politica.memoria_minima_mb:
        return 'memoria'
    if telemetria.disco_libre_mb < politica.disco_minimo_mb:
        return 'disco'
    return None
