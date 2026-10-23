"""Lo que se cuenta de cada alumno (salud mínima, domicilio, boletas, 911). Todo es inventado."""
import datetime

from validacion import cerebro_red, estandar, indicadores, respaldo

HOY = datetime.date(2026, 10, 16)


def dato(campo, valor, estado='vigente', detalle=None):
    return {'campo': campo, 'valor': valor, 'estado': estado, 'detalle': detalle or {}}


def test_lo_que_no_dice_nada_no_cuenta():
    assert indicadores.lista(['Negadas', 'Ninguna', 'No refiere', 'Sin alergias conocidas', '-', 'Polvo y polen', 'polvo']) == ['POLVO', 'POLEN']
    assert indicadores.discapacidades(['Hipoacusia leve', 'Ninguna'], ['TDAH', 'Asma']) == ['Hipoacusia', 'TDAH']
    assert indicadores.discapacidades(['Pie plano']) == ['Otras condiciones']
    assert indicadores.municipio('Municipio de Chalco, Estado de México') == 'CHALCO'
    assert indicadores.municipio('VALLE DE CHALCO SOLIDARIDAD') == 'VALLE DE CHALCO SOLIDARIDAD'  # Es otro municipio.
    assert indicadores.colonia('Col. San Martín') == 'SAN MARTIN' and indicadores.titulo('VALLE DE CHALCO') == 'Valle de Chalco'


def test_cada_alumno_se_cuenta_sin_su_nombre():
    datos = {'salud': [dato('peso', '32 kg'), dato('talla', '1.32'), dato('alergia', 'Penicilina'), dato('alergia', 'Negadas'),
                       dato('padecimiento', 'TDAH'), dato('fecha_certificado', '2026-08-20'), dato('tipo_sangre', 'A+', 'descartado')],
             'domicilio': [dato('domicilio', 'CALLE 5', detalle={'colonia': 'SAN MARTIN', 'municipio': 'CHALCO', 'cp': '56600'})],
             'escolar': [dato('promedio_1', '9.5'), dato('promedio_2', '8,7'), dato('promedio_3', '11'), dato('lenguajes_2', '8'),
                         dato('repite_grado', 'no'), dato('repite_grado', 'sí'), dato('beca', 'federal'), dato('procedencia', 'otra_entidad')],
             'alumno': [dato('lengua_indigena', 'No'), dato('afrodescendiente', 'sí', 'descartado')]}
    r = indicadores.de_alumno(datos, 3, 'H', '2017-10-02', 'XXXX171002HDFXXXA1', '2026-2027', HOY)
    assert (r['edad_911'], r['columna_911'], r['nacido'], r['entidad']) == (8, '8', 'Otra entidad', 'Ciudad de México')
    assert r['alergias'] == ['PENICILINA'] and r['discapacidades'] == ['TDAH']
    assert 'imc' not in r and 'tipo_sangre' not in r and 'vista' not in r  # Solo lo necesario: peso, talla y sangre ya no se cuentan.
    # Lo del 911 que pone la escuela: gana lo último; lo descartado no cuenta.
    assert (r['repite'], r['beca'], r['procedencia'], r['lengua_indigena'], r['afro']) == ('sí', 'federal', 'otra_entidad', 'no', None)
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


def test_el_estandar_solo_deja_pasar_lo_que_pide_el_gobierno():
    assert estandar.permitido('salud', 'alergia') and estandar.permitido('escolar', 'repite_grado')
    assert estandar.permitido('escolar', 'promedio_3') and estandar.permitido('escolar', 'escuela_procedencia_2')
    assert not estandar.permitido('salud', 'peso') and not estandar.permitido('salud', 'tipo_sangre')
    assert not estandar.permitido('salud', 'agudeza_visual') and not estandar.permitido('escolar', 'inasistencias_2')
    assert not estandar.permitido('tutor', 'ocupacion')
    registro = estandar.registro({'curp': 'XXXX171002HDFXXXA1', 'nombres': 'LUIS', 'primer_apellido': 'RAMOS', 'segundo_apellido': 'GIL',
                                  'fecha_nacimiento': datetime.date(2017, 10, 2), 'sexo': 'H', 'grado': 3, 'letra': 'A'},
                                 {'escolar': [dato('repite_grado', 'no')]}, '2026-2027', HOY)
    assert (registro['nombre'], registro['grupo'], registro['repite'], registro['fecha_nacimiento']) == ('RAMOS GIL LUIS', '3° A', 'no', '2017-10-02')
    assert [f['clave'] for f in estandar.faltan([registro])] == ['procedencia', 'beca', 'lengua_indigena', 'afro']
