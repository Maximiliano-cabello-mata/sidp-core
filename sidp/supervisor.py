"""Supervisor del nodo: un proceso hijo por rol, reinicio con espera creciente.

Procesos separados conservan el aislamiento (credencial, memoria y fallos por rol)
sin depender de servicios del sistema operativo.
"""
import logging
import signal
import subprocess
import sys
import time
from comun import rutas

registro = logging.getLogger('sidp.supervisor')
ESPERA_MAXIMA = 60
ESTABLE = 300


def comando(rol):
    if rol not in ('plataforma', 'agente', 'cerebro'):
        raise ValueError('Rol de proceso desconocido')
    argumentos = [rol, '--servicio'] if rol == 'cerebro' else [rol]
    if rutas.congelado():
        return [sys.executable, *argumentos]
    return [sys.executable, '-m', 'sidp', *argumentos]


class Proceso:
    def __init__(self, rol):
        self.rol, self.hijo, self.espera, self.proximo, self.inicio = rol, None, 1, 0.0, 0.0

    def revisar(self, ahora):
        if self.hijo and self.hijo.poll() is not None:
            codigo = self.hijo.returncode
            if ahora - self.inicio > ESTABLE:
                self.espera = 1
            else:
                self.espera = min(self.espera * 2, ESPERA_MAXIMA)
            if codigo == 3:  # Error de configuración o credencial: no insistir rápido.
                self.espera = ESPERA_MAXIMA
            registro.warning('%s terminó (código %s); reinicio en %ss', self.rol, codigo, self.espera)
            self.hijo, self.proximo = None, ahora + self.espera
        if not self.hijo and ahora >= self.proximo:
            registro.info('Iniciando %s', self.rol)
            self.hijo, self.inicio = subprocess.Popen(comando(self.rol)), ahora

    def detener(self):
        if self.hijo and self.hijo.poll() is None:
            self.hijo.terminate()
            try:
                self.hijo.wait(10)
            except subprocess.TimeoutExpired:
                self.hijo.kill()


def _terminar(*_):
    raise KeyboardInterrupt


def supervisar(roles):
    # La plataforma arranca primero; los demás reintentan solos hasta encontrarla.
    procesos = [Proceso(rol) for rol in sorted(roles, key=lambda r: r != 'plataforma')]
    signal.signal(signal.SIGTERM, _terminar)  # Apagado ordenado también desde el sistema operativo.
    registro.info('Nodo en marcha con roles: %s', ', '.join(roles))
    try:
        while True:
            for proceso in procesos:
                proceso.revisar(time.monotonic())
            time.sleep(1)
    except KeyboardInterrupt:
        registro.info('Deteniendo nodo')
    finally:
        for proceso in reversed(procesos):
            proceso.detener()

