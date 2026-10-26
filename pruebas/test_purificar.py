"""La purificación: de todo lo que dice una hoja, solo teléfonos, correos, contacto de emergencia y salud del alumno.

Todo es inventado (nombres, teléfonos y correos de prueba).
"""
from validacion import purificar

FICHA = """ESCUELA PRIMARIA DE PRUEBA  TEL. 55 5974 0000
FICHA DE INSCRIPCIÓN
Nombre del alumno: Ana López
DATOS DE LA MADRE
Nombre: Rosa Pérez
Celular: 55 1234 5678
Correo: rosa.perez @ gmail com
Padre: Juan López Tel. 5587654321 Correo juanl@hotmail.com
Teléfonos: 5511112222 (abuela), 5533334444 (tía)
Folio 5566778899
EN CASO DE EMERGENCIA
Nombre: María Pérez Ruiz
Parentesco: abuela
Tel: 044 55 9988 7766
Firma del padre o tutor
Dr. Luis Gómez Cédula 1234567 Tel 7225550000
"""


def test_los_telefonos_y_correos_salen_con_de_quien_son_y_sin_los_de_la_escuela_ni_del_medico():
    hallado = purificar.contactos(FICHA)
    assert hallado['telefonos'] == [
        {'valor': '5512345678', 'de': 'madre'},  # Bajo el título "Datos de la madre".
        {'valor': '5587654321', 'de': 'padre'},
        {'valor': '5511112222', 'de': 'emergencia'},  # "(abuela)" va después del número.
        {'valor': '5533334444', 'de': 'emergencia'},
        {'valor': '5599887766', 'de': 'emergencia'},  # Sin el 044.
    ]  # Ni el de la escuela, ni el folio (no dice "Tel."), ni el del médico.
    assert hallado['correos'] == [{'valor': 'rosa.perez@gmail.com', 'de': 'madre'}, {'valor': 'juanl@hotmail.com', 'de': 'padre'}]
    assert hallado['emergencia'] == [{'nombre': 'MARIA PEREZ RUIZ', 'parentesco': 'ABUELA'}]  # Y no "Firma del padre o tutor".


def test_el_contacto_de_emergencia_en_un_renglon_y_lo_que_contesta_el_modelo():
    renglon = purificar.contactos('En caso de emergencia avisar a: Rosa Hernández Díaz (tía) Tel. 722 123 4567')
    assert renglon['emergencia'] == [{'nombre': 'ROSA HERNANDEZ DIAZ', 'parentesco': 'TIA'}]
    assert renglon['telefonos'] == [{'valor': '7221234567', 'de': 'emergencia'}]
    # Lo que el modelo contesta a "¿qué teléfonos hay?" no trae "Tel.": se toma igual, menos un número que empieza con 800.
    respuesta = purificar.contactos('TELEFONOS: 7221234567 (mamá), 800 123 4567, 52 55 8765 4321 papá', exigir_etiqueta=False)
    assert respuesta['telefonos'] == [{'valor': '7221234567', 'de': 'madre'}, {'valor': '5587654321', 'de': 'padre'}]


CERTIFICADO = """[Hoja 1]
CERTIFICADO MÉDICO
Nombre del paciente: Ana López
Alergias: Sí [X] No [ ] ¿Cuál?: penicilina
¿Padece alguna enfermedad crónica? No
Medicamentos: ninguno
Diagnóstico nutricional: peso normal
[Hoja 2]
ANTECEDENTES HEREDOFAMILIARES:
Hipertensión [X] Diabetes [X] Cáncer [ ]
Enfermedad mental o nerviosa [X]
Antecedentes personales patológicos:
Asma [ ] Epilepsia [ ] Cardiopatía [ ]
Convulsiones: no
Diagnóstico: rinitis alérgica
Discapacidad o condición: [ ] Sí [X] No
"""


def test_la_salud_es_solo_del_alumno_ni_de_la_familia_ni_las_opciones_sin_marcar():
    assert purificar.salud(CERTIFICADO) == {
        'alergia': 'PENICILINA',  # Marcó "Sí" y escribió cuál.
        'padecimiento': 'RINITIS ALERGICA',  # La etiqueta manda: es un diagnóstico, aunque diga "alérgica".
        'medicamento': 'NINGUNA',
        'discapacidad': 'NINGUNA',  # "[X] No".
    }  # La hipertensión y la enfermedad mental son de la familia; asma y epilepsia no se marcaron.
    marcado = purificar.salud('Padecimientos: Asma [ ] Epilepsia [X] Otra [X] ¿Cuál?: soplo\nAlergias: polvo (igual que su mamá)')
    assert marcado == {'padecimiento': 'EPILEPSIA, SOPLO', 'alergia': 'POLVO'}
    assert purificar.salud('Alergias negadas\nEnfermedades de los padres: diabetes') == {'alergia': 'NINGUNA'}
    assert purificar.es_ninguno('NINGU NA') and purificar.es_ninguno('nin guno') and not purificar.es_ninguno('NINGUNA SALVO POLVO')
    assert purificar.es_grave('Hipertensión arterial') and purificar.es_grave('enfermedad nerviosa') and not purificar.es_grave('polvo')


def test_de_campos_llena_los_campos_de_la_plantilla_con_lo_transcrito():
    from validacion import campos
    lista = [campos.campo('telefono_madre', 'Teléfono de la madre', 'telefono', 'contacto', 'telefono', 'madre'),
             campos.campo('telefono_padre', 'Teléfono del padre', 'telefono', 'contacto', 'telefono', 'padre'),
             campos.campo('alergias', 'Alergias', 'lista', 'salud', 'alergia'),
             campos.campo('nombre_madre', 'Nombre de la madre', 'nombre', 'madre', 'nombre')]
    texto = 'Nombre de la madre: Rosa Pérez\nTeléfono de la madre: 55 1234 5678\nTeléfono del padre: 5587654321\nAlergias: ninguna'
    assert purificar.de_campos(texto, lista) == {'telefono_madre': '5512345678', 'telefono_padre': '5587654321', 'alergias': 'NINGUNA',
                                                 'nombre_madre': 'Rosa Pérez'}


def test_los_duplicados_de_la_maquina_se_marcan_y_lo_de_una_persona_nunca():
    def dato(id_, campo, valor, confianza='media', estado='vigente', quien='cerebro', categoria='salud'):
        return {'id': id_, 'categoria': categoria, 'campo': campo, 'valor': valor, 'confianza': confianza, 'estado': estado,
                'quien': quien, 'detalle': {}}
    filas = [
        dato(1, 'alergia', 'PENICILINA', 'confirmado', quien='secretaria'),
        dato(2, 'alergia', 'PENISILINA', 'baja', 'por_confirmar'),  # Casi igual a lo confirmado: sobra.
        dato(3, 'alergia', 'ALERGIA A LA PENICILINA'),  # La trae dentro: sobra.
        dato(4, 'alergia', 'NINGUNA'),  # Hay alergias de verdad: sobra.
        dato(5, 'alergia', 'POLVO'),
        dato(6, 'telefono', '7221234567', 'alta', categoria='contacto'),
        dato(7, 'telefono', '7221234561', 'baja', 'por_confirmar', categoria='contacto'),  # Un dígito distinto y dudoso: sobra.
        dato(8, 'telefono', '7221234560', 'media', categoria='contacto'),  # Un dígito distinto pero seguro: puede ser otro.
        dato(9, 'padecimiento', 'ASMA', 'confirmado', quien='directora'),
        dato(10, 'padecimiento', 'ASMA', 'confirmado', quien='secretaria'),  # Las dos las escribió una persona: no se tocan.
    ]
    assert sorted(purificar.duplicados(filas)) == [(2, 1), (3, 1), (4, 1), (7, 6)]
