"""Admisión cooperativa: medir antes de aceptar trabajo, no limitar el SO."""
import shutil
import psutil
from contratos.infraestructura import Telemetria


def medir(directorio):
    return Telemetria(cpu_porcentaje=psutil.cpu_percent(interval=0.1),
                      memoria_disponible_mb=psutil.virtual_memory().available // 2**20,
                      disco_libre_mb=shutil.disk_usage(directorio).free // 2**20)
