"""El diseño integral de la base (database/diseno_integral.sql) carga y sus defensas funcionan."""
import sqlite3
import uuid
from pathlib import Path
import pytest

DISENO = Path(__file__).resolve().parent.parent / 'database' / 'diseno_integral.sql'
HOY = '2026-10-13'
CURP = 'GOMA150101HMCRRNA5'


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


def rechaza(db, sql, parametros=(), texto=None):
    with pytest.raises(sqlite3.IntegrityError) as error:
        db.execute(sql, parametros)
    if texto:
        assert texto in str(error.value)


def test_carga_sin_errores(db):
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert db.execute('SELECT COUNT(*) FROM campo_formativo').fetchone()[0] == 4
    assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_no_se_borra_un_alumno(db, escuela):
    rechaza(db, 'DELETE FROM alumno WHERE id=?', (escuela['alumno'],), 'No se borran alumnos')


def test_curp_con_formato_invalido(db):
    rechaza(db, "INSERT INTO alumno(id,curp,nombres,primer_apellido) VALUES(?,'ABC','A','B')", (uid(),))


def test_version_vieja_no_sobrescribe(db, escuela):
    db.execute("UPDATE alumno SET nombres='Juan Carlos', version=version+1 WHERE id=?", (escuela['alumno'],))
    # Otra pantalla todavía tenía la versión 1 y quiere guardar.
    rechaza(db, "UPDATE alumno SET nombres='Juanito', version=2 WHERE id=?", (escuela['alumno'],), 'Conflicto')


def test_periodo_cerrado_solo_acepta_correcciones(db, escuela):
    cal = uid()
    db.execute("INSERT INTO calificacion(id,inscripcion_id,periodo_id,campo,valor,capturo) VALUES(?,?,?,'lenguajes',8,?)",
               (cal, escuela['inscripcion'], escuela['periodo'], escuela['usuario']))
    db.execute("UPDATE periodo SET estado='cerrado', version=version+1 WHERE id=?", (escuela['periodo'],))
    rechaza(db, "UPDATE calificacion SET valor=9, version=version+1 WHERE id=?", (cal,), 'Periodo cerrado')
    rechaza(db, "UPDATE periodo SET estado='abierto', version=version+1 WHERE id=?", (escuela['periodo'],), 'no se reabre')
    db.execute("INSERT INTO calificacion_correccion(id,calificacion_id,valor_nuevo,motivo,autorizo,fecha) VALUES(?,?,9,?,?,?)",
               (uid(), cal, 'Error de captura en el examen', escuela['usuario'], HOY))
    assert db.execute('SELECT valor FROM calificacion_vigente WHERE id=?', (cal,)).fetchone()[0] == 9
    assert db.execute('SELECT valor FROM calificacion WHERE id=?', (cal,)).fetchone()[0] == 8


def test_bitacora_solo_se_agrega(db):
    db.execute("INSERT INTO bitacora(fecha,actor,accion,objeto_tipo,objeto_id) VALUES(?,'ana','x','alumno','1')", (HOY,))
    rechaza(db, "UPDATE bitacora SET actor='otro'", texto='no se modifica')
    rechaza(db, 'DELETE FROM bitacora', texto='no se borra')


def test_archivo_y_documento_inmutables(db, escuela):
    sha = 'a' * 64
    db.execute("INSERT INTO archivo(sha256,tamano,tipo_mime,ruta_relativa,creado) VALUES(?,100,'application/pdf','aa/a.pdf',?)", (sha, HOY))
    rechaza(db, "UPDATE archivo SET tamano=5 WHERE sha256=?", (sha,), 'no cambia')
    db.execute("UPDATE archivo SET copias_confirmadas=1 WHERE sha256=?", (sha,))
    doc = uid()
    db.execute("INSERT INTO documento(id,tipo,alumno_id,archivo_sha256,origen,recibido) VALUES(?,'acta',?,?,'buzon',?)",
               (doc, escuela['alumno'], sha, HOY))
    rechaza(db, "UPDATE documento SET archivo_sha256=?, version=version+1 WHERE id=?", ('b' * 64, doc), 'no cambia')
    rechaza(db, "UPDATE documento SET estado='rechazado', version=version+1 WHERE id=?", (doc,))  # falta el motivo


def test_documento_con_un_solo_dueno(db, escuela):
    sha = 'c' * 64
    db.execute("INSERT INTO archivo(sha256,tamano,tipo_mime,ruta_relativa,creado) VALUES(?,100,'image/png','cc/c.png',?)", (sha, HOY))
    rechaza(db, "INSERT INTO documento(id,tipo,archivo_sha256,origen,recibido) VALUES(?,'acta',?,'foto',?)", (uid(), sha, HOY))


def test_misma_importacion_no_se_aplica_dos_veces(db, escuela):
    sha = 'd' * 64
    db.execute("INSERT INTO archivo(sha256,tamano,tipo_mime,ruta_relativa,creado) VALUES(?,9,"
               "'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','dd/alumnos.xlsx',?)", (sha, HOY))
    sql = "INSERT INTO importacion(id,archivo_sha256,tipo,estado,actor,fecha) VALUES(?,?,'alumnos','aplicada',?,?)"
    db.execute(sql, (uid(), sha, escuela['usuario'], HOY))
    rechaza(db, sql, (uid(), sha, escuela['usuario'], HOY))


def test_ciclo_cerrado_es_de_solo_lectura(db, escuela):
    db.execute("UPDATE ciclo SET estado='cerrado', version=version+1 WHERE id=?", (escuela['ciclo'],))
    rechaza(db, "INSERT INTO asistencia_alumno(inscripcion_id,fecha,estado,capturo) VALUES(?,?,'presente',?)",
            (escuela['inscripcion'], HOY, escuela['usuario']), 'Ciclo cerrado')


def test_sugerencia_de_ia_requiere_decision_humana(db, escuela):
    rechaza(db, "INSERT INTO sugerencia_ia(id,objeto_tipo,objeto_id,tipo,contenido,estado,fecha) "
                "VALUES(?,'documento','x','validacion','{}','aceptada',?)", (uid(), HOY))
