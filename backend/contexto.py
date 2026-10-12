"""Estado compartido de la plataforma en ejecución, sin variables globales."""
from dataclasses import dataclass
from fastapi import Request
from backend.base_datos import BaseDatos


@dataclass
class Contexto:
    bd: BaseDatos
    paquete: object | None
    modulos: list


def contexto(request: Request) -> Contexto:
    return request.app.state.contexto
