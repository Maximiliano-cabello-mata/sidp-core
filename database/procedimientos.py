"""Procedimientos de Maximiliano traducidos de PL/pgSQL a Python sobre SQLite.

SQLite no tiene procedimientos almacenados: cada uno es una función con el mismo nombre que
recibe una conexión abierta con isolation_level=None (como backend/base_datos.py) y corre en
UNA transacción (BEGIN IMMEDIATE ... COMMIT; ROLLBACK ante cualquier error). Los triggers de
database/diseno_integral.sql siguen siendo la última defensa; sus mensajes llegan como
ProcedimientoError.

Correcciones respecto al original:
  1. Versión (C4): quien guarda entrega la versión que vio; si la fila cambió, falla.
     El original leía la versión dentro del procedimiento y así nunca detectaba el conflicto.
  2. Bitácora (C5): todo cambio deja una fila con actor, antes y después en JSON.
  3. Datos extraídos de un escaneo solo proponen (C10): van a sugerencia_ia; la CURP no se
     escribe ni se confirma hasta que una persona lo decide.
  4. Una inscripción nueva empieza 'incompleta' (le faltan documentos hasta revisarlos).
  5. Nada se pierde: el motivo de un rechazo o cancelación y el valor anterior de un dato
     quedan en la bitácora aunque la tabla no tenga columna para ellos.
"""
import datetime
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager

CAMPOS_TUTOR = ('telefono', 'correo', 'domicilio')
CURP = re.compile(r'^[A-Z][AEIOUX][A-Z]{2}[0-9]{6}[HMX][A-Z]{5}[0-9A-Z][0-9]$')


class ProcedimientoError(Exception):
    """Una regla escolar impidió el cambio; el mensaje es para la persona que lo intentó."""


@contextmanager
def _transaccion(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
    except sqlite3.IntegrityError as error:
        db.execute('ROLLBACK')
        raise ProcedimientoError(str(error)) from error  # mensaje del trigger o de la restricción
    except BaseException:
        db.execute('ROLLBACK')
        raise
    db.execute('COMMIT')


def _ahora(ahora):
    return ahora or datetime.datetime.now().isoformat(timespec='seconds')


def _uid():
    return str(uuid.uuid4())


def _json(valor):
    return None if valor is None else json.dumps(valor, ensure_ascii=False)


def _uno(db, sql, parametros=()):
    cursor = db.execute(sql, parametros)
    fila = cursor.fetchone()
    return None if fila is None else dict(zip((c[0] for c in cursor.description), fila))


def _anotar(db, fecha, actor, accion, objeto_tipo, objeto_id, antes=None, despues=None):
    db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, antes, despues) VALUES(?,?,?,?,?,?,?)',
               (fecha, actor, accion, objeto_tipo, objeto_id, _json(antes), _json(despues)))


def _persona(db, actor):
    usuario = _uno(db, 'SELECT estado FROM usuario WHERE id = ?', (actor,))
    if usuario is None:
        raise ProcedimientoError('El actor debe ser un usuario registrado (una persona, nunca la IA).')
    if usuario['estado'] != 'activo':
        raise ProcedimientoError('El usuario no está activo.')


def _misma_version(fila, version, objeto):
    if fila['version'] != version:
        raise ProcedimientoError(f'{objeto} cambió, vuelva a cargarlo.')


def _requerido(texto, mensaje):
    if texto is None or not str(texto).strip():
        raise ProcedimientoError(mensaje)
    return str(texto).strip()


def _opcion(valor, opciones, nombre):
    if valor not in opciones:
        raise ProcedimientoError(f'{nombre} no válido: {valor!r}. Opciones: {", ".join(opciones)}.')


def _actualizar(db, tabla, fila_id, cambios, sube_version=True, clave='id'):
    asignaciones = [f'{columna} = ?' for columna in cambios]
    if sube_version:
        asignaciones.append('version = version + 1')
    db.execute(f'UPDATE {tabla} SET {", ".join(asignaciones)} WHERE {clave} = ?', (*cambios.values(), fila_id))


def sp_revisardocumento(db, documento_id, resultado, actor, version, motivo=None, *, ahora=None):
    """Valida o rechaza un documento del expediente y registra la revisión de la persona."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        _opcion(resultado, ('validado', 'rechazado'), 'Resultado')
        doc = _uno(db, 'SELECT estado, motivo_rechazo, version FROM documento WHERE id = ?', (documento_id,))
        if doc is None:
            raise ProcedimientoError('El documento especificado no existe.')
        _misma_version(doc, version, 'El documento')
        if doc['estado'] == 'reemplazado':
            raise ProcedimientoError('El documento ya fue reemplazado: revise la versión nueva.')
        motivo = motivo.strip() if motivo and motivo.strip() else None
        if resultado == 'rechazado' and motivo is None:
            raise ProcedimientoError('Es obligatorio especificar el motivo del rechazo.')
        cambios = {'estado': resultado, 'motivo_rechazo': motivo if resultado == 'rechazado' else None}
        _actualizar(db, 'documento', documento_id, cambios)
        revision_id = _uid()
        db.execute('INSERT INTO revision_documento(id, documento_id, resultado, motivo, reviso, fecha) VALUES(?,?,?,?,?,?)',
                   (revision_id, documento_id, resultado, motivo, actor, fecha))
        _anotar(db, fecha, actor, 'documento.revisado', 'documento', documento_id,
                {'estado': doc['estado'], 'motivo_rechazo': doc['motivo_rechazo']}, {**cambios, 'motivo': motivo})
    return revision_id


def sp_solicitudtutor(db, solicitud_id, decision, actor, version, motivo=None, *, ahora=None):
    """Aprueba o rechaza la solicitud de un tutor para cambiar su teléfono, correo o domicilio."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        _opcion(decision, ('aprobada', 'rechazada'), 'Decisión')
        solicitud = _uno(db, "SELECT tutor_id, campo, valor_nuevo FROM solicitud_cambio WHERE id = ? AND estado = 'pendiente'",
                         (solicitud_id,))
        if solicitud is None:
            raise ProcedimientoError('La solicitud no existe o no se encuentra pendiente.')
        campo = solicitud['campo']
        _opcion(campo, CAMPOS_TUTOR, 'Campo')  # el nombre de columna entra al SQL: solo de esta lista
        despues = {'estado': decision}
        if decision == 'rechazada':
            despues['motivo'] = _requerido(motivo, 'Es obligatorio especificar el motivo del rechazo.')
        else:
            tutor = _uno(db, f'SELECT {campo}, version FROM tutor WHERE id = ?', (solicitud['tutor_id'],))
            _misma_version(tutor, version, 'El tutor')
            _actualizar(db, 'tutor', solicitud['tutor_id'], {campo: solicitud['valor_nuevo']})
            _anotar(db, fecha, actor, 'tutor.contacto_cambiado', 'tutor', solicitud['tutor_id'],
                    {campo: tutor[campo]}, {campo: solicitud['valor_nuevo'], 'solicitud': solicitud_id})
        _actualizar(db, 'solicitud_cambio', solicitud_id, {'estado': decision, 'reviso': actor}, sube_version=False)
        _anotar(db, fecha, actor, f'solicitud_cambio.{decision}', 'solicitud_cambio', solicitud_id,
                {'estado': 'pendiente'}, despues)


def sp_inventario(db, bien_id, tipo_movimiento, detalle, actor, version, nueva_ubicacion=None, nuevo_estado=None,
                  *, ahora=None):
    """Registra un movimiento de un bien (ubicación, estado o baja) y actualiza el bien."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        _opcion(tipo_movimiento, ('alta', 'cambio_ubicacion', 'cambio_estado', 'baja'), 'Tipo de movimiento')
        detalle = _requerido(detalle, 'Describa el movimiento.')
        bien = _uno(db, 'SELECT ubicacion, estado, version FROM bien WHERE id = ?', (bien_id,))
        if bien is None:
            raise ProcedimientoError(f'El bien con ID {bien_id} no existe en inventario.')
        _misma_version(bien, version, 'El bien')
        if bien['estado'] == 'baja':
            raise ProcedimientoError('El bien ya está dado de baja.')
        if tipo_movimiento == 'baja':
            nuevo_estado = nuevo_estado or 'baja'
        if nuevo_estado is not None:
            _opcion(nuevo_estado, ('bueno', 'regular', 'malo', 'baja'), 'Estado del bien')
        antes = {'ubicacion': bien['ubicacion'], 'estado': bien['estado']}
        despues = {'ubicacion': nueva_ubicacion or bien['ubicacion'], 'estado': nuevo_estado or bien['estado']}
        _actualizar(db, 'bien', bien_id, despues)
        db.execute('INSERT INTO bien_movimiento(id, bien_id, tipo, detalle, registro, fecha) VALUES(?,?,?,?,?,?)',
                   (_uid(), bien_id, tipo_movimiento, detalle, actor, fecha))
        _anotar(db, fecha, actor, f'bien.{tipo_movimiento}', 'bien', bien_id, antes, {**despues, 'detalle': detalle})


def sp_siguenteciclo(db, grupo_origen_id, grupo_destino_id, ciclo_destino_id, actor, *, ahora=None):
    """Reinscribe en el grupo destino a los alumnos activos con inscripción completa del grupo origen."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        ciclo = _uno(db, 'SELECT estado FROM ciclo WHERE id = ?', (ciclo_destino_id,))
        if ciclo is None:
            raise ProcedimientoError('El ciclo escolar destino no existe.')
        if ciclo['estado'] == 'cerrado':
            raise ProcedimientoError('El ciclo escolar destino está cerrado.')
        if not _uno(db, 'SELECT 1 FROM grupo WHERE id = ?', (grupo_origen_id,)):
            raise ProcedimientoError('El grupo origen no existe.')
        if not _uno(db, 'SELECT 1 FROM grupo WHERE id = ? AND ciclo_id = ?', (grupo_destino_id, ciclo_destino_id)):
            raise ProcedimientoError('El grupo destino no pertenece al ciclo escolar destino indicado.')
        alumnos = [fila[0] for fila in db.execute(
            "SELECT i.alumno_id FROM inscripcion i JOIN alumno a ON a.id = i.alumno_id "
            "WHERE i.grupo_id = ? AND i.estado = 'completa' AND a.estado = 'activo' "
            "AND NOT EXISTS (SELECT 1 FROM inscripcion n WHERE n.alumno_id = i.alumno_id "
            "                AND n.ciclo_id = ? AND n.estado <> 'cancelada')",
            (grupo_origen_id, ciclo_destino_id))]
        for alumno_id in alumnos:
            nueva = {'alumno_id': alumno_id, 'ciclo_id': ciclo_destino_id, 'grupo_id': grupo_destino_id,
                     'tipo': 'reinscripcion', 'origen': 'captura', 'estado': 'incompleta', 'alta': fecha}
            inscripcion_id = _uid()
            db.execute('INSERT INTO inscripcion(id, alumno_id, ciclo_id, grupo_id, tipo, origen, estado, alta) '
                       'VALUES(?,?,?,?,?,?,?,?)', (inscripcion_id, *nueva.values()))
            _anotar(db, fecha, actor, 'inscripcion.reinscrita', 'inscripcion', inscripcion_id, None,
                    {**nueva, 'grupo_origen': grupo_origen_id})
    return len(alumnos)


def sp_publicarversionformato(db, formato_id, actor, *, ahora=None):
    """Publica un formato en borrador como vigente y retira la versión vigente del mismo nombre."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        formato = _uno(db, 'SELECT nombre, estado FROM formato WHERE id = ?', (formato_id,))
        if formato is None:
            raise ProcedimientoError('El formato indicado no existe.')
        if formato['estado'] != 'borrador':
            raise ProcedimientoError(f"Solo se publica un formato en borrador (este está {formato['estado']}).")
        # Primero se retira la anterior: el índice un_formato_vigente admite una sola vigente por nombre.
        for (anterior,) in db.execute("SELECT id FROM formato WHERE nombre = ? AND estado = 'vigente'",
                                      (formato['nombre'],)).fetchall():
            _actualizar(db, 'formato', anterior, {'estado': 'retirado'}, sube_version=False)
            _anotar(db, fecha, actor, 'formato.retirado', 'formato', anterior,
                    {'estado': 'vigente'}, {'estado': 'retirado', 'reemplazado_por': formato_id})
        _actualizar(db, 'formato', formato_id, {'estado': 'vigente'}, sube_version=False)
        _anotar(db, fecha, actor, 'formato.publicado', 'formato', formato_id, {'estado': 'borrador'}, {'estado': 'vigente'})


def sp_cancelardocumentoemitido(db, folio, motivo, actor, *, ahora=None):
    """Cancela un documento emitido (constancia, certificado) dejando motivo y responsable en la bitácora."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        motivo = _requerido(motivo, 'Es obligatorio especificar el motivo de la cancelación.')
        emitido = _uno(db, 'SELECT estado FROM documento_emitido WHERE folio = ?', (folio,))
        if emitido is None:
            raise ProcedimientoError(f'El documento emitido con folio {folio} no existe.')
        if emitido['estado'] == 'cancelado':
            raise ProcedimientoError(f'El documento {folio} ya fue cancelado previamente.')
        db.execute("UPDATE documento_emitido SET estado = 'cancelado' WHERE folio = ? AND estado = 'valido'", (folio,))
        _anotar(db, fecha, actor, 'documento_emitido.cancelado', 'documento_emitido', folio,
                {'estado': 'valido'}, {'estado': 'cancelado', 'motivo': motivo})


def sp_finalizar_lote_importacion(db, importacion_id, filas_leidas, filas_aplicadas, actor, errores=None, *, ahora=None):
    """Cierra una importación en revisión: aplicada si entró alguna fila, descartada si no."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        importacion = _uno(db, "SELECT filas_leidas, filas_aplicadas, errores, estado FROM importacion "
                               "WHERE id = ? AND estado = 'revisando'", (importacion_id,))
        if importacion is None:
            raise ProcedimientoError(f'La importación {importacion_id} no existe o ya fue procesada anteriormente.')
        if not 0 <= filas_aplicadas <= filas_leidas:
            raise ProcedimientoError('Las filas aplicadas deben estar entre cero y las filas leídas.')
        if errores is not None and not isinstance(errores, str):
            errores = _json(errores)
        cambios = {'filas_leidas': filas_leidas, 'filas_aplicadas': filas_aplicadas, 'errores': errores,
                   'estado': 'aplicada' if filas_aplicadas > 0 else 'descartada'}
        _actualizar(db, 'importacion', importacion_id, cambios, sube_version=False)
        _anotar(db, fecha, actor, f"importacion.{cambios['estado']}", 'importacion', importacion_id, importacion, cambios)


def sp_reemplazardocumento(db, documento_anterior_id, nuevo_archivo_sha256, actor, version, *, ahora=None):
    """Sube una versión nueva de un documento y marca la anterior como reemplazada."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        anterior = _uno(db, 'SELECT * FROM documento WHERE id = ?', (documento_anterior_id,))
        if anterior is None:
            raise ProcedimientoError(f'El documento a reemplazar ({documento_anterior_id}) no existe.')
        _misma_version(anterior, version, 'El documento')
        if anterior['estado'] == 'reemplazado':
            raise ProcedimientoError('Ese documento ya fue reemplazado: reemplace la versión más reciente.')
        if not _uno(db, 'SELECT 1 FROM archivo WHERE sha256 = ?', (nuevo_archivo_sha256,)):
            raise ProcedimientoError(f'El archivo con hash {nuevo_archivo_sha256} no está registrado.')
        if nuevo_archivo_sha256 == anterior['archivo_sha256']:
            raise ProcedimientoError('El archivo nuevo es el mismo que el anterior.')
        _actualizar(db, 'documento', documento_anterior_id, {'estado': 'reemplazado'})
        nuevo_id = _uid()
        db.execute('INSERT INTO documento(id, tipo, alumno_id, tutor_id, personal_id, ciclo_id, archivo_sha256, '
                   "reemplaza_a, origen, estado, recibio, recibido) VALUES(?,?,?,?,?,?,?,?,?,'recibido',?,?)",
                   (nuevo_id, anterior['tipo'], anterior['alumno_id'], anterior['tutor_id'], anterior['personal_id'],
                    anterior['ciclo_id'], nuevo_archivo_sha256, documento_anterior_id, anterior['origen'], actor, fecha))
        _anotar(db, fecha, actor, 'documento.reemplazado', 'documento', documento_anterior_id,
                {'estado': anterior['estado']}, {'estado': 'reemplazado', 'reemplazado_por': nuevo_id})
        _anotar(db, fecha, actor, 'documento.recibido', 'documento', nuevo_id, None,
                {'estado': 'recibido', 'archivo_sha256': nuevo_archivo_sha256, 'reemplaza_a': documento_anterior_id})
    return nuevo_id


def procesar_expediente_extraido(db, alumno_id, tipo_documento, archivo_sha256, datos_extraidos, actor, *, ahora=None):
    """Registra un documento escaneado como recibido y deja sus datos extraídos como propuesta en sugerencia_ia."""
    fecha = _ahora(ahora)
    if isinstance(datos_extraidos, str):
        datos_extraidos = json.loads(datos_extraidos)
    with _transaccion(db):
        _persona(db, actor)
        if not _uno(db, 'SELECT 1 FROM archivo WHERE sha256 = ?', (archivo_sha256,)):
            raise ProcedimientoError(f'El archivo físico con hash {archivo_sha256} no está registrado.')
        alumno = _uno(db, 'SELECT curp FROM alumno WHERE id = ?', (alumno_id,))
        if alumno is None:
            raise ProcedimientoError(f'El alumno con ID {alumno_id} no existe.')
        tipo = _uno(db, 'SELECT aplica_a FROM tipo_documento WHERE clave = ?', (tipo_documento,))
        if tipo is None or tipo['aplica_a'] != 'alumno':
            raise ProcedimientoError(f'{tipo_documento!r} no es un tipo de documento de alumno.')
        if _uno(db, 'SELECT 1 FROM documento WHERE alumno_id = ? AND tipo = ? AND archivo_sha256 = ?',
                (alumno_id, tipo_documento, archivo_sha256)):
            raise ProcedimientoError('Este documento ya fue registrado previamente para este alumno.')
        documento_id = _uid()
        db.execute('INSERT INTO documento(id, tipo, alumno_id, archivo_sha256, origen, estado, recibio, recibido) '
                   "VALUES(?,?,?,?,'escaneo','recibido',?,?)", (documento_id, tipo_documento, alumno_id, archivo_sha256, actor, fecha))
        _anotar(db, fecha, actor, 'documento.recibido', 'documento', documento_id, None,
                {'tipo': tipo_documento, 'alumno_id': alumno_id, 'archivo_sha256': archivo_sha256, 'estado': 'recibido'})

        # Las dudas sobre la CURP son avisos dentro de la propuesta, no errores: el archivo sí llegó
        # y debe quedar registrado; la persona que revise decide qué hacer con la CURP.
        curp = str(datos_extraidos.get('curp_encontrada') or '').strip().upper() or None
        avisos = []
        if curp and not CURP.match(curp):
            avisos.append(f'La CURP extraída ({curp}) no tiene un formato válido.')
            curp = None
        if curp:
            otro = _uno(db, 'SELECT id FROM alumno WHERE curp = ? AND id <> ?', (curp, alumno_id))
            if otro:
                avisos.append(f"La CURP extraída ({curp}) ya pertenece a otro alumno registrado ({otro['id']}).")
            if alumno['curp'] and alumno['curp'] != curp:
                avisos.append(f"La CURP extraída ({curp}) no coincide con la registrada ({alumno['curp']}).")
        contenido = {'datos_extraidos': datos_extraidos, 'curp_propuesta': curp, 'avisos': avisos}
        sugerencia_id = _uid()
        db.execute("INSERT INTO sugerencia_ia(id, objeto_tipo, objeto_id, tipo, contenido, estado, fecha) "
                   "VALUES(?,'documento',?,'validacion',?,'propuesta',?)", (sugerencia_id, documento_id, _json(contenido), fecha))
        _anotar(db, fecha, actor, 'sugerencia_ia.propuesta', 'sugerencia_ia', sugerencia_id, None,
                {'documento_id': documento_id, 'curp_propuesta': curp, 'avisos': avisos})
    return {'documento_id': documento_id, 'sugerencia_id': sugerencia_id}


def sp_inscribir_alumno(db, alumno_id, ciclo_id, grupo_id, tipo, actor, origen='captura', *, ahora=None):
    """Inscribe a un alumno activo en un grupo de un ciclo no cerrado; la inscripción empieza incompleta."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        _opcion(tipo, ('nuevo_ingreso', 'reinscripcion', 'traslado'), 'Tipo de inscripción')
        _opcion(origen, ('captura', 'said', 'importacion'), 'Origen')
        ciclo = _uno(db, 'SELECT estado FROM ciclo WHERE id = ?', (ciclo_id,))
        if ciclo is None:
            raise ProcedimientoError('El ciclo escolar no existe.')
        if ciclo['estado'] == 'cerrado':
            raise ProcedimientoError('No se puede inscribir: el ciclo escolar está cerrado.')
        alumno = _uno(db, 'SELECT estado FROM alumno WHERE id = ?', (alumno_id,))
        if alumno is None:
            raise ProcedimientoError('El alumno no existe.')
        if alumno['estado'] != 'activo':
            raise ProcedimientoError(f"El alumno no está activo (estado actual: {alumno['estado']}).")
        if not _uno(db, 'SELECT 1 FROM grupo WHERE id = ? AND ciclo_id = ?', (grupo_id, ciclo_id)):
            raise ProcedimientoError('El grupo no pertenece al ciclo escolar indicado.')
        if _uno(db, "SELECT 1 FROM inscripcion WHERE alumno_id = ? AND ciclo_id = ? AND estado <> 'cancelada'",
                (alumno_id, ciclo_id)):
            raise ProcedimientoError('El alumno ya tiene una inscripción activa en este ciclo.')
        nueva = {'alumno_id': alumno_id, 'ciclo_id': ciclo_id, 'grupo_id': grupo_id, 'tipo': tipo,
                 'origen': origen, 'estado': 'incompleta', 'alta': fecha}
        inscripcion_id = _uid()
        db.execute('INSERT INTO inscripcion(id, alumno_id, ciclo_id, grupo_id, tipo, origen, estado, alta) '
                   'VALUES(?,?,?,?,?,?,?,?)', (inscripcion_id, *nueva.values()))
        _anotar(db, fecha, actor, 'inscripcion.alta', 'inscripcion', inscripcion_id, None, nueva)
    return inscripcion_id


def sp_asignar_tutor(db, alumno_id, tutor_id, parentesco, actor, principal=True, puede_recoger=True, *, ahora=None):
    """Vincula un tutor con un alumno; si es principal, el principal anterior deja de serlo."""
    fecha = _ahora(ahora)
    principal, puede_recoger = int(bool(principal)), int(bool(puede_recoger))
    with _transaccion(db):
        _persona(db, actor)
        _opcion(parentesco, ('madre', 'padre', 'tutor_legal', 'abuelo', 'otro'), 'Parentesco')
        if not _uno(db, 'SELECT 1 FROM alumno WHERE id = ?', (alumno_id,)):
            raise ProcedimientoError('El alumno no existe.')
        if not _uno(db, 'SELECT 1 FROM tutor WHERE id = ?', (tutor_id,)):
            raise ProcedimientoError('El tutor no existe.')
        if principal:
            for (otro,) in db.execute('SELECT tutor_id FROM alumno_tutor WHERE alumno_id = ? AND principal = 1 AND tutor_id <> ?',
                                      (alumno_id, tutor_id)).fetchall():
                db.execute('UPDATE alumno_tutor SET principal = 0 WHERE alumno_id = ? AND tutor_id = ?', (alumno_id, otro))
                _anotar(db, fecha, actor, 'alumno_tutor.deja_principal', 'alumno_tutor', f'{alumno_id}/{otro}',
                        {'principal': 1}, {'principal': 0, 'nuevo_principal': tutor_id})
        actual = _uno(db, 'SELECT parentesco, principal, puede_recoger, vigente FROM alumno_tutor '
                          'WHERE alumno_id = ? AND tutor_id = ?', (alumno_id, tutor_id))
        despues = {'parentesco': parentesco, 'principal': principal, 'puede_recoger': puede_recoger, 'vigente': 1}
        if actual is None:
            db.execute('INSERT INTO alumno_tutor(alumno_id, tutor_id, parentesco, principal, puede_recoger, vigente) '
                       'VALUES(?,?,?,?,?,?)', (alumno_id, tutor_id, *despues.values()))
        else:
            db.execute('UPDATE alumno_tutor SET parentesco = ?, principal = ?, puede_recoger = ?, vigente = ? '
                       'WHERE alumno_id = ? AND tutor_id = ?', (*despues.values(), alumno_id, tutor_id))
        _anotar(db, fecha, actor, 'alumno_tutor.asignado', 'alumno_tutor', f'{alumno_id}/{tutor_id}', actual, despues)


def sp_validar_curp_renapo(db, alumno_id, archivo_sha256, resultado, actor, version, motivo=None, *, ahora=None):
    """Guarda la constancia de RENAPO que trajo una persona y, si coincide, confirma la CURP del alumno.

    La constancia queda como documento 'curp' revisado (validado o rechazado con su motivo); con
    'validado', alumno.curp_confirmada pasa a 1. Quién y cuándo quedan en la revisión y la bitácora.
    """
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        _opcion(resultado, ('validado', 'rechazado'), 'Resultado')
        alumno = _uno(db, 'SELECT curp, curp_confirmada, version FROM alumno WHERE id = ?', (alumno_id,))
        if alumno is None:
            raise ProcedimientoError('El alumno no existe.')
        _misma_version(alumno, version, 'El alumno')
        if not _uno(db, 'SELECT 1 FROM archivo WHERE sha256 = ?', (archivo_sha256,)):
            raise ProcedimientoError(f'El archivo físico con hash {archivo_sha256} no está registrado.')
        motivo = motivo.strip() if motivo and motivo.strip() else None
        if resultado == 'rechazado' and motivo is None:
            raise ProcedimientoError('Es obligatorio especificar por qué no coincide la constancia.')
        documento_id = _uid()
        db.execute('INSERT INTO documento(id, tipo, alumno_id, archivo_sha256, origen, estado, motivo_rechazo, recibio, recibido) '
                   "VALUES(?, 'curp', ?, ?, 'escaneo', ?, ?, ?, ?)",
                   (documento_id, alumno_id, archivo_sha256, resultado, motivo if resultado == 'rechazado' else None, actor, fecha))
        db.execute('INSERT INTO revision_documento(id, documento_id, resultado, motivo, reviso, fecha) VALUES(?,?,?,?,?,?)',
                   (_uid(), documento_id, resultado, motivo or 'Constancia de la CURP descargada de RENAPO', actor, fecha))
        despues = {'documento_id': documento_id, 'curp': alumno['curp'], 'fuente': 'constancia RENAPO'}
        if resultado == 'validado':
            _actualizar(db, 'alumno', alumno_id, {'curp_confirmada': 1})
            _anotar(db, fecha, actor, 'alumno.renapo_validada', 'alumno', alumno_id,
                    {'curp_confirmada': alumno['curp_confirmada']}, {**despues, 'curp_confirmada': 1})
        else:
            _anotar(db, fecha, actor, 'alumno.renapo_no_coincide', 'alumno', alumno_id, None, {**despues, 'motivo': motivo})
    return documento_id


def sp_pasar_lista(db, grupo_id, fecha, marcas, actor, *, ahora=None):
    """Asistencia de un grupo en una fecha. marcas: {inscripcion_id: 'presente'|'falta'|'retardo'|'justificada'}.

    Volver a pasar lista el mismo día cambia la marca y deja el valor anterior en la bitácora.
    """
    momento = _ahora(ahora)
    try:
        datetime.date.fromisoformat(fecha)
    except (TypeError, ValueError) as error:
        raise ProcedimientoError('La fecha debe tener la forma AAAA-MM-DD.') from error
    with _transaccion(db):
        _persona(db, actor)
        inscritas = {i for (i,) in db.execute("SELECT id FROM inscripcion WHERE grupo_id = ? AND estado IN ('incompleta','completa')",
                                              (grupo_id,))}
        for inscripcion_id, estado in marcas.items():
            _opcion(estado, ('presente', 'falta', 'retardo', 'justificada'), 'Asistencia')
            if inscripcion_id not in inscritas:
                raise ProcedimientoError('Un alumno de la lista no está inscrito en este grupo.')
            actual = _uno(db, 'SELECT estado FROM asistencia_alumno WHERE inscripcion_id = ? AND fecha = ?', (inscripcion_id, fecha))
            if actual is None:
                db.execute('INSERT INTO asistencia_alumno(inscripcion_id, fecha, estado, capturo) VALUES(?,?,?,?)',
                           (inscripcion_id, fecha, estado, actor))
            elif actual['estado'] != estado:
                db.execute('UPDATE asistencia_alumno SET estado = ?, capturo = ?, version = version + 1 '
                           'WHERE inscripcion_id = ? AND fecha = ?', (estado, actor, inscripcion_id, fecha))
            else:
                continue
            _anotar(db, momento, actor, 'asistencia.capturada', 'inscripcion', inscripcion_id, actual,
                    {'fecha': fecha, 'estado': estado})


def sp_capturar_calificacion(db, inscripcion_id, periodo_id, campo, valor, actor, version=None, observaciones=None,
                             *, ahora=None):
    """Captura o cambia la calificación de un campo formativo en un periodo abierto."""
    fecha = _ahora(ahora)
    with _transaccion(db):
        _persona(db, actor)
        if not isinstance(valor, int) or not 5 <= valor <= 10:
            raise ProcedimientoError('La calificación debe ser un entero entre 5 y 10.')
        periodo = _uno(db, 'SELECT ciclo_id FROM periodo WHERE id = ?', (periodo_id,))
        if periodo is None:
            raise ProcedimientoError('El periodo especificado no existe.')
        inscripcion = _uno(db, 'SELECT ciclo_id, estado FROM inscripcion WHERE id = ?', (inscripcion_id,))
        if inscripcion is None:
            raise ProcedimientoError('La inscripción no existe.')
        if inscripcion['ciclo_id'] != periodo['ciclo_id']:
            raise ProcedimientoError('El periodo no pertenece al ciclo de la inscripción.')
        if inscripcion['estado'] not in ('incompleta', 'completa'):
            raise ProcedimientoError(f"La inscripción está en {inscripcion['estado']}: no admite calificaciones.")
        # Periodo cerrado: lo rechazan los triggers periodo_cerrado_*; su mensaje sale como ProcedimientoError.
        actual = _uno(db, 'SELECT id, valor, observaciones, capturo, version FROM calificacion '
                          'WHERE inscripcion_id = ? AND periodo_id = ? AND campo = ?', (inscripcion_id, periodo_id, campo))
        cambios = {'valor': valor, 'observaciones': observaciones, 'capturo': actor}
        if actual is None:
            calificacion_id = _uid()
            db.execute('INSERT INTO calificacion(id, inscripcion_id, periodo_id, campo, valor, observaciones, capturo) '
                       'VALUES(?,?,?,?,?,?,?)', (calificacion_id, inscripcion_id, periodo_id, campo, *cambios.values()))
            _anotar(db, fecha, actor, 'calificacion.capturada', 'calificacion', calificacion_id, None,
                    {'inscripcion_id': inscripcion_id, 'periodo_id': periodo_id, 'campo': campo, **cambios})
        else:
            calificacion_id = actual.pop('id')
            if version is None:
                raise ProcedimientoError('La calificación ya existe: indique la versión que vio para cambiarla.')
            _misma_version(actual, version, 'La calificación')
            _actualizar(db, 'calificacion', calificacion_id, cambios)
            del actual['version']
            _anotar(db, fecha, actor, 'calificacion.cambiada', 'calificacion', calificacion_id, actual, cambios)
    return calificacion_id


def sp_baja_alumno(db, alumno_id, motivo, actor, version, inscripciones=None, *, ahora=None):
    """Da de baja a un alumno y a sus inscripciones vigentes en ciclos no cerrados.

    inscripciones: {inscripcion_id: versión vista} de las inscripciones vigentes que la persona tenía en pantalla.
    """
    fecha = _ahora(ahora)
    inscripciones = inscripciones or {}
    with _transaccion(db):
        _persona(db, actor)
        motivo = _requerido(motivo, 'Es obligatorio especificar el motivo de la baja.')
        alumno = _uno(db, 'SELECT estado, version FROM alumno WHERE id = ?', (alumno_id,))
        if alumno is None:
            raise ProcedimientoError('El alumno no existe.')
        _misma_version(alumno, version, 'El alumno')
        if alumno['estado'] != 'activo':
            raise ProcedimientoError(f"El alumno no está activo (estado actual: {alumno['estado']}).")
        vigentes = {fila[0]: fila for fila in db.execute(
            "SELECT i.id, i.estado, i.version FROM inscripcion i JOIN ciclo c ON c.id = i.ciclo_id "
            "WHERE i.alumno_id = ? AND i.estado IN ('incompleta', 'completa') AND c.estado <> 'cerrado'", (alumno_id,))}
        if set(vigentes) != set(inscripciones):
            raise ProcedimientoError('Las inscripciones del alumno cambiaron, vuelva a cargarlo.')
        _actualizar(db, 'alumno', alumno_id, {'estado': 'baja'})
        _anotar(db, fecha, actor, 'alumno.baja', 'alumno', alumno_id, {'estado': alumno['estado']},
                {'estado': 'baja', 'motivo': motivo})
        for inscripcion_id, (_, estado, version_actual) in vigentes.items():
            _misma_version({'version': version_actual}, inscripciones[inscripcion_id], 'La inscripción')
            cambios = {'estado': 'baja', 'baja': fecha, 'motivo_baja': motivo}
            _actualizar(db, 'inscripcion', inscripcion_id, cambios)
            _anotar(db, fecha, actor, 'inscripcion.baja', 'inscripcion', inscripcion_id, {'estado': estado}, cambios)
