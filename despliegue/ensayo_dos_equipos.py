"""Ensayo con el ejecutable real: dos equipos simulados en una máquina.

    python despliegue/ensayo_dos_equipos.py dist/sidp.exe

PC1 crea la instalación y arranca plataforma + agente. PC2 recibe solo instalacion.json,
se une con una invitación (descubriendo al servidor por UDP) y arranca su agente.
Luego `sidp prueba-conexion` debe pasar en ambos, incluida la ida y vuelta PC1 -> PC2.
Sale con 0 si todo pasa. No sustituye la prueba en dos computadoras reales
(ver docs/PRUEBA_DOS_EQUIPOS.md), pero valida el binario antes de repartirlo.
"""
import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def entorno(hogar):
    variables = {k: v for k, v in os.environ.items() if not k.startswith('SIDP_')}
    return {**variables, 'SIDP_HOME': str(hogar), 'PYTHONIOENCODING': 'utf-8'}


def correr(ejecutable, argumentos, hogar, tiempo=180):
    print(f'\n$ sidp {" ".join(argumentos)}   (SIDP_HOME={hogar.name})', flush=True)
    resultado = subprocess.run([str(ejecutable), *argumentos], env=entorno(hogar), capture_output=True,
                               text=True, encoding='utf-8', errors='replace', timeout=tiempo)
    print(resultado.stdout + resultado.stderr, flush=True)
    return resultado


def arrancar(ejecutable, hogar):
    registro = open(hogar.parent / f'{hogar.name}-nodo.log', 'w', encoding='utf-8')
    return subprocess.Popen([str(ejecutable), 'iniciar'], env=entorno(hogar), stdout=registro, stderr=subprocess.STDOUT)


def detener(proceso):
    if proceso.poll() is not None:
        return
    if os.name == 'nt':  # terminate() en Windows no alcanza a los hijos del supervisor.
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proceso.pid)], capture_output=True)
    else:
        proceso.terminate()
    try:
        proceso.wait(15)
    except subprocess.TimeoutExpired:
        proceso.kill()


def esperar_puerto(puerto, limite=60):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        try:
            socket.create_connection(('127.0.0.1', puerto), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    for flujo in (sys.stdout, sys.stderr):  # La consola de Windows en CI usa cp1252.
        flujo.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('ejecutable')
    parser.add_argument('--conservar', action='store_true', help='No borrar las carpetas de ensayo')
    args = parser.parse_args()
    ejecutable = Path(args.ejecutable).resolve()
    base = Path(tempfile.mkdtemp(prefix='sidp-ensayo-'))
    pc1, pc2 = base / 'pc1', base / 'pc2'
    puerto = puerto_libre()
    procesos, fallos, completo = [], [], False
    try:
        if correr(ejecutable, ['crear-instalacion', '--nombre', 'Ensayo dos equipos', '--equipo', 'pc1',
                               '--puerto', str(puerto)], pc1).returncode:
            raise SystemExit('No se pudo crear la instalación')
        procesos.append(arrancar(ejecutable, pc1))
        if not esperar_puerto(puerto):
            raise SystemExit('La plataforma de PC1 no abrió su puerto')

        salida = correr(ejecutable, ['invitacion', '--rol', 'agente'], pc1).stdout
        codigo = re.search(r'([0-9A-F]{4}(?:-[0-9A-F]{4}){3})', salida)
        if not codigo:
            raise SystemExit('No se obtuvo código de invitación')
        pc2.mkdir(parents=True)
        shutil.copy(pc1 / 'instalacion.json', pc2 / 'instalacion.json')  # Lo único que viaja a PC2.
        if correr(ejecutable, ['unirse', '--equipo', 'pc2', '--invitacion', codigo.group(1)], pc2).returncode:
            raise SystemExit('PC2 no pudo unirse (descubrimiento o enrolamiento)')
        procesos.append(arrancar(ejecutable, pc2))

        if correr(ejecutable, ['prueba-conexion', '--equipo', 'pc2-agente'], pc1).returncode:
            fallos.append('prueba-conexion en PC1 (ida y vuelta hacia PC2)')
        if correr(ejecutable, ['prueba-conexion'], pc2).returncode:
            fallos.append('prueba-conexion en PC2')
        completo = True
    finally:
        for proceso in reversed(procesos):
            detener(proceso)
        if fallos or not completo:
            for archivo in sorted(base.glob('*-nodo.log')) + sorted(base.glob('*/registros/*.log')):
                print(f'\n----- {archivo.relative_to(base)} -----\n{archivo.read_text(encoding="utf-8", errors="replace")[-4000:]}')
        if not args.conservar:
            shutil.rmtree(base, ignore_errors=True)
    if fallos:
        print('\nENSAYO: FALLA -> ' + '; '.join(fallos))
        return 1
    print('\nENSAYO: PASA - dos equipos conectados, autorizados y sincronizados por la plataforma')
    return 0


if __name__ == '__main__':
    sys.exit(main())
