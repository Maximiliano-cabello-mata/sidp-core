"""Prueba oficial del validador: expedientes reales mezclados con falsos, en una carpeta local.

Uso, desde la raíz del repositorio:
    python -m validacion.prueba C:\\SIDP-prueba
    python -m validacion.prueba validacion\\ejemplo --hoy 2026-10-14 --sin-modelo   # ejemplo con datos inventados

La carpeta lleva `expedientes/<id>/` (ver validacion/expediente.py) y, si se quiere medir,
`etiquetas.csv` con columnas expediente,es_falso,trampa. Deja dos archivos en la carpeta:
- informe_local.html: el detalle con datos personales. Se queda en este equipo.
- resumen_para_repo.md: solo números y claves de reglas, sin nombres, CURP ni domicilios.
"""
import argparse
import csv
import datetime
import html
import json
import platform
import statistics
import sys
from collections import Counter
from pathlib import Path

from validacion import expediente, lector, modelo

TRAMPAS = {'nombre', 'curp', 'fecha', 'sexo', 'tutor', 'domicilio', 'comprobante_viejo', 'otro_documento',
           'falta_documento', 'foto_mala', 'texto_oculto', 'otra'}
DOCUMENTOS_REALES = lector.PDF | lector.IMAGEN


def dentro_de_repositorio(carpeta):
    return any((padre / '.git').exists() for padre in [carpeta, *carpeta.parents])


def etiquetas(carpeta):
    archivo = carpeta / 'etiquetas.csv'
    if not archivo.exists():
        return {}
    with archivo.open(encoding='utf-8-sig', newline='') as entrada:
        return {fila['expediente'].strip(): {'falso': fila.get('es_falso', '').strip().lower() in ('si', 'sí', 's', '1'),
                                             'trampa': (fila.get('trampa') or '').strip().lower()}
                for fila in csv.DictReader(entrada) if fila.get('expediente')}


def medir(resultados, marcas):
    """Números de la prueba. No guarda nombres: solo estados, reglas y opiniones."""
    medidas = {'expedientes': len(resultados), 'etiquetados': 0, 'verdaderos': 0, 'verdaderos_listos': 0, 'falsas_alarmas': 0,
               'falsos': 0, 'falsos_detectados': 0, 'falsos_pasaron': 0, 'trampas_pasaron': Counter(), 'trampas': Counter(),
               'reglas_verdaderos': Counter(), 'reglas_falsos': Counter(), 'no_leidos': Counter(), 'opiniones': Counter()}
    for r in resultados:
        reglas = [h['regla'] for h in r['hallazgos']] + [g['regla'] for g in r['grises']] + [n['regla'] for n in r['no_leidos']]
        medidas['no_leidos'].update(n['regla'] for n in r['no_leidos'])
        marca = marcas.get(r['id'])
        grupo = 'falsos' if marca and marca['falso'] else 'verdaderos'
        for g in r['grises']:
            medidas['opiniones'][(grupo if marca else 'sin_etiqueta', g['opinion']['misma'])] += 1
        if not marca:
            continue
        medidas['etiquetados'] += 1
        listo = r['estado'] == 'listo para autorizar'
        medidas[f'reglas_{grupo}'].update(set(reglas))
        if marca['falso']:
            trampa = marca['trampa'] if marca['trampa'] in TRAMPAS else 'otra'
            medidas['falsos'] += 1
            medidas['trampas'][trampa] += 1
            if listo:
                medidas['falsos_pasaron'] += 1
                medidas['trampas_pasaron'][trampa] += 1
            else:
                medidas['falsos_detectados'] += 1
        else:
            medidas['verdaderos'] += 1
            medidas['verdaderos_listos' if listo else 'falsas_alarmas'] += 1
    segundos = [r['segundos'] for r in resultados] or [0]
    medidas['segundos_promedio'], medidas['segundos_maximo'] = round(statistics.mean(segundos), 1), max(segundos)
    return medidas


def porcentaje(parte, total):
    return f'{parte} de {total} ({100 * parte / total:.0f} %)' if total else f'{parte} de {total}'


def resumen(medidas, entorno, resultados, marcas):
    m = medidas
    lineas = ['# Prueba del validador: resumen sin datos personales', '']
    lineas += [f'- {clave}: {valor}' for clave, valor in entorno.items()]
    lineas += ['', '## Resultado', '',
               f'- Expedientes revisados: {m["expedientes"]}; con etiqueta: {m["etiquetados"]}.',
               f'- Verdaderos que quedaron listos para autorizar: {porcentaje(m["verdaderos_listos"], m["verdaderos"])}.',
               f'- Verdaderos enviados a revisión manual (falsa alarma): {porcentaje(m["falsas_alarmas"], m["verdaderos"])}.',
               f'- Falsos detectados (enviados a revisión): {porcentaje(m["falsos_detectados"], m["falsos"])}.',
               f'- **Falsos que pasaron como listos (peligroso): {porcentaje(m["falsos_pasaron"], m["falsos"])}.**',
               f'- Tiempo por expediente: promedio {m["segundos_promedio"]} s, máximo {m["segundos_maximo"]} s.', '']
    if m['trampas']:
        lineas += ['## Trampas', '', '| Trampa | Expedientes | Pasaron |', '|---|---|---|']
        lineas += [f'| {t} | {n} | {m["trampas_pasaron"][t]} |' for t, n in sorted(m['trampas'].items())] + ['']
    reglas = sorted(set(m['reglas_verdaderos']) | set(m['reglas_falsos']))
    if reglas:
        lineas += ['## Reglas que se activaron', '', '| Regla | En verdaderos | En falsos |', '|---|---|---|']
        lineas += [f'| {r} | {m["reglas_verdaderos"][r]} | {m["reglas_falsos"][r]} |' for r in reglas] + ['']
    if m['no_leidos']:
        lineas += ['## No se pudo leer', '', '| Regla | Veces |', '|---|---|']
        lineas += [f'| {r} | {n} |' for r, n in sorted(m['no_leidos'].items())] + ['']
    if m['opiniones']:
        lineas += ['## Opiniones del modelo en la zona gris', '', '| Expedientes | Opinión | Veces |', '|---|---|---|']
        lineas += [f'| {g} | {o} | {n} |' for (g, o), n in sorted(m['opiniones'].items())]
        lineas += ['', 'Un "si" en un expediente falso habría sido peligroso si el modelo decidiera; por eso nunca decide.', '']
    lineas += ['## Por expediente', '', 'Los expedientes se numeran por orden; aquí no van los nombres de las carpetas.', '',
               '| # | Etiqueta | Trampa | Estado | Reglas |', '|---|---|---|---|---|']
    for numero, r in enumerate(resultados, 1):
        marca = marcas.get(r['id'])
        etiqueta = ('falso' if marca['falso'] else 'verdadero') if marca else '-'
        trampa = (marca['trampa'] if marca['trampa'] in TRAMPAS else 'otra') if marca and marca['falso'] else ''
        reglas = sorted({h['regla'] for h in r['hallazgos']} | {g['regla'] for g in r['grises']} | {n['regla'] for n in r['no_leidos']})
        lineas.append(f'| {numero} | {etiqueta} | {trampa} | {r["estado"]} | {", ".join(reglas) or "-"} |')
    return '\n'.join(lineas) + '\n'


ESTILO = """
:root{--fondo:#f3f4f6;--tarjeta:#fff;--texto:#1f2937;--suave:#6b7280;--azul:#1d4ed8;--verde:#15803d;--ambar:#b45309;--rojo:#b91c1c;--borde:#e5e7eb}
@media (prefers-color-scheme:dark){:root{--fondo:#111827;--tarjeta:#1f2937;--texto:#f3f4f6;--suave:#9ca3af;--borde:#374151}}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--texto);font:15px/1.5 system-ui,Segoe UI,sans-serif}
header{background:var(--azul);color:#fff;padding:16px 24px}header h1{margin:0;font-size:20px}header p{margin:4px 0 0;opacity:.85}
main{max-width:1100px;margin:0 auto;padding:16px}.aviso{background:#fef3c7;color:#78350f;border-radius:10px;padding:10px 14px;margin-bottom:16px}
.tarjetas{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.tarjeta{background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;padding:14px}
.numero{font-size:28px;font-weight:700}.etiqueta{color:var(--suave);font-size:13px}
details{overflow-x:auto;background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;margin-bottom:10px;padding:10px 14px}
summary{cursor:pointer;font-weight:600;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.estado{border-radius:999px;padding:2px 10px;font-size:12px;color:#fff}.listo{background:var(--verde)}.revision{background:var(--ambar)}
.marca{font-size:12px;color:var(--suave)}.alta{color:var(--rojo)}.media{color:var(--ambar)}
table{width:100%;border-collapse:collapse;font-size:14px}td,th{border-bottom:1px solid var(--borde);padding:6px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
"""


def informe_html(resultados, medidas, entorno, marcas):
    e = html.escape
    m = medidas
    tarjetas = [(m['expedientes'], 'Expedientes revisados'),
                (sum(r['estado'] == 'listo para autorizar' for r in resultados), 'Listos para autorizar'),
                (sum(r['estado'] != 'listo para autorizar' for r in resultados), 'A revisión manual')]
    if m['etiquetados']:
        tarjetas += [(f'{m["falsos_detectados"]}/{m["falsos"]}', 'Falsos detectados'),
                     (f'{m["falsos_pasaron"]}', 'Falsos que pasaron (peligroso)'),
                     (f'{m["falsas_alarmas"]}/{m["verdaderos"]}', 'Verdaderos con falsa alarma')]
    partes = [f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
              f'<title>Prueba del validador</title><style>{ESTILO}</style></head><body>',
              f'<header><h1>Prueba del validador de expedientes</h1><p>{e(entorno["Fecha"])} · {e(entorno["Equipo"])} · modelo: {e(entorno["Modelo"])}</p></header><main>',
              '<div class="aviso">Este informe tiene datos personales. Se queda en este equipo: no lo subas al repositorio ni lo mandes por internet.</div>',
              '<div class="tarjetas">' + ''.join(f'<div class="tarjeta"><div class="numero">{e(str(n))}</div><div class="etiqueta">{e(t)}</div></div>'
                                                for n, t in tarjetas) + '</div>']
    for r in resultados:
        marca = marcas.get(r['id'])
        texto_marca = (f'falso: {marca["trampa"] or "sin trampa anotada"}' if marca['falso'] else 'verdadero') if marca else 'sin etiqueta'
        clase = 'listo' if r['estado'] == 'listo para autorizar' else 'revision'
        filas = [f'<tr><td class="{h["gravedad"]}">Hallazgo</td><td>{e(h["documento"])}</td><td>{e(h["detalle"])}</td><td>{e(h["regla"])}</td></tr>'
                 for h in r['hallazgos']]
        filas += [f'<tr><td>Zona gris</td><td>{e(g["documento"])}</td><td>"{e(g["a"])}" contra "{e(g["b"])}". Opinión: <b>{e(g["opinion"]["misma"])}</b>'
                  f' ({e(g["opinion"].get("motivo", ""))})</td><td>{e(g["regla"])}</td></tr>' for g in r['grises']]
        filas += [f'<tr><td>No se pudo leer</td><td>{e(n["documento"])}</td><td>{e(n["detalle"])}</td><td>{e(n["regla"])}</td></tr>'
                  for n in r['no_leidos']]
        documentos = ', '.join(f'{e(t)} ({e("+".join(d["metodo"]) or "sin leer")}, {d["caracteres"]} car.)' for t, d in r['documentos'].items())
        partes.append(f'<details{" open" if clase == "revision" else ""}><summary><span>{e(r["id"])}</span>'
                      f'<span class="estado {clase}">{e(r["estado"])}</span><span class="marca">{e(texto_marca)} · {r["segundos"]} s</span></summary>'
                      f'<p class="marca">Documentos: {documentos or "ninguno"}</p>'
                      + (f'<table><tr><th>Qué</th><th>Documento</th><th>Detalle</th><th>Regla</th></tr>{"".join(filas)}</table>' if filas
                         else '<p>Todo coincide. Falta que el administrador lo autorice.</p>') + '</details>')
    partes.append('</main></body></html>')
    return '\n'.join(partes)


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.prueba')
    parser.add_argument('carpeta', type=Path)
    parser.add_argument('--sin-modelo', action='store_true', help='Solo procesos, sin preguntar a Ollama')
    parser.add_argument('--modelo', default=modelo.MODELO)
    parser.add_argument('--url', default=modelo.URL)
    parser.add_argument('--hoy', type=datetime.date.fromisoformat, default=datetime.date.today())
    args = parser.parse_args(argumentos)

    carpeta = args.carpeta.resolve()
    expedientes = sorted(p for p in (carpeta / 'expedientes').glob('*') if p.is_dir()) if (carpeta / 'expedientes').is_dir() else []
    if not expedientes:
        print(f'No hay expedientes en {carpeta / "expedientes"}', file=sys.stderr)
        return 2
    if dentro_de_repositorio(carpeta) and any(a.suffix.lower() in DOCUMENTOS_REALES for p in expedientes for a in p.iterdir()):
        print('La carpeta tiene PDF o fotos y está dentro de un repositorio de Git. Muévela fuera para que '
              'los documentos nunca se suban.', file=sys.stderr)
        return 2
    disponibles = lector.herramientas()
    entorno = {'Fecha': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), 'Equipo': platform.node(),
               'Python': platform.python_version(), 'Modelo': 'sin modelo' if args.sin_modelo else args.modelo,
               'Herramientas': ', '.join(f'{k}: {v if isinstance(v, str) else "sí" if v else "no"}'
                                                 for k, v in disponibles.items())}
    resultados = []
    for numero, carpeta_expediente in enumerate(expedientes, 1):
        print(f'[{numero}/{len(expedientes)}] revisando...', flush=True)
        resultados.append(expediente.revisar(carpeta_expediente, args.hoy, not args.sin_modelo, args.modelo, args.url))
    marcas = etiquetas(carpeta)
    medidas = medir(resultados, marcas)
    (carpeta / 'informe_local.html').write_text(informe_html(resultados, medidas, entorno, marcas), encoding='utf-8')
    (carpeta / 'resultados_local.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding='utf-8')
    texto = resumen(medidas, entorno, resultados, marcas)
    (carpeta / 'resumen_para_repo.md').write_text(texto, encoding='utf-8')
    print(texto.split('## Por expediente')[0])
    print(f'Informe con detalle (se queda aquí): {carpeta / "informe_local.html"}')
    print(f'Resumen sin datos personales: {carpeta / "resumen_para_repo.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
