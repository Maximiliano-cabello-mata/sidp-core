"""Análisis del cerebro sobre lo que ya se guardó en SIDP-Validador.exe (entorno de pruebas).

Corre en la PC 4. Lee del .exe, por IP y con la clave del cerebro, lo que el validador
extrajo y lo que decidió el administrador (sin archivos ni documentos). Cuenta qué reglas
se activan, qué documentos no se leen y en cuántos casos la persona coincidió con el
sistema. Después regresa el informe al .exe, que lo guarda en su carpeta `analisis/`.
La PC 4 no se queda con nada.

    python -m validacion.analisis --exe http://192.168.1.30:8770
"""
import argparse
import json
import urllib.request
from collections import Counter
from pathlib import Path


LISTO = 'listo para autorizar'


def analizar(expedientes):
    reglas, metodos, problemas = Counter(), Counter(), Counter()
    coinciden = difieren = sin_decision = 0
    for e in expedientes:
        reglas.update(e['reglas'])
        for tipo, documento in e.get('documentos', {}).items():
            metodos[(tipo, '+'.join(documento.get('metodo', [])) or 'sin leer')] += 1
            problemas.update(p.split(': ', 1)[-1] for p in documento.get('problemas', []))
        if not e.get('decision'):
            sin_decision += 1
        elif (e['estado'] == LISTO) == (e['decision']['decision'] == 'autorizado'):
            coinciden += 1
        else:
            difieren += 1
    lineas = ['# Análisis del cerebro', '', f'- Expedientes revisados: {len(expedientes)}.',
              f'- Listos para autorizar según el sistema: {sum(e["estado"] == LISTO for e in expedientes)}.',
              f'- Decisiones de la persona que coinciden con el sistema: {coinciden}; que difieren: {difieren}; '
              f'sin decidir: {sin_decision}.', '']
    if reglas:
        lineas += ['## Reglas que más se activan', '', '| Regla | Expedientes |', '|---|---|']
        lineas += [f'| {r} | {n} |' for r, n in reglas.most_common()] + ['']
    if metodos:
        lineas += ['## Cómo se leyó cada documento', '', '| Documento | Método | Veces |', '|---|---|---|']
        lineas += [f'| {t} | {m} | {n} |' for (t, m), n in sorted(metodos.items())] + ['']
    if problemas:
        lineas += ['## Problemas al leer', '', '| Problema | Veces |', '|---|---|']
        lineas += [f'| {p} | {n} |' for p, n in problemas.most_common(15)] + ['']
    return '\n'.join(lineas)


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.analisis')
    parser.add_argument('--exe', required=True, help='Dirección de SIDP-Validador.exe, por ejemplo http://192.168.1.30:8770')
    parser.add_argument('--clave', type=Path, default=Path.home() / '.sidp' / 'clave_cerebro.txt')
    args = parser.parse_args(argumentos)
    clave = args.clave.read_text(encoding='utf-8').strip()
    base = args.exe.rstrip('/')
    with urllib.request.urlopen(urllib.request.Request(base + '/api/cerebro/datos', headers={'X-SIDP-Clave': clave}), timeout=30) as r:
        expedientes = json.load(r)['expedientes']
    informe = analizar(expedientes)
    print(informe)
    solicitud = urllib.request.Request(base + '/api/cerebro/analisis', informe.encode('utf-8'),
                                       {'Content-Type': 'text/markdown; charset=utf-8', 'X-SIDP-Clave': clave})
    with urllib.request.urlopen(solicitud, timeout=30) as r:
        print(f'Guardado en el .exe: analisis/{json.load(r)["guardado"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
