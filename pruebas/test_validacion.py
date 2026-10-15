"""El validador de expedientes revisa la captura contra los documentos y la prueba no saca datos personales."""
import datetime
import json
import shutil
from pathlib import Path
import pytest
from validacion import expediente, lector, prueba
from validacion.ejemplo import generar

HOY = datetime.date(2026, 10, 14)


@pytest.fixture
def ejemplo(tmp_path):
    generar.generar(tmp_path)
    return tmp_path


def revisar(carpeta):
    return expediente.revisar(carpeta, HOY, usar_modelo=False)


def reglas(resultado):
    return {h['regla'] for h in resultado['hallazgos']} | {g['regla'] for g in resultado['grises']} | {
        n['regla'] for n in resultado['no_leidos']}


@pytest.mark.parametrize('clave,esperadas', [
    ('E01', set()), ('E02', set()), ('E04', set()),
    ('E03', {'ine_tutor_nombre'}),            # una letra distinta en la INE: zona gris
    ('E05', {'acta_fecha'}),                  # la fecha del acta no es la de la CURP
    ('E06', {'comprobante_viejo'}),
    ('E07', {'ine_tutor_nombre'}),            # INE de otra persona
    ('E08', {'curp_digito', 'acta_curp'}),
    ('E09', {'comprobante_domicilio'}),       # otro número de casa
    ('E10', {'texto_sospechoso'}),
])
def test_expedientes_de_ejemplo(ejemplo, clave, esperadas):
    resultado = revisar(ejemplo / 'expedientes' / clave)
    assert reglas(resultado) == esperadas
    assert resultado['estado'] == ('revisión manual' if esperadas else 'listo para autorizar')


def test_la_ine_pone_primero_los_apellidos(ejemplo):
    gris = revisar(ejemplo / 'expedientes' / 'E03')['grises'][0]
    assert gris['b'] == 'LAURA NABA PENA' and gris['sin_consultar'] is None


def test_falta_un_documento_obligatorio(ejemplo):
    carpeta = ejemplo / 'expedientes' / 'E01'
    (carpeta / 'comprobante.txt').unlink()
    assert {'falta_documento'} == reglas(revisar(carpeta))


def test_documento_equivocado(ejemplo):
    carpeta = ejemplo / 'expedientes' / 'E01'
    shutil.copy(carpeta / 'boleta.txt', carpeta / 'certificado_medico.txt')
    assert 'tipo_incorrecto' in reglas(revisar(carpeta))


def test_archivo_que_no_se_puede_leer_pasa_al_administrador(ejemplo):
    carpeta = ejemplo / 'expedientes' / 'E01'
    (carpeta / 'acta_alumno.txt').unlink()
    (carpeta / 'acta_alumno.docx').write_bytes(b'no es un documento aceptado')
    resultado = revisar(carpeta)
    assert resultado['no_leidos'][0]['regla'] == 'no_leido' and resultado['estado'] == 'revisión manual'


def test_fechas_en_varios_formatos():
    assert expediente.fechas('14/03/2018, 2018-03-14, 14 de marzo de 2018, 14-MAR-2018, 14 SEPT 2018') == [
        datetime.date(2018, 3, 14), datetime.date(2018, 3, 14), datetime.date(2018, 3, 14),
        datetime.date(2018, 3, 14), datetime.date(2018, 9, 14)]


def test_lector_sin_herramientas_no_falla(tmp_path, monkeypatch):
    monkeypatch.setattr(lector, '_pypdf', lambda: None)
    monkeypatch.setattr(lector, '_cv2', lambda: None)
    monkeypatch.setattr(lector, '_tesseract', lambda: None)
    (tmp_path / 'a.pdf').write_bytes(b'%PDF-1.4')
    (tmp_path / 'b.jpg').write_bytes(b'\xff\xd8')
    assert 'falta pypdf' in lector.leer(tmp_path / 'a.pdf')['problemas'][0]
    assert any('falta opencv' in p for p in lector.leer(tmp_path / 'b.jpg')['problemas'])


def test_prueba_mide_y_el_resumen_no_tiene_datos_personales(ejemplo):
    assert prueba.main([str(ejemplo), '--hoy', '2026-10-14', '--sin-modelo']) == 0
    resumen = (ejemplo / 'resumen_para_repo.md').read_text(encoding='utf-8')
    assert 'Falsos que pasaron como listos (peligroso): 0 de 6' in resumen
    assert 'Falsos detectados (enviados a revisión): 6 de 6' in resumen
    for captura in (ejemplo / 'expedientes').glob('*/captura.json'):
        datos = json.loads(captura.read_text(encoding='utf-8'))
        for valor in (datos['alumno']['nombre'], datos['alumno']['curp'], datos['tutor']['nombre'], captura.parent.name):
            assert valor not in resumen
    assert 'datos personales' in (ejemplo / 'informe_local.html').read_text(encoding='utf-8')


def test_no_corre_con_documentos_reales_dentro_de_un_repositorio(ejemplo):
    (ejemplo / '.git').mkdir()
    (ejemplo / 'expedientes' / 'E01' / 'ine_tutor_frente.jpg').write_bytes(b'\xff\xd8')
    assert prueba.main([str(ejemplo), '--sin-modelo']) == 2


def test_tipo_de_documento_tolera_errores_del_ocr():
    marcas = expediente.TIPOS['ine_tutor'][2]
    assert expediente.parece('INSTITUT0 NACI0NAL ELECT0RAL\nMEXICO', marcas)
    assert expediente.parece('CREDENClAL PARA V0TAR', marcas)
    assert not expediente.parece('RECIBO DE LUZ CFE', marcas)
    assert not expediente.parece('CF3 RECIBO', expediente.TIPOS['comprobante'][2][1:2])  # Las marcas cortas van exactas.


def test_franja_de_la_ine():
    from validacion import mrz
    nacimiento, vigencia = '850101', '241231'
    renglon = f'{nacimiento}{mrz.digito(nacimiento)}F{vigencia}{mrz.digito(vigencia)}MEX<02<<12345<7'
    texto = f'IDMEX1234567890<<0123456789012\n{renglon}\nRAMOS<SOTO<<MARIA<ELENA<<<<<<<'
    datos = mrz.leer(texto)
    assert datos['nombre'] == 'MARIA ELENA RAMOS SOTO' and datos['sexo'] == 'M'
    assert datos['nacimiento'] == datetime.date(1985, 1, 1) and datos['vigencia'] == datetime.date(2024, 12, 31)
    assert not mrz.leer(texto.replace('850101', '850102'))['nacimiento_valido']  # El OCR leyó mal un número.
    assert mrz.leer('RECIBO DE LUZ') is None


def test_ine_vencida_y_nombre_de_la_franja(ejemplo):
    from validacion import mrz
    carpeta = ejemplo / 'expedientes' / 'E01'
    nacimiento, vigencia = '850101', '241231'
    franja = f'\nIDMEX1234567890<<0123456789012\n{nacimiento}{mrz.digito(nacimiento)}F{vigencia}{mrz.digito(vigencia)}MEX<<<<<<<<<<<4\nRAMOS<SOTO<<MARIA<ELENA<<<<<<<'
    ine = carpeta / 'ine_tutor.txt'
    ine.write_text(ine.read_text(encoding='utf-8') + franja, encoding='utf-8')
    resultado = revisar(carpeta)
    assert 'ine_vencida' in reglas(resultado)
    assert resultado['extraidos']['ine_mrz']['nombre'] == 'MARIA ELENA RAMOS SOTO'


def test_fotos_chuecas_giradas_y_con_sombra(tmp_path):
    cv2 = pytest.importorskip('cv2')
    pytest.importorskip('PIL')
    if not lector._tesseract():
        pytest.skip('sin Tesseract')
    import numpy
    from validacion.ejemplo import fotos
    texto = (Path(generar.__file__).parent / 'expedientes' / 'E01' / 'ine_tutor.txt').read_text(encoding='utf-8')
    for variante in ('girada', 'sombra', 'escaneo'):
        foto = fotos.deformar(fotos.hoja(texto), variante, cv2, numpy)
        archivo = tmp_path / f'ine_{variante}.png'
        cv2.imwrite(str(archivo), foto)
        leido = lector.leer(archivo)
        assert expediente.parece(leido['texto'], expediente.TIPOS['ine_tutor'][2]), (variante, leido)
        assert 'RAMOS' in leido['texto'].upper()
