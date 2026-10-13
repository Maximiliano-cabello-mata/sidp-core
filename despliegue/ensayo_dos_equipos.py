"""Ensayo con los ejecutables reales: varios equipos simulados en una máquina (3 por omisión).

    python despliegue/ensayo_dos_equipos.py dist/SIDP-Servidor.exe --estacion dist/SIDP-Equipo.exe
    python despliegue/ensayo_dos_equipos.py dist/sidp.exe          # un solo ejecutable, papel automático

Igual que en la escuela (ADR-025, ADR-029): PC1 abre el ejecutable del servidor y los demás
el de equipo, todos con la misma clave de escuela. Los equipos descubren el servidor por UDP,
reciben el certificado firmado y se unen aprobados, sin archivos ni invitaciones. Con dos
ejecutables se comprueba además que un segundo servidor con la misma clave se niega a crearse.
Luego `sidp prueba-conexion` debe pasar en todos, con la ida y vuelta desde
PC1 hacia cada estación y el reparto de tareas entre todos los equipos (ADR-026).
Sale con 0 si todo pasa. No sustituye la prueba en dos computadoras reales
(ver docs/PRUEBA_DOS_EQUIPOS.md), pero valida el binario antes de repartirlo.
"""
import argparse
import locale
import os
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
    return {**variables, 'SIDP_HOME': str(hogar)}


def correr(ejecutable, argumentos, hogar, tiempo=180):
    print(f'\n$ sidp {" ".join(argumentos)}   (SIDP_HOME={hogar.name})', flush=True)
    # El .exe ignora PYTHONIOENCODING: en una tubería escribe con la codificación local (cp1252 en Windows).
    resultado = subprocess.run([str(ejecutable), *argumentos], env=entorno(hogar), capture_output=True, text=True,
                               encoding=locale.getpreferredencoding(False), errors='replace', timeout=tiempo)
    print(resultado.stdout + resultado.stderr, flush=True)
    return resultado


def arrancar(ejecutable, hogar, argumentos):
    """Como el doble clic: el primer arranque configura el equipo y deja el nodo corriendo."""
    print(f'\n$ sidp {" ".join(argumentos)}   (SIDP_HOME={hogar.name}, en segundo plano)', flush=True)
    registro = open(hogar.parent / f'{hogar.name}-nodo.log', 'w', encoding='utf-8')
    return subprocess.Popen([str(ejecutable), *argumentos], env=entorno(hogar), stdout=registro,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


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


def esperar_archivo(ruta, limite=90):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if ruta.exists():
            return True
        time.sleep(0.5)
    return False


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
    for flujo in (sys.stdout, sys.stderr):
        flujo.reconfigure(errors='replace')  # Nunca abortar el ensayo por un carácter no imprimible.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('ejecutable', help='Ejecutable del servidor (o el único sidp.exe)')
    parser.add_argument('--estacion', help='Ejecutable de los equipos (por omisión, el mismo)')
    parser.add_argument('--equipos', type=int, default=3, help='Equipos simulados (mínimo 2)')
    parser.add_argument('--conservar', action='store_true', help='No borrar las carpetas de ensayo')
    args = parser.parse_args()
    ejecutable = Path(args.ejecutable).resolve()
    de_estacion = Path(args.estacion).resolve() if args.estacion else ejecutable
    base = Path(tempfile.mkdtemp(prefix='sidp-ensayo-'))
    equipos = [base / f'pc{numero}' for numero in range(1, max(args.equipos, 2) + 1)]
    servidor, estaciones = equipos[0], equipos[1:]
    puerto = puerto_libre()
    clave = 'ensayo escuela 2026'
    procesos, fallos, completo = [], [], False
    try:
        procesos.append(arrancar(ejecutable, servidor, ['iniciar', '--clave', clave, '--nombre', 'Ensayo',
                                                        '--puerto', str(puerto)]))
        if not esperar_puerto(puerto):
            raise SystemExit('PC1 no se volvió servidor (la plataforma no abrió su puerto)')
        for estacion in estaciones:
            procesos.append(arrancar(de_estacion, estacion, ['iniciar', '--clave', clave]))
            if not esperar_archivo(estacion / 'nodo.json'):
                raise SystemExit(f'{estacion.name} no se unió solo (descubrimiento o enrolamiento por clave)')
        time.sleep(5)  # Que los agentes arranquen y se registren en la plataforma.

        if de_estacion != ejecutable:  # Dos ejecutables: nunca dos servidores con la misma clave.
            try:
                segundo = correr(ejecutable, ['iniciar', '--clave', clave, '--puerto', str(puerto_libre())],
                                 base / 'pc-servidor-2', tiempo=120)
                negado = segundo.returncode != 0 and 'Ya hay un servidor' in segundo.stdout + segundo.stderr
            except subprocess.TimeoutExpired:  # Se quedó corriendo: se creó como servidor.
                negado = False
            if not negado:
                fallos.append('un segundo servidor con la misma clave no se negó a crearse')

        # Ida y vuelta con cada estación y reparto de trabajo entre todos los equipos.
        if correr(ejecutable, ['prueba-conexion', '--reparto', str(3 * len(equipos)), '--espera', '150'],
                  servidor, tiempo=600).returncode:
            fallos.append('prueba-conexion en PC1 (ida y vuelta y reparto)')
        for estacion in estaciones:
            if correr(de_estacion, ['prueba-conexion'], estacion).returncode:
                fallos.append(f'prueba-conexion en {estacion.name.upper()}')
        correr(ejecutable, ['equipos'], servidor)
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
    print(f'\nENSAYO: PASA - {len(equipos)} equipos unidos con la misma clave, conectados y repartiendo trabajo')
    return 0


if __name__ == '__main__':
    sys.exit(main())
