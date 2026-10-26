"""Lo que se cuenta de cada alumno (salud, domicilio, boletas, 911) y las tablas de la OMS. Todo es inventado."""
import datetime

from validacion import cerebro_red, estandar, indicadores, oms, respaldo

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


def test_la_salud_general_se_resume_en_pocas_clases():
    assert indicadores.medida('talla', '128 cm') == '1.28' and indicadores.medida('talla', '1,18 m') == '1.18'
    assert indicadores.medida('peso', '22,5 kg') == '22.5' and indicadores.medida('peso', '3.2') is None  # El peso al nacer no.
    assert indicadores.sangre('O positivo') == 'O+' and indicadores.sangre('0-') == 'O-' and indicadores.sangre('AB RH negativo') == 'AB-'
    assert indicadores.sangre('Z+') is None
    assert indicadores.vista('20/20', '') == 'Normal' and indicadores.vista('OD 20/20 OI 20/40', 'No') == 'Necesita valoración'
    assert indicadores.vista('Normal', 'Sí') == 'Usa lentes' and indicadores.vista('Sin lentes, normal') == 'Normal'
    assert indicadores.vista('', '') is None
    assert indicadores.audicion('No presenta hipoacusia, normal') == 'Normal' and indicadores.audicion('Hipoacusia derecha') == 'Necesita valoración'
    assert indicadores.bucal('Sin caries') == 'Sana' and indicadores.bucal('Presenta caries') == 'Necesita dentista'
    assert indicadores.vacunas('Esquema completo') == 'Completas' and indicadores.vacunas('Incompleto') == 'Incompletas'
    assert indicadores.educacion_fisica('Apto') == 'Apto' and indicadores.educacion_fisica('Apto con restricciones: no correr') == 'Apto con cuidados'
    assert indicadores.educacion_fisica('No apto') == 'No apto' and indicadores.educacion_fisica('Sin restricciones') == 'Apto'
    assert indicadores.servicio('IMSS') == 'IMSS' and indicadores.servicio('IMSS Bienestar') == 'IMSS-Bienestar'
    assert indicadores.servicio('Ninguno') == 'Ninguno' and indicadores.servicio('no cuenta con seguro') == 'Ninguno'
    assert indicadores.misma_clase('agudeza_visual', '20/20 AMBOS OJOS', 'NORMAL') and not indicadores.misma_clase('vacunas', 'COMPLETO', 'INCOMPLETO')


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
    # Su salud general: el IMC para su edad con las tablas de la OMS; el tipo de sangre descartado no cuenta.
    assert (r['peso'], r['talla'], r['imc'], r['nutricion'], r['nutricion_segun'], r['tipo_sangre']) == (32.0, 1.32, 18.4, 'Sobrepeso', 'OMS', None)
    assert r['atender'] == ['sobrepeso para su edad', 'alergia a penicilina', 'TDAH'] and r['con_certificado'] and r['edad'] == 9
    assert r['resumen'] == 'Requiere atención: sobrepeso para su edad, alergia a penicilina, TDAH.'
    sano = indicadores.de_alumno({'salud': [dato('estado_general', 'Clínicamente sano'), dato('usa_lentes', 'sí'), dato('vacunas', 'Completo'),
                                            dato('agudeza_visual', 'Hipermetropía', 'por_confirmar')]}, 3, 'M', '2017-10-02', None, None, HOY)
    assert (sano['vista'], sano['vacunas'], sano['resumen']) == ('Usa lentes', 'Completas', 'Sano según el médico. Sin nada que atender. Usa lentes.')
    assert indicadores.de_alumno({}, 3, 'M', None, None, None, HOY)['resumen'] == 'Sin datos del certificado médico.'
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
    # La salud general del certificado sí (decisión del 26/10/2026); los signos del día y los datos del médico no.
    assert estandar.permitido('salud', 'peso') and estandar.permitido('salud', 'tipo_sangre') and estandar.permitido('salud', 'agudeza_visual')
    assert not estandar.permitido('salud', 'presion') and not estandar.permitido('salud', 'medico') and not estandar.permitido('salud', 'cedula')
    assert not estandar.permitido('escolar', 'inasistencias_2') and not estandar.permitido('tutor', 'ocupacion')
    registro = estandar.registro({'curp': 'XXXX171002HDFXXXA1', 'nombres': 'LUIS', 'primer_apellido': 'RAMOS', 'segundo_apellido': 'GIL',
                                  'fecha_nacimiento': datetime.date(2017, 10, 2), 'sexo': 'H', 'grado': 3, 'letra': 'A'},
                                 {'escolar': [dato('repite_grado', 'no')]}, '2026-2027', HOY)
    assert (registro['nombre'], registro['grupo'], registro['repite'], registro['fecha_nacimiento']) == ('RAMOS GIL LUIS', '3° A', 'no', '2017-10-02')
    assert [f['clave'] for f in estandar.faltan([registro])] == ['procedencia', 'beca', 'lengua_indigena', 'afro']
