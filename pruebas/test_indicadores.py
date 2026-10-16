"""Lo que se cuenta de cada alumno (salud, domicilio, boletas, 911) y las tablas de la OMS. Todo es inventado."""
import datetime

from validacion import cerebro_red, indicadores, oms, respaldo

HOY = datetime.date(2026, 10, 16)


def dato(campo, valor, estado='vigente', detalle=None):
    return {'campo': campo, 'valor': valor, 'estado': estado, 'detalle': detalle or {}}


def test_la_oms_clasifica_el_imc_para_la_edad():
    # Con el IMC de la mediana (M) la puntuación z es 0: los números son los de la tabla de la OMS.
    assert oms.puntuacion_z(15.2641, 'H', 61) == 0 and oms.puntuacion_z(18.8012, 'M', 156) == 0
    assert oms.estado_nutricional(30, 1.30, 'H', '2017-03-01', HOY) == {'imc': 17.8, 'z': 0.81, 'clase': 'Peso normal'}
    assert oms.estado_nutricional(45, 130, 'H', '2017-03-01', HOY)['clase'] == 'Obesidad'  # Talla en centímetros.
    assert oms.estado_nutricional(16, 1.30, 'M', '2017-03-01', HOY)['clase'] in ('Delgadez', 'Delgadez severa')
    assert oms.estado_nutricional(400, 1.30, 'H', '2017-03-01', HOY) is None  # Un peso que no puede ser.
    assert oms.puntuacion_z(17, 'H', 40) is None  # Menos de 5 años: fuera de la tabla.


def test_lo_que_no_dice_nada_no_cuenta():
    assert indicadores.lista(['Negadas', 'Ninguna', 'No refiere', 'Sin alergias conocidas', '-', 'Polvo y polen', 'polvo']) == ['POLVO', 'POLEN']
    assert indicadores.sangre('O positivo') == 'O+' and indicadores.sangre('0-') == 'O-' and indicadores.sangre('AB RH negativo') == 'AB-'
    assert indicadores.sangre('Z+') is None
    assert indicadores.discapacidades(['Hipoacusia leve', 'Ninguna'], ['TDAH', 'Asma']) == ['Hipoacusia', 'TDAH']
    assert indicadores.discapacidades(['Pie plano']) == ['Otras condiciones']
    assert indicadores.vista('20/20', '') == 'Normal' and indicadores.vista('20/40', 'No') == 'Necesita valoración'
    assert indicadores.vista('Normal', 'Sí') == 'Usa lentes' and indicadores.vista('', '') is None
    assert indicadores.bucal('Sin caries') == 'Sana' and indicadores.bucal('Presenta caries') == 'Necesita dentista'
    assert indicadores.vacunas('Esquema completo') == 'Completas' and indicadores.vacunas('Incompleto') == 'Incompletas'
    assert indicadores.municipio('Municipio de Chalco, Estado de México') == 'CHALCO'
    assert indicadores.municipio('VALLE DE CHALCO SOLIDARIDAD') == 'VALLE DE CHALCO SOLIDARIDAD'  # Es otro municipio.
    assert indicadores.colonia('Col. San Martín') == 'SAN MARTIN' and indicadores.titulo('VALLE DE CHALCO') == 'Valle de Chalco'


def test_cada_alumno_se_cuenta_sin_su_nombre():
    datos = {'salud': [dato('peso', '32 kg'), dato('talla', '1.32'), dato('alergia', 'Penicilina'), dato('alergia', 'Negadas'),
                       dato('padecimiento', 'TDAH'), dato('fecha_certificado', '2026-08-20'), dato('tipo_sangre', 'A+', 'descartado')],
             'domicilio': [dato('domicilio', 'CALLE 5', detalle={'colonia': 'SAN MARTIN', 'municipio': 'CHALCO', 'cp': '56600'})],
             'escolar': [dato('promedio_1', '9.5'), dato('promedio_2', '8,7'), dato('promedio_3', '11'), dato('lenguajes_2', '8')]}
    r = indicadores.de_alumno(datos, 3, 'H', '2017-10-02', 'XXXX171002HDFXXXA1', '2026-2027', HOY)
    assert (r['edad_911'], r['columna_911'], r['nacido'], r['entidad']) == (8, '8', 'Otra entidad', 'Ciudad de México')
    assert (r['imc'], r['nutricion'], r['nutricion_segun']) == (18.4, 'Sobrepeso', 'OMS')
    assert r['alergias'] == ['PENICILINA'] and r['discapacidades'] == ['TDAH'] and r['tipo_sangre'] is None  # El descartado no cuenta.
    assert (r['municipio'], r['colonia'], r['cp']) == ('CHALCO', 'SAN MARTIN', '56600')
    assert r['promedios'] == {1: 9.5, 2: 8.7} and r['ultimo_promedio'] == 8.7 and r['formativos'] == {'lenguajes': 8.0}  # 11 no puede ser.
    assert r['con_salud'] and r['con_domicilio'] and r['con_boletas']
    assert indicadores.de_alumno({}, 1, 'M', '2020-09-05', 'XXXX200905MNEXXXA1', '2026-2027', HOY)['columna_911'] == 'Menos de 6'
    assert indicadores.de_alumno({}, 1, 'M', None, 'XXXX200905MNEXXXA1', '2026-2027', HOY)['nacido'] == 'Otro país'


def test_las_senas_de_una_plantilla_son_solo_texto_impreso():
    assert cerebro_red.senas(['FICHA DE INSCRIPCIÓN', 'Ciclo 2026-2027', 'ficha de inscripción', 'Sí', 'Datos del alumno:']) == \
        ['FICHA DE INSCRIPCIÓN', 'Datos del alumno']


def test_el_respaldo_no_lleva_la_ventana_ni_se_detiene_por_un_archivo_bloqueado(tmp_path, monkeypatch):
    (tmp_path / 'ventana' / 'Default' / 'Cache').mkdir(parents=True)
    (tmp_path / 'ventana' / 'Default' / 'Cache' / 'data_0').write_bytes(b'cache de Edge')
    (tmp_path / 'expedientes').mkdir()
    (tmp_path / 'expedientes' / 'acta.pdf').write_bytes(b'%PDF-1.4')
    (tmp_path / 'bloqueado.txt').write_text('abierto por otro programa', encoding='utf-8')
    leer = type(tmp_path).read_bytes

    def read_bytes(ruta):
        if ruta.name == 'bloqueado.txt':
            raise PermissionError(13, 'Permission denied')
        return leer(ruta)
    monkeypatch.setattr(type(tmp_path), 'read_bytes', read_bytes)
    assert [r for r, _ in respaldo.archivos_de(tmp_path)] == ['expedientes/acta.pdf']
