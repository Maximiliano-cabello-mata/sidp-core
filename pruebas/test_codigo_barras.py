"""Las etiquetas del inventario: el código de barras que se imprime es el que lee un lector."""
import pytest

from validacion import codigo_barras


def test_el_codigo_de_barras_se_lee_con_un_lector():
    zxingcpp = pytest.importorskip('zxingcpp')
    from PIL import Image, ImageDraw
    for texto in ('MOB-000001', 'COM-123456'):
        lista, ancho = codigo_barras.barras(texto)
        imagen = Image.new('L', (ancho * 3, 80), 255)
        dibujo = ImageDraw.Draw(imagen)
        for x, w in lista:
            dibujo.rectangle([x * 3, 0, (x + w) * 3 - 1, 79], fill=0)
        assert [r.text for r in zxingcpp.read_barcodes(imagen)] == [texto]
    with pytest.raises(ValueError):
        codigo_barras.svg('MESA Ñ')
