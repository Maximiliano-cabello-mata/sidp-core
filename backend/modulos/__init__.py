"""Contrato de módulo de plataforma y registro estático.

Los módulos se registran en código, no se descargan: el ejecutable contiene exactamente
lo que se probó. Ver docs/arquitectura/modulos.md.
"""
from dataclasses import dataclass, field
from typing import Callable
from fastapi import APIRouter


@dataclass(frozen=True)
class Modulo:
    nombre: str
    version: str
    descripcion: str
    migraciones: tuple = ()
    rutas: APIRouter | None = None
    depende: tuple = ()
    al_iniciar: Callable | None = field(default=None, compare=False)


def ordenar(modulos):
    """Valida nombres únicos y dependencias declaradas antes de arrancar."""
    vistos = set()
    for modulo in modulos:
        if modulo.nombre in vistos:
            raise RuntimeError(f"Módulo duplicado: {modulo.nombre}")
        faltantes = set(modulo.depende) - vistos
        if faltantes:
            raise RuntimeError(f"{modulo.nombre} requiere antes: {', '.join(sorted(faltantes))}")
        vistos.add(modulo.nombre)
    return list(modulos)


def registrados():
    # Importación tardía: cada módulo importa este paquete para declarar su Modulo.
    from backend.modulos import escolar, identidad, orquestacion, sistema
    return ordenar([sistema.MODULO, identidad.MODULO, orquestacion.MODULO, escolar.MODULO])
