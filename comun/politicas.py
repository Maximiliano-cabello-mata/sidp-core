"""Parámetros acotados de transporte y cola. Sobrescritura local por entorno."""
import os
import random
from pydantic import BaseModel, ConfigDict, Field


class Transporte(BaseModel):
    model_config = ConfigDict(extra='forbid')
    conexion_s: float = Field(default=3, gt=0, le=30)
    lectura_s: float = Field(default=10, gt=0, le=60)
    conexiones: int = Field(default=4, ge=1, le=16)
    espera_minima_s: float = Field(default=2, ge=0.5, le=10)
    espera_maxima_s: float = Field(default=30, ge=10, le=60)

    @classmethod
    def cargar(cls):
        return cls.model_validate_json(os.environ.get('SIDP_TRANSPORTE', '{}'))


class Cola(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pendientes_maximos: int = Field(default=1000, ge=1, le=10000)
    ejecuciones_maximas: int = Field(default=2, ge=1, le=16)
    reserva_s: int = Field(default=60, ge=10, le=300)
    duracion_maxima_s: int = Field(default=600, ge=300, le=3600)
    telemetria_vigente_s: int = Field(default=90, ge=30, le=600)

    @classmethod
    def cargar(cls):
        return cls.model_validate_json(os.environ.get('SIDP_COLA', '{}'))


def espera_reintento(fallos, politica=None):
    """Backoff exponencial con jitter; siempre acotado, sin bucle de red inmediato."""
    politica = politica or Transporte.cargar()
    techo = min(politica.espera_maxima_s, politica.espera_minima_s * 2 ** min(max(fallos, 0), 16))
    return random.uniform(politica.espera_minima_s / 2, techo)
