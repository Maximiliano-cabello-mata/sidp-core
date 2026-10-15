"""Los procedimientos de Maximiliano, traducidos a Python, respetan las reglas del diseño integral."""
import json
import sqlite3
import uuid
from pathlib import Path
import pytest
from database.procedimientos import (
    ProcedimientoError, procesar_expediente_extraido, sp_asignar_tutor, sp_baja_alumno, sp_cancelardocumentoemitido,
    sp_capturar_calificacion, sp_finalizar_lote_importacion, sp_inscribir_alumno, sp_inventario,
    sp_publicarversionformato, sp_reemplazardocumento, sp_revisardocumento, sp_siguenteciclo, sp_solicitudtutor)

DISENO = Path(__file__).resolve().parent.parent / 'database' / 'diseno_integral.sql'
HOY = '2026-10-13'
CURP = 'GOMA150101HMCRRNA5'
OTRA_CURP = 'LOPE160202MMCPRRA1'


def uid():
    return str(uuid.uuid4())


@pytest.fixture
def db():
    conexion = sqlite3.connect(':memory:', isolation_level=None)
    conexion.executescript(DISENO.read_text(encoding='utf-8'))
    conexion.execute('PRAGMA foreign_keys=ON')
    return conexion


@pytest.fixture
def escuela(db):
    """Un ciclo con su periodo, un grupo, un alumno inscrito y un usuario docente."""
    ids = {k: uid() for k in ('ciclo', 'periodo', 'personal', 'usuario', 'grupo', 'alumno', 'inscripcion')}
    db.execute("INSERT INTO ciclo(id,nombre,inicio,fin) VALUES(?,?,?,?)", (ids['ciclo'], '2026-2027', '2026-08-31', '2027-07-15'))
    db.execute("INSERT INTO periodo(id,ciclo_id,numero,inicio,fin) VALUES(?,?,1,'2026-08-31','2026-11-27')", (ids['periodo'], ids['ciclo']))
    db.execute("INSERT INTO personal(id,nombres,primer_apellido,puesto) VALUES(?,'Ana','Ruiz','docente')", (ids['personal'],))
    db.execute("INSERT INTO usuario(id,personal_id,nombre_usuario,contrasena_resumen,rol) VALUES(?,?,'ana','x','docente')",
               (ids['usuario'], ids['personal']))
    db.execute("INSERT INTO grupo(id,ciclo_id,grado,letra,docente_id) VALUES(?,?,3,'A',?)", (ids['grupo'], ids['ciclo'], ids['personal']))
    db.execute("INSERT INTO alumno(id,curp,nombres,primer_apellido) VALUES(?,?,'Juan','Gómez')", (ids['alumno'], CURP))
    db.execute("INSERT INTO inscripcion(id,alumno_id,ciclo_id,grupo_id,tipo,alta) VALUES(?,?,?,?,'reinscripcion',?)",
               (ids['inscripcion'], ids['alumno'], ids['ciclo'], ids['grupo'], HOY))
    return ids


def valor(db, sql, parametros=()):
    return db.execute(sql, parametros).fetchone()[0]


def bitacora(db, accion):
    return [{'actor': a, 'objeto_id': o, 'antes': json.loads(x) if x else None, 'despues': json.loads(y) if y else None}
            for a, o, x, y in db.execute('SELECT actor, objeto_id, antes, despues FROM bitacora WHERE accion = ? '
                                         'ORDER BY secuencia', (accion,))]


def falla(texto, funcion, *argumentos, **opciones):
    with pytest.raises(ProcedimientoError, match=texto):
        funcion(*argumentos, **opciones)


def archivo(db, letra, tipo='application/pdf'):
    sha = letra * 64
    db.execute('INSERT INTO archivo(sha256,tamano,tipo_mime,ruta_relativa,creado) VALUES(?,100,?,?,?)',
               (sha, tipo, f'{letra}{letra}/{letra}.pdf', HOY))
    return sha


def documento(db, alumno_id, sha, tipo='acta'):
    doc = uid()
    db.execute("INSERT INTO documento(id,tipo,alumno_id,archivo_sha256,origen,recibido) VALUES(?,?,?,?,'buzon',?)",
               (doc, tipo, alumno_id, sha, HOY))
    return doc


def alumno(db, curp=None, nombre='Luisa'):
    nuevo = uid()
    db.execute("INSERT INTO alumno(id,curp,nombres,primer_apellido) VALUES(?,?,?,'López')", (nuevo, curp, nombre))
    return nuevo


def tutor(db, telefono='5550000000'):
    nuevo = uid()
    db.execute("INSERT INTO tutor(id,nombres,primer_apellido,telefono) VALUES(?,'Rosa','Gómez',?)", (nuevo, telefono))
    return nuevo


# ------------------------------------------------------------ sp_revisardocumento

def test_validar_documento(db, escuela):
    doc = documento(db, escuela['alumno'], archivo(db, 'a'))
    sp_revisardocumento(db, doc, 'validado', escuela['usuario'], version=1)
    assert db.execute('SELECT estado, version FROM documento WHERE id=?', (doc,)).fetchone() == ('validado', 2)
    assert valor(db, 'SELECT reviso FROM revision_documento WHERE documento_id=?', (doc,)) == escuela['usuario']
    assert bitacora(db, 'documento.revisado')[0]['antes']['estado'] == 'recibido'


def test_rechazo_sin_motivo_no_cambia_nada(db, escuela):
    doc = documento(db, escuela['alumno'], archivo(db, 'a'))
    falla('motivo del rechazo', sp_revisardocumento, db, doc, 'rechazado', escuela['usuario'], 1, '  ')
    assert not db.in_transaction
    assert valor(db, 'SELECT estado FROM documento WHERE id=?', (doc,)) == 'recibido'
    assert valor(db, 'SELECT COUNT(*) FROM revision_documento') == 0
    sp_revisardocumento(db, doc, 'rechazado', escuela['usuario'], 1, 'Ilegible')
    assert valor(db, 'SELECT motivo_rechazo FROM documento WHERE id=?', (doc,)) == 'Ilegible'


def test_revision_con_version_vieja_o_sin_persona(db, escuela):
    doc = documento(db, escuela['alumno'], archivo(db, 'a'))
    sp_revisardocumento(db, doc, 'validado', escuela['usuario'], 1)
    falla('cambió, vuelva a cargarlo', sp_revisardocumento, db, doc, 'rechazado', escuela['usuario'], 1, 'Borroso')
    falla('usuario registrado', sp_revisardocumento, db, doc, 'rechazado', 'cerebro', 2, 'Borroso')


# ------------------------------------------------------------ sp_solicitudtutor

def solicitud(db, tutor_id, campo='telefono', valor_nuevo='5551112222'):
    nueva = uid()
    db.execute('INSERT INTO solicitud_cambio(id,tutor_id,campo,valor_nuevo,fecha) VALUES(?,?,?,?,?)',
               (nueva, tutor_id, campo, valor_nuevo, HOY))
    return nueva


def test_aprobar_solicitud_guarda_valor_anterior(db, escuela):
    t = tutor(db)
    s = solicitud(db, t)
    sp_solicitudtutor(db, s, 'aprobada', escuela['usuario'], version=1)
    assert db.execute('SELECT telefono, version FROM tutor WHERE id=?', (t,)).fetchone() == ('5551112222', 2)
    assert db.execute('SELECT estado, reviso FROM solicitud_cambio WHERE id=?', (s,)).fetchone() == ('aprobada', escuela['usuario'])
    assert bitacora(db, 'tutor.contacto_cambiado')[0]['antes'] == {'telefono': '5550000000'}
    falla('no se encuentra pendiente', sp_solicitudtutor, db, s, 'aprobada', escuela['usuario'], 2)


def test_rechazar_solicitud_exige_motivo(db, escuela):
    t = tutor(db)
    s = solicitud(db, t, 'correo', 'rosa@ejemplo.mx')
    falla('motivo', sp_solicitudtutor, db, s, 'rechazada', escuela['usuario'], 1)
    sp_solicitudtutor(db, s, 'rechazada', escuela['usuario'], 1, motivo='No coincide con la INE')
    assert valor(db, 'SELECT correo FROM tutor WHERE id=?', (t,)) is None
    assert bitacora(db, 'solicitud_cambio.rechazada')[0]['despues']['motivo'] == 'No coincide con la INE'


def test_solicitud_con_tutor_cambiado(db, escuela):
    t = tutor(db)
    s = solicitud(db, t)
    db.execute("UPDATE tutor SET domicilio='Centro', version=version+1 WHERE id=?", (t,))
    falla('El tutor cambió', sp_solicitudtutor, db, s, 'aprobada', escuela['usuario'], 1)
    assert valor(db, 'SELECT estado FROM solicitud_cambio WHERE id=?', (s,)) == 'pendiente'


# ------------------------------------------------------------ sp_inventario

def bien(db):
    nuevo = uid()
    db.execute("INSERT INTO bien(id,descripcion,categoria,ubicacion,alta) VALUES(?,'Proyector','computo','Dirección',?)", (nuevo, HOY))
    return nuevo


def test_movimiento_de_inventario(db, escuela):
    b = bien(db)
    sp_inventario(db, b, 'cambio_ubicacion', 'Se presta al aula 3', escuela['usuario'], 1, nueva_ubicacion='Aula 3')
    assert db.execute('SELECT ubicacion, estado, version FROM bien WHERE id=?', (b,)).fetchone() == ('Aula 3', 'bueno', 2)
    assert valor(db, 'SELECT tipo FROM bien_movimiento WHERE bien_id=?', (b,)) == 'cambio_ubicacion'
    assert bitacora(db, 'bien.cambio_ubicacion')[0]['antes']['ubicacion'] == 'Dirección'
    falla('El bien cambió', sp_inventario, db, b, 'cambio_estado', 'Golpe', escuela['usuario'], 1, nuevo_estado='malo')


def test_baja_de_bien_lo_cierra(db, escuela):
    b = bien(db)
    sp_inventario(db, b, 'baja', 'Lámpara fundida sin refacción', escuela['usuario'], 1)
    assert valor(db, 'SELECT estado FROM bien WHERE id=?', (b,)) == 'baja'
    falla('ya está dado de baja', sp_inventario, db, b, 'cambio_ubicacion', 'x', escuela['usuario'], 2, nueva_ubicacion='Bodega')


# ------------------------------------------------------------ sp_siguenteciclo

def ciclo_siguiente(db, estado='preparacion'):
    ciclo, grupo = uid(), uid()
    db.execute("INSERT INTO ciclo(id,nombre,inicio,fin,estado) VALUES(?,'2027-2028','2027-08-30','2028-07-14',?)", (ciclo, estado))
    db.execute("INSERT INTO grupo(id,ciclo_id,grado,letra) VALUES(?,?,4,'A')", (grupo, ciclo))
    return ciclo, grupo


def test_promocion_masiva(db, escuela):
    db.execute("UPDATE inscripcion SET estado='completa', version=version+1 WHERE id=?", (escuela['inscripcion'],))
    otro = alumno(db)
    db.execute("INSERT INTO inscripcion(id,alumno_id,ciclo_id,grupo_id,tipo,alta) VALUES(?,?,?,?,'nuevo_ingreso',?)",
               (uid(), otro, escuela['ciclo'], escuela['grupo'], HOY))  # incompleta: no se promueve
    ciclo, grupo = ciclo_siguiente(db)
    assert sp_siguenteciclo(db, escuela['grupo'], grupo, ciclo, escuela['usuario']) == 1
    assert db.execute('SELECT alumno_id, tipo, estado FROM inscripcion WHERE ciclo_id=?', (ciclo,)).fetchall() == [
        (escuela['alumno'], 'reinscripcion', 'incompleta')]
    assert len(bitacora(db, 'inscripcion.reinscrita')) == 1
    assert sp_siguenteciclo(db, escuela['grupo'], grupo, ciclo, escuela['usuario']) == 0


def test_promocion_a_ciclo_cerrado_o_grupo_ajeno(db, escuela):
    ciclo, grupo = ciclo_siguiente(db, 'cerrado')
    falla('está cerrado', sp_siguenteciclo, db, escuela['grupo'], grupo, ciclo, escuela['usuario'])
    falla('no pertenece', sp_siguenteciclo, db, escuela['grupo'], grupo, escuela['ciclo'], escuela['usuario'])


# ------------------------------------------------------------ sp_publicarversionformato

def formato(db, version, estado, sha):
    nuevo = uid()
    db.execute("INSERT INTO formato(id,nombre,emisor,version,plantilla_sha256,estado) VALUES(?,'Constancia','escuela',?,?,?)",
               (nuevo, version, sha, estado))
    return nuevo


def test_publicar_version_retira_la_anterior(db, escuela):
    sha = archivo(db, 'f')
    v1, v2 = formato(db, 1, 'vigente', sha), formato(db, 2, 'borrador', sha)
    sp_publicarversionformato(db, v2, escuela['usuario'])
    assert dict(db.execute('SELECT id, estado FROM formato').fetchall()) == {v1: 'retirado', v2: 'vigente'}
    assert bitacora(db, 'formato.retirado')[0]['objeto_id'] == v1
    falla('Solo se publica un formato en borrador', sp_publicarversionformato, db, v1, escuela['usuario'])


# ------------------------------------------------------------ sp_cancelardocumentoemitido

def test_cancelar_documento_emitido(db, escuela):
    sha = archivo(db, 'e')
    f = formato(db, 1, 'vigente', sha)
    db.execute("INSERT INTO documento_emitido(folio,formato_id,alumno_id,archivo_sha256,datos,emitio,fecha) "
               "VALUES('CONST-2026-1',?,?,?,'{}',?,?)", (f, escuela['alumno'], sha, escuela['usuario'], HOY))
    falla('motivo', sp_cancelardocumentoemitido, db, 'CONST-2026-1', '', escuela['usuario'])
    sp_cancelardocumentoemitido(db, 'CONST-2026-1', 'Nombre mal escrito', escuela['usuario'])
    assert valor(db, "SELECT estado FROM documento_emitido") == 'cancelado'
    nota = bitacora(db, 'documento_emitido.cancelado')[0]
    assert (nota['actor'], nota['despues']['motivo']) == (escuela['usuario'], 'Nombre mal escrito')
    falla('ya fue cancelado', sp_cancelardocumentoemitido, db, 'CONST-2026-1', 'Otra vez', escuela['usuario'])


# ------------------------------------------------------------ sp_finalizar_lote_importacion

def importacion(db, escuela, letra):
    nueva = uid()
    db.execute("INSERT INTO importacion(id,archivo_sha256,tipo,estado,actor,fecha) VALUES(?,?,'said','revisando',?,?)",
               (nueva, archivo(db, letra), escuela['usuario'], HOY))
    return nueva


def test_finalizar_importacion(db, escuela):
    aplicada, vacia = importacion(db, escuela, '1'), importacion(db, escuela, '2')
    falla('entre cero', sp_finalizar_lote_importacion, db, aplicada, 3, 5, escuela['usuario'])
    sp_finalizar_lote_importacion(db, aplicada, 10, 9, escuela['usuario'], errores=[{'fila': 4, 'error': 'CURP'}])
    sp_finalizar_lote_importacion(db, vacia, 2, 0, escuela['usuario'])
    assert db.execute('SELECT estado, errores FROM importacion WHERE id=?', (aplicada,)).fetchone() == (
        'aplicada', '[{"fila": 4, "error": "CURP"}]')
    assert valor(db, 'SELECT estado FROM importacion WHERE id=?', (vacia,)) == 'descartada'
    assert bitacora(db, 'importacion.aplicada')[0]['antes']['estado'] == 'revisando'
    falla('ya fue procesada', sp_finalizar_lote_importacion, db, aplicada, 10, 9, escuela['usuario'])


# ------------------------------------------------------------ sp_reemplazardocumento

def test_reemplazar_documento(db, escuela):
    doc = documento(db, escuela['alumno'], archivo(db, 'a'))
    nuevo_sha = archivo(db, 'b')
    falla('no está registrado', sp_reemplazardocumento, db, doc, 'c' * 64, escuela['usuario'], 1)
    falla('cambió', sp_reemplazardocumento, db, doc, nuevo_sha, escuela['usuario'], 7)
    nuevo = sp_reemplazardocumento(db, doc, nuevo_sha, escuela['usuario'], 1)
    assert db.execute('SELECT estado, version FROM documento WHERE id=?', (doc,)).fetchone() == ('reemplazado', 2)
    assert db.execute('SELECT estado, reemplaza_a, tipo FROM documento WHERE id=?', (nuevo,)).fetchone() == ('recibido', doc, 'acta')
    falla('ya fue reemplazado', sp_reemplazardocumento, db, doc, archivo(db, 'd'), escuela['usuario'], 2)


# ------------------------------------------------------------ procesar_expediente_extraido

def test_datos_extraidos_solo_proponen(db, escuela):
    sin_curp = alumno(db)
    sha = archivo(db, 'a')
    r = procesar_expediente_extraido(db, sin_curp, 'curp', sha, {'curp_encontrada': ' lope160202mmcprra1 '}, escuela['usuario'])
    assert db.execute('SELECT curp, curp_confirmada, version FROM alumno WHERE id=?', (sin_curp,)).fetchone() == (None, 0, 1)
    assert valor(db, 'SELECT estado FROM documento WHERE id=?', (r['documento_id'],)) == 'recibido'
    tipo, objeto, estado, contenido = db.execute(
        'SELECT tipo, objeto_id, estado, contenido FROM sugerencia_ia WHERE id=?', (r['sugerencia_id'],)).fetchone()
    assert (tipo, objeto, estado) == ('validacion', r['documento_id'], 'propuesta')
    assert json.loads(contenido)['curp_propuesta'] == OTRA_CURP
    falla('ya fue registrado', procesar_expediente_extraido, db, sin_curp, 'curp', sha, {}, escuela['usuario'])


def test_curp_de_otro_alumno_queda_como_aviso(db, escuela):
    sin_curp = alumno(db)
    r = procesar_expediente_extraido(db, sin_curp, 'acta', archivo(db, 'a'), json.dumps({'curp_encontrada': CURP}),
                                     escuela['usuario'])
    contenido = json.loads(valor(db, 'SELECT contenido FROM sugerencia_ia WHERE id=?', (r['sugerencia_id'],)))
    assert 'ya pertenece a otro alumno' in contenido['avisos'][0]
    assert valor(db, 'SELECT curp FROM alumno WHERE id=?', (sin_curp,)) is None


# ------------------------------------------------------------ sp_inscribir_alumno

def test_inscripcion_nueva_empieza_incompleta(db, escuela):
    nuevo = alumno(db)
    inscripcion = sp_inscribir_alumno(db, nuevo, escuela['ciclo'], escuela['grupo'], 'nuevo_ingreso', escuela['usuario'])
    assert valor(db, 'SELECT estado FROM inscripcion WHERE id=?', (inscripcion,)) == 'incompleta'
    assert bitacora(db, 'inscripcion.alta')[0]['despues']['alumno_id'] == nuevo
    falla('ya tiene una inscripción', sp_inscribir_alumno, db, nuevo, escuela['ciclo'], escuela['grupo'], 'nuevo_ingreso',
          escuela['usuario'])


def test_no_se_inscribe_en_ciclo_cerrado_ni_alumno_inactivo(db, escuela):
    ciclo, grupo = ciclo_siguiente(db, 'cerrado')
    falla('ciclo escolar está cerrado', sp_inscribir_alumno, db, alumno(db), ciclo, grupo, 'traslado', escuela['usuario'])
    egresado = alumno(db)
    db.execute("UPDATE alumno SET estado='egresado', version=version+1 WHERE id=?", (egresado,))
    falla('no está activo', sp_inscribir_alumno, db, egresado, escuela['ciclo'], escuela['grupo'], 'traslado', escuela['usuario'])


# ------------------------------------------------------------ sp_asignar_tutor

def test_nuevo_tutor_principal_desplaza_al_anterior(db, escuela):
    madre, padre = tutor(db), tutor(db)
    sp_asignar_tutor(db, escuela['alumno'], madre, 'madre', escuela['usuario'])
    sp_asignar_tutor(db, escuela['alumno'], padre, 'padre', escuela['usuario'], puede_recoger=False)
    assert dict(db.execute('SELECT tutor_id, principal FROM alumno_tutor').fetchall()) == {madre: 0, padre: 1}
    assert bitacora(db, 'alumno_tutor.deja_principal')[0]['objeto_id'] == f"{escuela['alumno']}/{madre}"
    sp_asignar_tutor(db, escuela['alumno'], madre, 'tutor_legal', escuela['usuario'], principal=False)
    assert bitacora(db, 'alumno_tutor.asignado')[-1]['antes']['parentesco'] == 'madre'
    falla('Parentesco no válido', sp_asignar_tutor, db, escuela['alumno'], madre, 'vecina', escuela['usuario'])


# ------------------------------------------------------------ sp_capturar_calificacion

def test_capturar_y_cambiar_calificacion(db, escuela):
    args = (db, escuela['inscripcion'], escuela['periodo'], 'lenguajes')
    cal = sp_capturar_calificacion(*args, 8, escuela['usuario'])
    falla('indique la versión', sp_capturar_calificacion, *args, 9, escuela['usuario'])
    falla('La calificación cambió', sp_capturar_calificacion, *args, 9, escuela['usuario'], version=3)
    assert sp_capturar_calificacion(*args, 9, escuela['usuario'], version=1) == cal
    assert db.execute('SELECT valor, version FROM calificacion WHERE id=?', (cal,)).fetchone() == (9, 2)
    assert bitacora(db, 'calificacion.cambiada')[0]['antes']['valor'] == 8
    falla('entre 5 y 10', sp_capturar_calificacion, *args, 11, escuela['usuario'], version=2)


def test_periodo_cerrado_usa_el_mensaje_del_trigger(db, escuela):
    args = (db, escuela['inscripcion'], escuela['periodo'])
    sp_capturar_calificacion(*args, 'lenguajes', 8, escuela['usuario'])
    db.execute("UPDATE periodo SET estado='cerrado', version=version+1 WHERE id=?", (escuela['periodo'],))
    antes = valor(db, 'SELECT COUNT(*) FROM bitacora')
    falla('Periodo cerrado: registre una corrección', sp_capturar_calificacion, *args, 'lenguajes', 9, escuela['usuario'], version=1)
    falla('Periodo cerrado', sp_capturar_calificacion, *args, 'saberes', 9, escuela['usuario'])
    assert valor(db, 'SELECT COUNT(*) FROM bitacora') == antes
    assert not db.in_transaction


# ------------------------------------------------------------ sp_baja_alumno

def test_baja_de_alumno_e_inscripcion(db, escuela):
    a, i = escuela['alumno'], escuela['inscripcion']
    falla('motivo', sp_baja_alumno, db, a, ' ', escuela['usuario'], 1, {i: 1})
    falla('inscripciones del alumno cambiaron', sp_baja_alumno, db, a, 'Cambio de domicilio', escuela['usuario'], 1)
    falla('La inscripción cambió', sp_baja_alumno, db, a, 'Cambio de domicilio', escuela['usuario'], 1, {i: 5})
    assert valor(db, 'SELECT estado FROM alumno WHERE id=?', (a,)) == 'activo'
    sp_baja_alumno(db, a, 'Cambio de domicilio', escuela['usuario'], 1, {i: 1}, ahora='2026-10-15T09:00:00')
    assert db.execute('SELECT estado, version FROM alumno WHERE id=?', (a,)).fetchone() == ('baja', 2)
    assert db.execute('SELECT estado, baja, motivo_baja, version FROM inscripcion WHERE id=?', (i,)).fetchone() == (
        'baja', '2026-10-15T09:00:00', 'Cambio de domicilio', 2)
    assert bitacora(db, 'alumno.baja')[0]['despues']['motivo'] == 'Cambio de domicilio'
    falla('El alumno cambió', sp_baja_alumno, db, a, 'Otra vez', escuela['usuario'], 1)
