"""Corre las fichas de prueba y guarda los resultados para Claude.

Uso, desde la raíz del repositorio:
    python -m cerebro.laboratorio.correr               # procesos y modelo
    python -m cerebro.laboratorio.correr --sin-modelo  # solo procesos, sin guardar informe
    python -m cerebro.laboratorio.correr --pares --modelo sidp-revisor-2  # solo la zona gris
"""
import argparse
import datetime
import json
import platform
import statistics
import urllib.request
from pathlib import Path

from cerebro.laboratorio import comparador, modelo

AQUI = Path(__file__).parent


def version_ollama(url):
    try:
        with urllib.request.urlopen(url.replace('/api/chat', '/api/version'), timeout=5) as respuesta:
            return json.load(respuesta).get('version', '?')
    except Exception as error:
        return f'sin respuesta ({error})'


def evaluar(ficha, hallazgos, grises):
    esperado = ficha['esperado']
    return (comparador.estado(hallazgos, grises) == esperado['estado']
            and sorted({h['campo'] for h in hallazgos}) == sorted(esperado['hallazgos'])
            and sorted(g['campo'] for g in grises) == sorted(esperado['grises']))


def correr(fichas, hoy, usar_modelo, nombre_modelo, url, vueltas):
    filas = []
    for ficha in fichas:
        hallazgos, grises = comparador.revisar(ficha['datos'], hoy)
        for gris in grises:
            aceptadas = ficha['esperado']['grises'].get(gris['campo'], [])
            gris['esperado'] = aceptadas
            gris['opiniones'] = [modelo.opinar(gris, nombre_modelo, url) for _ in range(vueltas)] if usar_modelo else []
            gris['aciertos'] = sum(o['misma'] in aceptadas for o in gris['opiniones'])
            # "si" cuando lo correcto es "no": sería peligroso dejar que el modelo despejara el caso.
            gris['peligrosas'] = sum(o['misma'] == 'si' and 'si' not in aceptadas for o in gris['opiniones'])
        filas.append({'id': ficha['id'], 'descripcion': ficha['descripcion'],
                      'estado': comparador.estado(hallazgos, grises), 'reglas_ok': evaluar(ficha, hallazgos, grises),
                      'hallazgos': hallazgos, 'grises': grises})
    return filas


def correr_pares(pares, usar_modelo, nombre_modelo, url, vueltas):
    filas = []
    for par in pares:
        proceso = comparador.comparar(par['a'], par['b'], par['tipo'])[0]
        opiniones = [modelo.opinar(par, nombre_modelo, url) for _ in range(vueltas)] if usar_modelo and proceso == 'gris' else []
        filas.append({**par, 'proceso': proceso, 'opiniones': opiniones,
                      'aciertos': sum(o['misma'] in par['esperado'] for o in opiniones),
                      'peligrosas': sum(o['misma'] == 'si' and 'si' not in par['esperado'] for o in opiniones)})
    return filas


def informe_pares(filas, entorno):
    opiniones = [o for f in filas for o in f['opiniones']]
    lineas = ['# Resultados del laboratorio: zona gris', '']
    lineas += [f'- {clave}: {valor}' for clave, valor in entorno.items()] + ['', '## Resumen', '',
               f'- Pares en zona gris según los procesos: {sum(f["proceso"] == "gris" for f in filas)} de {len(filas)}.',
               f'- Opiniones acertadas: {sum(f["aciertos"] for f in filas)} de {len(opiniones)}; '
               f'{sum(f["peligrosas"] for f in filas)} dijeron "si" cuando era "no".']
    if opiniones:
        segundos = [o['segundos'] for o in opiniones]
        lineas.append(f'- Tiempo por opinión: promedio {statistics.mean(segundos):.1f} s, máximo {max(segundos):.1f} s.')
    lineas += ['', '## Pares', '', '| Par | Tipo | Texto A | Texto B | Esperado | Opiniones |', '|---|---|---|---|---|---|']
    for f in filas:
        opiniones_par = ', '.join(o['misma'] for o in f['opiniones']) or f'sin modelo (proceso: {f["proceso"]})'
        lineas.append(f'| {f["id"]} | {f["tipo"]} | {f["a"]} | {f["b"]} | {"/".join(f["esperado"])} | {opiniones_par} |')
    lineas += ['', '## Detalle', '', '```json', json.dumps(filas, ensure_ascii=False, indent=1), '```', '']
    return '\n'.join(lineas)


def informe(filas, entorno):
    lineas = ['# Resultados del laboratorio del cerebro', '']
    lineas += [f'- {clave}: {valor}' for clave, valor in entorno.items()] + ['']
    reglas = sum(f['reglas_ok'] for f in filas)
    opiniones = [o for f in filas for g in f['grises'] for o in g['opiniones']]
    aciertos = sum(g['aciertos'] for f in filas for g in f['grises'])
    peligrosas = sum(g['peligrosas'] for f in filas for g in f['grises'])
    lineas += ['## Resumen', '',
               f'- Procesos (reglas): {reglas} de {len(filas)} fichas como se esperaba.',
               f'- Opiniones del modelo: {aciertos} de {len(opiniones)} acertadas; {peligrosas} dijeron "si" cuando era "no".']
    if opiniones:
        segundos = [o['segundos'] for o in opiniones]
        lineas.append(f'- Tiempo por opinión: promedio {statistics.mean(segundos):.1f} s, máximo {max(segundos):.1f} s.')
    lineas += ['', '## Fichas', '', '| Ficha | Qué prueba | Estado | Reglas | Zona gris: esperado → opiniones |',
               '|---|---|---|---|---|']
    for f in filas:
        grises = '; '.join(f'{g["campo"]}: {"/".join(g["esperado"]) or "?"} → '
                           f'{", ".join(o["misma"] for o in g["opiniones"]) or "sin modelo"}' for g in f['grises'])
        lineas.append(f'| {f["id"]} | {f["descripcion"]} | {f["estado"]} | {"OK" if f["reglas_ok"] else "FALLA"} | {grises or "-"} |')
    lineas += ['', '## Detalle', '', '```json', json.dumps(filas, ensure_ascii=False, indent=1), '```', '']
    return '\n'.join(lineas)


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m cerebro.laboratorio.correr')
    parser.add_argument('--sin-modelo', action='store_true', help='Solo procesos, sin llamar a Ollama')
    parser.add_argument('--modelo', default=modelo.MODELO)
    parser.add_argument('--url', default=modelo.URL)
    parser.add_argument('--vueltas', type=int, default=3)
    parser.add_argument('--fichas', type=Path, default=AQUI / 'fichas.json')
    parser.add_argument('--pares', action='store_true', help='Probar solo los pares de zona gris de pares.json')
    parser.add_argument('--salida', type=Path, default=AQUI / 'resultados')
    args = parser.parse_args(argumentos)

    ahora = datetime.datetime.now()
    entorno = {'Fecha': ahora.strftime('%Y-%m-%d %H:%M'), 'Equipo': platform.node(), 'Sistema': platform.platform(),
               'Procesador': platform.processor() or '?', 'Python': platform.python_version(),
               'Modelo': 'sin modelo' if args.sin_modelo else args.modelo,
               'Ollama': 'no se usó' if args.sin_modelo else version_ollama(args.url)}
    if args.pares:
        pares = json.loads((AQUI / 'pares.json').read_text(encoding='utf-8'))['pares']
        texto = informe_pares(correr_pares(pares, not args.sin_modelo, args.modelo, args.url, args.vueltas), entorno)
        print(texto.split('## Detalle')[0])
        if not args.sin_modelo:
            args.salida.mkdir(parents=True, exist_ok=True)
            archivo = args.salida / f'{ahora:%Y-%m-%d_%H%M}_{args.modelo.replace(":", "-")}_pares.md'
            archivo.write_text(texto, encoding='utf-8')
            print(f'Guardado en {archivo}')
        return 0
    datos = json.loads(args.fichas.read_text(encoding='utf-8'))
    hoy = datetime.date.fromisoformat(datos['hoy'])
    filas = correr(datos['fichas'], hoy, not args.sin_modelo, args.modelo, args.url, args.vueltas)
    if args.sin_modelo:  # Comprobación rápida: no deja informe.
        print(informe(filas, entorno).split('## Detalle')[0])
        return 0 if all(f['reglas_ok'] for f in filas) else 1
    args.salida.mkdir(parents=True, exist_ok=True)
    archivo = args.salida / f'{ahora:%Y-%m-%d_%H%M}.md'
    archivo.write_text(informe(filas, entorno), encoding='utf-8')
    print(informe(filas, entorno).split('## Detalle')[0])
    print(f'Guardado en {archivo}')
    return 0 if all(f['reglas_ok'] for f in filas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
