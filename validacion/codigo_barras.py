"""Códigos de barras Code 128 (juego B) para las etiquetas del inventario, sin bibliotecas.

Cualquier lector de códigos de barras USB (los que escriben como teclado) lee estas etiquetas: al escanear, el
código aparece en el campo de búsqueda del inventario y se abre la pieza.
"""
import html

# Anchos de barra y espacio de cada símbolo (0 a 106), en módulos. 103-105 son los inicios A, B y C; 106 es el fin.
PATRONES = (
    '212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 '
    '123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 '
    '232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 '
    '313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 '
    '111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 '
    '111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 '
    '114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112').split()
INICIO_B = 104
FIN = 106


def simbolos(texto):
    """Los símbolos del código: inicio B, un símbolo por letra, el dígito de control y el fin."""
    if not texto or any(not 32 <= ord(c) <= 126 for c in texto):
        raise ValueError(f'el código solo puede llevar letras, números y signos sin acento: {texto!r}')
    valores = [ord(c) - 32 for c in texto]
    control = (INICIO_B + sum(i * v for i, v in enumerate(valores, 1))) % 103
    return [INICIO_B, *valores, control, FIN]


def barras(texto):
    """[(posición, ancho)] de cada barra negra, en módulos, con 10 módulos de margen blanco a cada lado."""
    salida, x = [], 10
    for simbolo in simbolos(texto):
        for i, ancho in enumerate(PATRONES[simbolo]):
            if i % 2 == 0:
                salida.append((x, int(ancho)))
            x += int(ancho)
    return salida, x + 10


def svg(texto, alto=40, modulo=2):
    """El código como SVG: barras negras sobre blanco, listo para imprimir."""
    lista, ancho = barras(texto)
    rects = ''.join(f'<rect x="{x * modulo}" y="0" width="{w * modulo}" height="{alto}"/>' for x, w in lista)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho * modulo} {alto}" width="{ancho * modulo}" height="{alto}" '
            f'role="img" aria-label="{html.escape(texto)}"><rect width="100%" height="100%" fill="#fff"/><g fill="#000">{rects}</g></svg>')


def hoja_etiquetas(piezas, escuela='Escuela Primaria Delfino Pando'):
    """Página para imprimir: una etiqueta por pieza con su código de barras, el código en letra y qué es."""
    etiquetas = ''.join(
        f'<div class="etiqueta">{svg(p["codigo"])}<div class="codigo">{html.escape(p["codigo"])}</div>'
        f'<div class="que">{html.escape(p.get("nombre") or "")}</div>'
        f'<div class="donde">{html.escape(escuela)}{" · " + html.escape(p["ubicacion"]) if p.get("ubicacion") else ""}</div></div>'
        for p in piezas)
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Etiquetas de inventario</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 12px; color: #000; background: #fff; }}
.barra {{ margin-bottom: 12px; }} .barra button {{ font-size: 16px; padding: 8px 16px; }}
.hoja {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
.etiqueta {{ border: 1px dashed #999; padding: 8px; text-align: center; break-inside: avoid; }}
.etiqueta svg {{ max-width: 100%; height: 40px; }}
.codigo {{ font: bold 15px monospace; letter-spacing: 1px; }} .que {{ font-size: 12px; }} .donde {{ font-size: 10px; color: #444; }}
@media print {{ .barra {{ display: none; }} body {{ margin: 0; }} }}
</style></head><body>
<div class="barra"><button onclick="print()">Imprimir</button> {len(piezas)} etiqueta(s). Pégalas en un lugar que no se raspe.</div>
<div class="hoja">{etiquetas}</div></body></html>'''
