"""El estándar de datos de cada alumno: lo que pide el gobierno (911.3, control escolar, SAID, becas) y nada más.

Cada alumno tiene el mismo conjunto fijo de datos, con los catálogos del gobierno. El escaneo solo guarda lo que está
aquí (taller.py pregunta `permitido`); lo que ya estaba guardado de antes no se borra, pero ya no sale en el Excel,
en el estudio ni en los documentos. De dónde sale cada dato y para qué lo pide el gobierno:
docs/investigacion/gobierno_y_estandar.md.

Salud: el 23 de octubre de 2026 se decidió «Solo lo necesario» (discapacidad o condición para el 911, alergias,
medicamentos, padecimientos y contacto de emergencia). El 26 de octubre Maximiliano lo cambió: quiere saber el estado
de salud general de cada alumno, con lo que trae el certificado médico (peso, estatura, tipo de sangre, vista, oído,
dientes, vacunas, educación física, lo que concluyó el médico y sus recomendaciones). El Metadato de la supervisión
pide varios de ellos (tipo de sangre, peso, talla, lentes, servicio médico, vacunación). Signos vitales del día (presión,
temperatura, frecuencia), el nombre del médico y su cédula no se guardan.

Quién gana cuando dos documentos dicen cosas distintas: lo que escribió o confirmó una persona; luego la fuente con
más prioridad (RENAPO > acta > CURP > lista oficial > boleta > ficha de la escuela); luego la más segura; luego la
más nueva. Los datos sensibles (S) siempre los confirma una persona.
"""
import datetime
import re

from validacion import indicadores

SI_NO = {'sí': 'Sí', 'no': 'No'}
SEXO = {'H': 'Hombre', 'M': 'Mujer', 'X': 'No binario (X)'}
# 911.3, sección II: de dónde viene el alumno que llegó este ciclo.
PROCEDENCIA = {
    'misma': 'Ya estaba en esta escuela o entra a 1.°',
    'otra_edomex': 'Viene de otra escuela del Estado de México',
    'otra_entidad': 'Viene de una escuela de otro estado',
    'otro_pais': 'Viene de una escuela de otro país',
}
# 911.3, sección III: beca en dinero; si tiene varias, la de mayor monto.
BECA = {
    'ninguna': 'Sin beca', 'federal': 'Federal (por ejemplo, Rita Cetina)', 'estatal': 'Estatal', 'municipal': 'Municipal',
    'fundacion': 'Fundación o asociación civil', 'escuela': 'De la propia escuela', 'particular': 'Particular', 'otro': 'Otra',
}
PARENTESCO = {'madre': 'Madre', 'padre': 'Padre', 'tutor_legal': 'Tutor legal', 'abuelo': 'Abuelo o abuela', 'otro': 'Otro familiar'}
CONDICIONES_911 = tuple(nombre for nombre, _ in indicadores.DISCAPACIDAD_911) + (indicadores.OTRAS_CONDICIONES,)


def dato(clave, etiqueta, categoria, campo, para, captura, catalogo=None, sensible=False, varios=False):
    return {'clave': clave, 'etiqueta': etiqueta, 'categoria': categoria, 'campo': campo, 'para': para, 'captura': captura,
            'catalogo': catalogo, 'sensible': sensible, 'varios': varios}


# captura: 'lista' (lista oficial y RENAPO), 'documento' (lo saca el escaneo), 'persona' (lo pone la escuela en SIDP).
DICCIONARIO = (
    # Identidad: la lista oficial y RENAPO; el acta y la CURP lo confirman (no se guarda otra vez en sidp.dato).
    dato('curp', 'CURP', 'alumno', 'curp', ('911', 'Control escolar', 'SAID', 'Beca'), 'lista'),
    dato('nombre', 'Nombre completo', 'alumno', 'nombre', ('Control escolar', 'SAID'), 'lista'),
    dato('fecha_nacimiento', 'Fecha de nacimiento', 'alumno', 'fecha_nacimiento', ('911', 'Control escolar'), 'lista'),
    dato('sexo', 'Sexo', 'alumno', 'sexo', ('911', 'Control escolar'), 'lista', SEXO),
    dato('lugar_nacimiento', 'Lugar de nacimiento', 'alumno', 'lugar_nacimiento', ('911',), 'documento'),
    # Para el 911: lo pone la escuela (no viene en ningún documento).
    dato('repite_grado', '¿Repite el grado?', 'escolar', 'repite_grado', ('911',), 'persona', SI_NO),
    dato('procedencia', '¿De dónde viene?', 'escolar', 'procedencia', ('911',), 'persona', PROCEDENCIA),
    dato('beca', 'Beca en dinero', 'escolar', 'beca', ('911',), 'persona', BECA),
    dato('lengua_indigena', '¿Habla una lengua indígena?', 'alumno', 'lengua_indigena', ('911',), 'persona', SI_NO, sensible=True),
    dato('lengua', 'Cuál lengua indígena', 'alumno', 'lengua', ('911',), 'persona', sensible=True),
    dato('afrodescendiente', '¿Se considera afromexicano o afrodescendiente?', 'alumno', 'afrodescendiente', ('911',), 'persona', SI_NO,
         sensible=True),
    dato('discapacidad', 'Discapacidad o condición', 'salud', 'discapacidad', ('911',), 'documento', sensible=True, varios=True),
    # Lo que hay que cuidar en la escuela.
    dato('alergias', 'Alergias', 'salud', 'alergia', ('Escuela',), 'documento', sensible=True, varios=True),
    dato('padecimientos', 'Padecimientos', 'salud', 'padecimiento', ('Escuela',), 'documento', sensible=True, varios=True),
    dato('medicamentos', 'Medicamentos', 'salud', 'medicamento', ('Escuela',), 'documento', sensible=True, varios=True),
    # Salud general del certificado médico (decisión del 26 de octubre de 2026): cómo está el alumno, para la escuela y el Metadato.
    dato('peso', 'Peso (kg)', 'salud', 'peso', ('Metadato', 'Escuela'), 'documento', sensible=True),
    dato('talla', 'Estatura (m)', 'salud', 'talla', ('Metadato', 'Escuela'), 'documento', sensible=True),
    dato('tipo_sangre', 'Tipo de sangre', 'salud', 'tipo_sangre', ('Metadato', 'Escuela'), 'documento', sensible=True),
    dato('estado_nutricional', 'Estado nutricional (lo que anotó el médico)', 'salud', 'estado_nutricional', ('Escuela',), 'documento',
         sensible=True),
    dato('agudeza_visual', 'Vista (agudeza visual)', 'salud', 'agudeza_visual', ('Escuela',), 'documento', sensible=True),
    dato('usa_lentes', '¿Usa lentes?', 'salud', 'usa_lentes', ('Metadato',), 'documento', SI_NO, sensible=True),
    dato('audicion', 'Audición', 'salud', 'audicion', ('Metadato', 'Escuela'), 'documento', sensible=True),
    dato('salud_bucal', 'Salud bucal', 'salud', 'salud_bucal', ('Escuela',), 'documento', sensible=True),
    dato('vacunas', 'Esquema de vacunación', 'salud', 'vacunas', ('Metadato',), 'documento', sensible=True),
    dato('educacion_fisica', 'Educación física', 'salud', 'educacion_fisica', ('Escuela',), 'documento', sensible=True),
    dato('estado_general', 'Estado de salud general (según el médico)', 'salud', 'estado_general', ('Escuela',), 'documento', sensible=True),
    dato('recomendaciones', 'Recomendaciones del médico', 'salud', 'recomendaciones', ('Escuela',), 'documento', sensible=True),
    dato('servicio_medico', 'Servicio médico (IMSS, ISSSTE...)', 'salud', 'servicio_medico', ('Metadato',), 'documento', sensible=True),
    dato('fecha_certificado', 'Fecha del certificado médico', 'salud', 'fecha_certificado', ('Metadato',), 'documento', sensible=True),
    # Tutores y contacto: control escolar, SAID y avisos.
    dato('madre_nombre', 'Nombre de la madre', 'madre', 'nombre', ('Control escolar',), 'documento'),
    dato('madre_curp', 'CURP de la madre', 'madre', 'curp', ('SAID',), 'documento'),
    dato('padre_nombre', 'Nombre del padre', 'padre', 'nombre', ('Control escolar',), 'documento'),
    dato('padre_curp', 'CURP del padre', 'padre', 'curp', ('SAID',), 'documento'),
    dato('tutor_nombre', 'Nombre del tutor', 'tutor', 'nombre', ('Control escolar', 'SAID'), 'documento'),
    dato('tutor_curp', 'CURP del tutor', 'tutor', 'curp', ('SAID', 'Beca'), 'documento'),
    dato('tutor_parentesco', 'Parentesco del tutor', 'tutor', 'parentesco', ('Control escolar',), 'persona', PARENTESCO),
    dato('telefono', 'Teléfono', 'contacto', 'telefono', ('Control escolar',), 'documento', varios=True),
    dato('correo', 'Correo electrónico', 'contacto', 'correo', ('SAID',), 'documento', varios=True),
    dato('emergencia', 'Contacto de emergencia', 'contacto', 'nombre_emergencia', ('Escuela',), 'documento'),
    # Domicilio: control escolar y el estudio de dónde viven los alumnos (911 no lo pide).
    dato('domicilio', 'Domicilio', 'domicilio', 'domicilio', ('Control escolar',), 'documento'),
    dato('colonia', 'Colonia', 'domicilio', 'colonia', ('Control escolar',), 'documento'),
    dato('municipio', 'Municipio', 'domicilio', 'municipio', ('Control escolar',), 'documento'),
    dato('cp', 'Código postal', 'domicilio', 'cp', ('Control escolar',), 'documento'),
)
# Las boletas de años anteriores: un dato por cada grado cursado (promedio_3 es la boleta de 3.°).
BOLETA = ('ciclo_boleta', 'promedio', 'lenguajes', 'saberes', 'etica', 'humano', 'escuela_procedencia', 'cct_procedencia')
PERMITIDOS = {(d['categoria'], d['campo']) for d in DICCIONARIO}
POR_CLAVE = {d['clave']: d for d in DICCIONARIO}


def permitido(categoria, campo):
    """¿Este dato es del estándar? Lo que no lo es no se guarda (los documentos traen mucho más de lo que hace falta)."""
    if (categoria, campo) in PERMITIDOS:
        return True
    hallado = re.fullmatch(r'([a-z_]+?)(?:_([1-6]))?', campo or '')
    return categoria == 'escolar' and bool(hallado) and hallado[1] in BOLETA


# ---------------------------------------------------------------- El registro estándar de cada alumno

def registro(alumno, datos, ciclo=None, hoy=None):
    """Todos los datos estándar de un alumno, ya limpios y con catálogo.

    alumno: {curp, nombres, primer_apellido, segundo_apellido, fecha_nacimiento, sexo, grado, letra} (lista oficial).
    datos: {categoria: [{'campo', 'valor', 'detalle', 'estado'}]} de sidp.dato (puede faltar).
    Lleva nombre y CURP: sirve para los documentos de la escuela. Para contar, indicadores.de_alumno no los lleva.
    """
    hoy = hoy or datetime.date.today()
    nacimiento = alumno.get('fecha_nacimiento')
    nacimiento = nacimiento.isoformat() if hasattr(nacimiento, 'isoformat') else nacimiento
    cuenta = indicadores.de_alumno(datos, alumno.get('grado'), alumno.get('sexo'), nacimiento, alumno.get('curp'), ciclo, hoy)
    uno = lambda categoria, campo: indicadores._uno(datos, categoria, campo)  # noqa: E731
    nombre = ' '.join(filter(None, (alumno.get('primer_apellido'), alumno.get('segundo_apellido'), alumno.get('nombres'))))
    telefonos = indicadores.valores_de(datos, 'contacto', 'telefono')
    return {
        **cuenta,
        'curp': alumno.get('curp') or '', 'nombre': nombre, 'nombres': alumno.get('nombres') or '',
        'primer_apellido': alumno.get('primer_apellido') or '', 'segundo_apellido': alumno.get('segundo_apellido') or '',
        'fecha_nacimiento': nacimiento, 'sexo_curp': alumno.get('sexo') or '', 'letra': alumno.get('letra') or '',
        'grupo': f'{int(alumno["grado"])}° {alumno.get("letra") or ""}'.strip() if alumno.get('grado') else 'Sin grupo',
        'tutor': uno('tutor', 'nombre') or uno('madre', 'nombre') or uno('padre', 'nombre'),
        'parentesco': (PARENTESCO.get(uno('tutor', 'parentesco'), uno('tutor', 'parentesco')) if uno('tutor', 'nombre')
                       else 'Madre' if uno('madre', 'nombre') else 'Padre' if uno('padre', 'nombre') else None),
        'tutor_curp': uno('tutor', 'curp') or uno('madre', 'curp') or uno('padre', 'curp'),
        'telefono': telefonos[-1] if telefonos else None, 'emergencia': uno('contacto', 'nombre_emergencia'),
        'correo': (indicadores.valores_de(datos, 'contacto', 'correo') or [None])[-1],
        'domicilio': uno('domicilio', 'domicilio'),
    }


def registros(base, ciclo=None, hoy=None):
    """El registro estándar de cada alumno inscrito en la base de la PC 4 (lo usa el motor de documentos)."""
    ciclo = ciclo or base._uno('SELECT max(ciclo) FROM sidp.v_inscritos')
    if not ciclo:
        return ciclo, []
    datos = {}
    for alumno_id, categoria, campo, valor, detalle, estado in base._consulta(
            "SELECT d.alumno_id, d.categoria, d.campo, d.valor, d.detalle, d.estado FROM sidp.dato d "
            "JOIN sidp.v_inscritos i ON i.id = d.alumno_id AND i.ciclo = %s WHERE d.estado IN ('vigente', 'por_confirmar') ORDER BY d.id",
            (ciclo,)):
        datos.setdefault(alumno_id, {}).setdefault(categoria, []).append({'campo': campo, 'valor': valor, 'detalle': detalle, 'estado': estado})
    salida = []
    for fila in base._consulta('SELECT id, curp, nombres, primer_apellido, segundo_apellido, fecha_nacimiento, sexo, grado, letra '
                               'FROM sidp.v_inscritos WHERE ciclo = %s ORDER BY grado, letra, primer_apellido, segundo_apellido, nombres',
                               (ciclo,)):
        alumno = dict(zip(('id', 'curp', 'nombres', 'primer_apellido', 'segundo_apellido', 'fecha_nacimiento', 'sexo', 'grado', 'letra'), fila))
        salida.append({**registro(alumno, datos.get(alumno['id']), ciclo, hoy), 'id': alumno['id']})
    return ciclo, salida


# Lo que necesita el 911 de cada alumno, y cómo se completa si falta.
PARA_911 = (
    ('fecha_nacimiento', 'fecha de nacimiento', 'Se llena sola con la CURP o con el acta escaneada.', 'listas'),
    ('sexo_curp', 'sexo', 'Se llena solo con la CURP.', 'listas'),
    ('repite', 'el dato de «¿Repite el grado?»', 'Ponlo en «Completar datos del 911», abajo.', None),
    ('procedencia', 'el dato de «¿De dónde viene?»', 'Ponlo en «Completar datos del 911», abajo.', None),
    ('beca', 'el dato de la beca', 'Ponlo en «Completar datos del 911», abajo.', None),
    ('lengua_indigena', 'el dato de lengua indígena', 'Ponlo en «Completar datos del 911», abajo.', None),
    ('afro', 'el dato de afromexicano', 'Ponlo en «Completar datos del 911», abajo.', None),
)


def faltan(lista):
    """Cuántos alumnos no tienen cada dato que pide el 911 (sin nombres: los nombres van en la hoja «Faltan» del Excel)."""
    salida = []
    for clave, nombre, como, ir in PARA_911:
        cuantos = sum(1 for r in lista if r.get(clave) in (None, ''))
        if cuantos:
            salida.append({'dato': nombre, 'alumnos': cuantos, 'como': como, 'ir': ir, 'clave': clave})
    return salida


# «Completar datos del 911» (Formatos oficiales): lo que la escuela anota de cada alumno de un grupo.
# (clave en el registro, clave del diccionario)
COMPLETAR_911 = (('repite', 'repite_grado'), ('procedencia', 'procedencia'), ('beca', 'beca'), ('lengua_indigena', 'lengua_indigena'),
                 ('lengua', 'lengua'), ('afro', 'afrodescendiente'))
PARA_COMPLETAR = ('curp', 'nombre', 'grupo', 'grado', 'letra') + tuple(clave for clave, _ in COMPLETAR_911)


def columnas_911():
    return [{'clave': clave, 'etiqueta': POR_CLAVE[d]['etiqueta'], 'categoria': POR_CLAVE[d]['categoria'], 'campo': POR_CLAVE[d]['campo'],
             'opciones': POR_CLAVE[d]['catalogo']} for clave, d in COMPLETAR_911]


def valor_de(categoria, campo, valor):
    """El valor con el catálogo del gobierno (sí o no, tipo de beca...), o ValueError si no es una de las opciones."""
    texto = ' '.join(str(valor or '').split())
    entrada = next((d for d in DICCIONARIO if (d['categoria'], d['campo']) == (categoria, campo)), None)
    if not entrada or not entrada['catalogo'] or entrada['catalogo'] is SEXO:
        return texto
    if entrada['catalogo'] is SI_NO:
        elegido = indicadores.si_no(texto)
    else:
        textos = {indicadores.normal(v): k for k, v in entrada['catalogo'].items()}
        elegido = indicadores.clave(texto, entrada['catalogo']) or textos.get(indicadores.normal(texto))
    if not elegido:
        raise ValueError(f'«{texto}» no es una de las opciones de «{entrada["etiqueta"]}»: ' + ', '.join(entrada['catalogo'].values()))
    return elegido
