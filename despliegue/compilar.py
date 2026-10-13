"""Genera los ejecutables de SIDP con PyInstaller.

    python despliegue/compilar.py --tipo servidor         # SIDP-Servidor.exe (ADR-029)
    python despliegue/compilar.py --tipo equipo           # SIDP-Equipo.exe
    python despliegue/compilar.py                         # sidp.exe genérico (papel automático)
    python despliegue/compilar.py --paquete C:\\ProgramData\\SIDP\\instalacion.json

Los tres contienen el mismo programa y aceptan las mismas órdenes; solo cambia qué hace
el doble clic la primera vez. Cada uno lleva incrustadas la fecha y la versión de
compilación, que muestra al abrirse.

Con --paquete el ejecutable queda preconfigurado para esa escuela: al abrirlo en un
equipo nuevo busca la plataforma, solicita autorización y arranca solo. Ese ejecutable
contiene el secreto de la instalación: distribuirlo solo dentro de la escuela y nunca
subirlo a Git ni a CI. PyInstaller no compila de forma cruzada: el .exe se genera en Windows.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# Módulos que uvicorn carga por nombre y PyInstaller no descubre solo.
OCULTOS = ['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.auto',
           'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on']
# Lo que nunca se usa: reduce tamaño y tiempo de arranque.
EXCLUIDOS = ['tkinter', 'unittest', 'pydoc', 'test', 'pytest', 'sqlalchemy', 'aiosqlite', 'IPython']


TIPOS = {  # tipo: (nombre del ejecutable, punto de entrada)
    'servidor': ('SIDP-Servidor', 'entrada_servidor.py'),
    'equipo': ('SIDP-Equipo', 'entrada_equipo.py'),
    'generico': ('sidp', '__main__.py'),
}


def version_git():
    try:
        salida = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=RAIZ, capture_output=True, text=True)
        return salida.stdout.strip() or 'sin git'
    except OSError:
        return 'sin git'


def validar_paquete(ruta):
    datos = json.loads(Path(ruta).read_text(encoding='utf-8'))
    faltantes = {'instalacion', 'nombre', 'secreto'} - set(datos)
    if faltantes:
        raise SystemExit(f'Paquete incompleto, faltan: {", ".join(sorted(faltantes))}')
    return datos


def main():
    parser = argparse.ArgumentParser(description='Compilar el ejecutable único de SIDP')
    parser.add_argument('--paquete', help='instalacion.json a incrustar (ejecutable preconfigurado)')
    parser.add_argument('--tipo', choices=sorted(TIPOS), default='generico')
    parser.add_argument('--nombre', help='Nombre del ejecutable (por omisión, el del tipo)')
    parser.add_argument('--destino', default=str(RAIZ / 'dist'))
    args = parser.parse_args()

    nombre, entrada = TIPOS[args.tipo]
    args.nombre = args.nombre or nombre
    trabajo = Path(tempfile.mkdtemp(prefix='sidp-build-'))
    compilacion = trabajo / 'compilacion.txt'
    compilacion.write_text(f'compilado {datetime.date.today().isoformat()} ({version_git()})', encoding='utf-8')
    comando = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console',
               '--name', args.nombre, '--paths', str(RAIZ), '--distpath', args.destino,
               '--workpath', str(trabajo / 'build'), '--specpath', str(trabajo)]
    comando += [f'--hidden-import={m}' for m in OCULTOS] + [f'--exclude-module={m}' for m in EXCLUIDOS]
    comando += ['--add-data', f'{compilacion}{os.pathsep}.']
    if args.paquete:
        datos = validar_paquete(args.paquete)
        comando += ['--add-data', f'{Path(args.paquete).resolve()}{os.pathsep}.']
        print(f'Incrustando instalación "{datos["nombre"]}" ({datos["instalacion"]})')
    comando.append(str(RAIZ / 'sidp' / entrada))
    try:
        subprocess.run(comando, check=True, cwd=RAIZ)
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)
    print(f'Listo: {Path(args.destino) / args.nombre}{".exe" if os.name == "nt" else ""}')


if __name__ == '__main__':
    main()
