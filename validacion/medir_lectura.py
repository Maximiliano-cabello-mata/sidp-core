"""Mide cuánto saca el escaneo de cada campo, contra lo que de verdad dice cada hoja.

    python -m validacion.medir_lectura CARPETA [--sin-vision] [--modelo qwen2.5vl:3b] [--lecturas 1|2] [--lado 1280]
                                               [--hojas 6] [--etiqueta NOMBRE] [--ollama URL] [--hoy 2026-10-16]

CARPETA trae las hojas (fotos, escaneos o PDF), respuestas.csv (archivo, tipo, clave, valor; opcional letra y
variante) y, para hojas que no son documentos del sistema, campos.json ({tipo: [campos]}). Lo arma solo
python -m validacion.ejemplo.manuscritos. Cada hoja pasa por lo mismo que en el taller de la PC 4 (procesos
fijos, modelo que ve y reglas de cada campo) y se compara campo por campo:

- bien y solo:        se guardó solo y está bien;
- bien, un clic:      quedó "por confirmar" pero está bien (la persona solo da "Está bien");
- hay que corregir:   quedó "por confirmar" y está mal, o no se leyó (la persona lo escribe);
- PELIGROSO:          se guardó como seguro y está mal (nadie lo revisaría).

La meta es que "bien y solo" + "bien, un clic" pase de 80 % y que lo peligroso sea casi cero. Deja:
- resumen_lectura.md: solo números (se puede subir al repositorio);
- detalle_local.csv: lo leído y lo correcto de cada campo. Tiene los datos de las hojas: no sale de la PC.
Con --etiqueta X quedan como resumen_lectura_X.md y detalle_local_X.csv, para comparar ajustes (modelo, lecturas,
tamaño de la imagen) sobre las mismas hojas; --hojas N toma solo las primeras N, para que la comparación no tarde horas.
"""
import argparse
import collections
import csv
import datetime
import json
import time
from pathlib import Path

from validacion import campos as campos_mod
from validacion import comparador, lector, modelo, taller, vision

CLASES = ('bien_solo', 'bien_un_clic', 'corregir', 'vacio', 'peligroso')
NOMBRES = {'bien_solo': 'Bien y solo', 'bien_un_clic': 'Bien, un clic', 'corregir': 'Leído mal (por confirmar)',
           'vacio': 'No se leyó', 'peligroso': 'PELIGROSO: mal y marcado seguro'}


def igual(tipo, leido, correcto, hoy):
    if tipo == 'lista':
        return set(campos_mod.lista(leido or '')) == set(campos_mod.lista(correcto or ''))
    a = campos_mod.limpiar(tipo, leido, hoy)[0] if leido else None
    b = campos_mod.limpiar(tipo, correcto, hoy)[0] or correcto
    return a is not None and comparador.normalizar(str(a)) == comparador.normalizar(str(b))


def clase(resultado, tipo, correcto, hoy):
    if resultado is None:
        return 'vacio', ''
    leido = '' if resultado.get('nada') else str(resultado.get('valor') or '')
    seguro = resultado['confianza'] in ('alta', 'media', 'confirmado')
    if igual(tipo, leido, correcto, hoy):
        return ('bien_solo' if seguro else 'bien_un_clic'), leido
    return ('peligroso' if seguro else 'corregir'), leido


def leer_hoja(archivo, tipo, lista, hoy, modelo_vision, url, lecturas=None):
    """Lo mismo que hace el taller con un documento. Devuelve ({clave: resultado}, segundos del modelo)."""
    lectura = lector.leer(archivo)
    metodo = 'ocr' if any('ocr' in m for m in lectura['metodo']) else 'texto'
    procesos = taller.de_procesos(tipo, lectura['texto'], lectura['qr'], hoy, metodo)
    for clave, valor in campos_mod.de_texto(lectura['texto'], lista, hoy).items():
        procesos.setdefault(clave, (valor, metodo))
    vistos, segundos = None, 0.0
    if modelo_vision and taller.necesita_ver(lista, procesos):
        hojas = vision.paginas(archivo.read_bytes(), archivo.name)[:taller.MAXIMO_HOJAS]
        try:
            vistos, segundos = taller.ver(hojas, tipo.replace('_', ' '), lista, modelo_vision, url, lecturas, hoy)
        except vision.ErrorVision as error:
            print(f'{archivo.name}: {error}', flush=True)
    return {r['clave']: r for r in taller.combinar(lista, procesos, vistos, {}, hoy)}, segundos


def medir(carpeta, hoy=None, con_vision=True, nombre_modelo=None, url=modelo.URL, lecturas=None, hojas=None):
    carpeta = Path(carpeta)
    hoy = hoy or datetime.date.today()
    propios = json.loads((carpeta / 'campos.json').read_text(encoding='utf-8')) if (carpeta / 'campos.json').exists() else {}
    with open(carpeta / 'respuestas.csv', encoding='utf-8-sig') as entrada:
        respuestas = list(csv.DictReader(entrada))
    por_archivo = collections.defaultdict(list)
    for r in respuestas:
        por_archivo[r['archivo']].append(r)
    modelo_vision = vision.elegir(url, nombre_modelo) if con_vision else None
    if con_vision and not modelo_vision:
        raise SystemExit(f'No está instalado el modelo que ve {nombre_modelo or ""} (python -m validacion.vision modelos).')
    if modelo_vision:  # Que la carga del modelo no cuente en el tiempo de la primera hoja.
        print(f'Cargando {modelo_vision}... {vision.cargar(modelo_vision, url)} s', flush=True)
    detalle, tiempos = [], []
    for nombre, filas in sorted(por_archivo.items())[:hojas]:
        tipo = filas[0]['tipo']
        lista = propios.get(tipo) or campos_mod.FABRICA.get(tipo, [])
        archivo = carpeta / nombre
        if not archivo.exists() or not lista:
            print(f'{nombre}: {"no existe" if not archivo.exists() else "no hay campos para " + tipo}', flush=True)
            continue
        inicio = time.monotonic()
        leidos, segundos = leer_hoja(archivo, tipo, lista, hoy, modelo_vision, url, lecturas)
        tiempos.append((time.monotonic() - inicio, segundos))
        tipos = {c['clave']: c['tipo'] for c in lista}
        for fila in filas:
            if fila['clave'] not in tipos:
                continue
            que, leido = clase(leidos.get(fila['clave']), tipos[fila['clave']], fila['valor'], hoy)
            detalle.append({'archivo': nombre, 'tipo': tipo, 'clave': fila['clave'], 'tipo_campo': tipos[fila['clave']], 'correcto': fila['valor'],
                            'leido': leido, 'confianza': (leidos.get(fila['clave']) or {}).get('confianza', ''), 'resultado': que,
                            'letra': fila.get('letra', ''), 'variante': fila.get('variante', '')})
        print(f'{nombre}: {sum(1 for d in detalle if d["archivo"] == nombre and d["resultado"].startswith("bien"))} de '
              f'{sum(1 for d in detalle if d["archivo"] == nombre)} bien ({tiempos[-1][0]:.0f} s)', flush=True)
    return detalle, tiempos, modelo_vision


def tabla(detalle, por):
    grupos = collections.defaultdict(collections.Counter)
    for d in detalle:
        grupos[d[por] if por else 'Todo'][d['resultado']] += 1
    renglones = [f'| {por or ""} | Campos | ' + ' | '.join(NOMBRES[c] for c in CLASES) + ' | Bien (meta 80 %) |',
                 '|' + '---|' * (len(CLASES) + 3)]
    for clave, cuenta in sorted(grupos.items()):
        total = sum(cuenta.values())
        bien = cuenta['bien_solo'] + cuenta['bien_un_clic']
        renglones.append(f'| {clave} | {total} | ' + ' | '.join(str(cuenta[c]) for c in CLASES) + f' | {round(100 * bien / total)} % |')
    return '\n'.join(renglones)


def resumen(detalle, tiempos, modelo_vision, lecturas=1, lado=None):
    """Solo números y nombres de campos: nada de lo que dicen las hojas."""
    total = len(detalle)
    cuenta = collections.Counter(d['resultado'] for d in detalle)
    bien = cuenta['bien_solo'] + cuenta['bien_un_clic']
    hojas = len(tiempos)
    lineas = [f'# Medición de la lectura por campo ({datetime.date.today().isoformat()})', '',
              f'- Hojas: {hojas} · campos medidos: {total} · modelo que ve: '
              f'{f"{modelo_vision}, {lecturas} lectura(s) por hoja, imagen de {lado or vision.LADO} px" if modelo_vision else "ninguno (solo procesos)"}',
              f'- Tiempo por hoja: {sum(t for t, _ in tiempos) / hojas:.0f} s en promedio (modelo: {sum(s for _, s in tiempos) / hojas:.0f} s)' if hojas else '- Sin hojas',
              f'- **Bien (solo o con un clic): {round(100 * bien / total) if total else 0} %** · se llenaron solos y bien: '
              f'{round(100 * cuenta["bien_solo"] / total) if total else 0} % · peligrosos: {cuenta["peligroso"]}', '',
              '## Por tipo de hoja', '', tabla(detalle, 'tipo'), '', '## Por tipo de campo', '', tabla(detalle, 'tipo_campo'), '',
              '## Por letra', '', tabla(detalle, 'letra'), '', '## Por cómo se tomó la foto', '', tabla(detalle, 'variante'), '',
              '## Por campo', '', tabla(detalle, 'clave'), '']
    return '\n'.join(lineas)


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.medir_lectura')
    parser.add_argument('carpeta', type=Path)
    parser.add_argument('--sin-vision', action='store_true', help='Solo procesos fijos (para comparar)')
    parser.add_argument('--modelo', help='Por omisión el mejor modelo que ve instalado')
    parser.add_argument('--ollama', default=modelo.URL)
    parser.add_argument('--hoy', type=datetime.date.fromisoformat)
    parser.add_argument('--lecturas', type=int, choices=(1, 2), help='Cuántas veces lee el modelo cada hoja (por omisión, como el taller: 2)')
    parser.add_argument('--lado', type=int, help=f'Píxeles del lado mayor de la imagen para el modelo (por omisión {vision.LADO})')
    parser.add_argument('--hojas', type=int, help='Solo las primeras N hojas (para comparar ajustes sin esperar horas)')
    parser.add_argument('--etiqueta', default='', help='Sufijo de los archivos que deja: resumen_lectura_ETIQUETA.md')
    args = parser.parse_args(argumentos)
    vision.LADO = args.lado or vision.LADO
    fin = f'_{args.etiqueta}' if args.etiqueta else ''
    detalle, tiempos, modelo_vision = medir(args.carpeta, args.hoy, not args.sin_vision, args.modelo, args.ollama, args.lecturas, args.hojas)
    with open(args.carpeta / f'detalle_local{fin}.csv', 'w', newline='', encoding='utf-8') as salida:
        escritor = csv.DictWriter(salida, ['archivo', 'tipo', 'clave', 'tipo_campo', 'correcto', 'leido', 'confianza', 'resultado', 'letra', 'variante'])
        escritor.writeheader()
        escritor.writerows(detalle)
    texto = resumen(detalle, tiempos, modelo_vision, args.lecturas or taller.LECTURAS)
    (args.carpeta / f'resumen_lectura{fin}.md').write_text(texto, encoding='utf-8')
    print(texto.split('## Por tipo de hoja')[0])
    print(f'Resumen (solo números): {args.carpeta / f"resumen_lectura{fin}.md"} · detalle con datos (no sale de la PC): '
          f'{args.carpeta / f"detalle_local{fin}.csv"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
