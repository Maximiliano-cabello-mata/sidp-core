"""Arma la demostración pública de la validación para GitHub Pages.

Copia las mismas pantallas de SIDP-Validador.exe y empaqueta el código de Python del
repositorio y los expedientes inventados del ejemplo. En la página, el navegador corre ese
código con Pyodide: nada se envía a ningún lado y no hay documentos reales.

    python -m herramientas.armar_pagina _pagina
"""
import argparse
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
INTERFAZ = RAIZ / 'validacion' / 'interfaz'
EJEMPLO = RAIZ / 'validacion' / 'ejemplo'
PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/'
CODIGO = ['validacion/__init__.py', 'validacion/comparador.py', 'validacion/modelo.py', 'validacion/lector.py',
          'validacion/expediente.py', 'validacion/prueba.py', 'validacion/cerebro_red.py', 'validacion/registro.py', 'validacion/renapo.py', 'validacion/extraer.py',
          'validacion/plantillas.py',
          'validacion/servicio.py', 'database/__init__.py', 'database/procedimientos.py', 'database/diseno_integral.sql']


def ejemplo():
    """Solo lo inventado: la captura y el texto de cada documento, más las etiquetas de la prueba."""
    archivos = {'etiquetas.csv': (EJEMPLO / 'etiquetas.csv').read_text(encoding='utf-8')}
    for archivo in sorted((EJEMPLO / 'expedientes').glob('*/*')):
        if archivo.suffix in ('.txt', '.json') and archivo.name != 'resultado.json':
            archivos[f'expedientes/{archivo.parent.name}/{archivo.name}'] = archivo.read_text(encoding='utf-8')
    return archivos


def armar(destino, pyodide=PYODIDE):
    destino = Path(destino)
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    config = f'window.SIDP = {json.dumps({"modo": "demo", "pyodide": pyodide})};'
    for nombre, salida in (('panel.html', 'index.html'), ('padres.html', 'padres.html')):
        texto = (INTERFAZ / nombre).read_text(encoding='utf-8')
        (destino / salida).write_text(texto.replace('/*SIDP_CONFIG*/', config), encoding='utf-8')
    for nombre in ('estilo.css', 'motor.js'):
        shutil.copy(INTERFAZ / nombre, destino / nombre)
    codigo = {ruta: (RAIZ / ruta).read_text(encoding='utf-8') for ruta in CODIGO}
    (destino / 'codigo.json').write_text(json.dumps(codigo, ensure_ascii=False), encoding='utf-8')
    (destino / 'ejemplo.json').write_text(json.dumps(ejemplo(), ensure_ascii=False), encoding='utf-8')
    (destino / '.nojekyll').write_text('', encoding='utf-8')
    return destino


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m herramientas.armar_pagina')
    parser.add_argument('destino', type=Path)
    parser.add_argument('--pyodide', default=PYODIDE, help='Dónde está Pyodide (para probar sin internet)')
    args = parser.parse_args(argumentos)
    print(f'Página armada en {armar(args.destino, args.pyodide)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
