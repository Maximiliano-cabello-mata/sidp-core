"""El expediente en la base de prueba: las 39 tablas del diseño integral y los procedimientos de Maximiliano.

Cuando un padre sube su expediente, se registran el alumno, el tutor, cada archivo (por su
sha256, sin sobrescribir) y cada documento. Lo que el validador extrajo queda en
sugerencia_ia como propuesta: la CURP no se confirma sola. La decisión del administrador
pasa por sp_revisardocumento, que deja la revisión y la bitácora.
"""
import datetime
import hashlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path

from database import procedimientos as sp
from validacion import comparador

RAIZ = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))  # Dentro del .exe, los datos incluidos.
DISENO = RAIZ / 'database' / 'diseno_integral.sql'
# Espacio de la página de padres -> (tipo_documento del diseño, de quién es).
TIPO_DISENO = {'acta_alumno': ('acta', 'alumno'), 'certificado_medico': ('certificado_medico', 'alumno'),
               'boleta': ('boleta_anterior', 'alumno'), 'ine_tutor': ('ine_tutor', 'tutor'),
               'comprobante': ('comprobante_domicilio', 'tutor')}
MIME = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}


def _ahora():
    return datetime.datetime.now().isoformat(timespec='seconds')


class Registro:
    def __init__(self, ruta):
        nueva = not Path(ruta).exists()
        self.db = sqlite3.connect(str(ruta), isolation_level=None, check_same_thread=False)
        if nueva:
            self.db.executescript(DISENO.read_text(encoding='utf-8'))
        self.db.execute('PRAGMA foreign_keys=ON')
        self.actor = self._administrador()

    def _administrador(self):
        """La persona que revisa en el entorno de pruebas; en la plataforma será cada usuario con su cuenta."""
        fila = self.db.execute("SELECT id FROM usuario WHERE nombre_usuario = 'administrador'").fetchone()
        if fila:
            return fila[0]
        personal, usuario = str(uuid.uuid4()), str(uuid.uuid4())
        with self.db:
            self.db.execute("INSERT INTO personal(id, nombres, primer_apellido, puesto) VALUES(?, 'Administrador', 'de pruebas', 'secretaria')",
                            (personal,))
            self.db.execute("INSERT INTO usuario(id, personal_id, nombre_usuario, contrasena_resumen, rol) "
                            "VALUES(?, ?, 'administrador', 'sin contraseña: entorno de pruebas', 'administrativo')", (usuario, personal))
        return usuario

    def _persona(self, tabla, datos, curp=None):
        curp = curp if curp and comparador.desglose_curp(curp) else None  # Una CURP mal escrita no entra como dato.
        if curp:
            fila = self.db.execute(f'SELECT id FROM {tabla} WHERE curp = ?', (curp,)).fetchone()
            if fila:
                return fila[0]
        identificador = str(uuid.uuid4())
        columnas = {'id': identificador, 'curp': curp, 'nombres': datos['nombres'], 'primer_apellido': datos['primer_apellido'],
                    'segundo_apellido': datos.get('segundo_apellido') or None}
        if tabla == 'tutor':
            columnas.update(telefono=datos.get('telefono') or None, correo=datos.get('correo') or None,
                            domicilio=datos.get('domicilio') or None)
        with self.db:
            self.db.execute(f'INSERT INTO {tabla}({", ".join(columnas)}) VALUES({", ".join("?" * len(columnas))})',
                            tuple(columnas.values()))
            self.db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, despues) VALUES(?,?,?,?,?,?)',
                            (_ahora(), 'pagina_padres', f'{tabla}.registrado', tabla, identificador,
                             json.dumps({k: v for k, v in columnas.items() if k != 'id'}, ensure_ascii=False)))
        return identificador

    def registrar(self, captura, archivos, extraidos=None):
        """captura: lo que escribió el padre; archivos: [(espacio, ruta relativa a la carpeta de datos, contenido)].

        extraidos: lo que el validador encontró (resultado['extraidos']); cada documento recibe lo suyo.
        Devuelve los identificadores para guardarlos junto al expediente.
        """
        extraidos = extraidos or {}
        alumno = self._persona('alumno', captura['alumno'], captura['alumno'].get('curp', '').upper())
        tutor = self._persona('tutor', captura['tutor'])
        parentesco = captura['tutor'].get('parentesco', 'otro')
        sp.sp_asignar_tutor(self.db, alumno, tutor, parentesco if parentesco in ('madre', 'padre', 'tutor_legal', 'abuelo') else 'otro',
                            self.actor)
        documentos = []
        for espacio, ruta, contenido in archivos:
            tipo, dueno = TIPO_DISENO.get(espacio, (None, None))
            mime = MIME.get(Path(ruta).suffix.lower())
            if not tipo or not mime:
                continue  # Opcionales sin tipo en el diseño (acta del tutor) o textos de prueba: solo quedan en la carpeta.
            sha = hashlib.sha256(contenido).hexdigest()
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO archivo(sha256, tamano, tipo_mime, ruta_relativa, creado) VALUES(?,?,?,?,?)',
                                (sha, len(contenido), mime, ruta, _ahora()))
            if dueno == 'alumno':
                try:
                    prefijo = 'acta_' if espacio == 'acta_alumno' else f'{espacio}_'
                    datos = {k: v for k, v in extraidos.items() if k.startswith(prefijo) and not k.startswith('acta_tutor')}
                    if len(datos.get('acta_curps', [])) == 1:
                        datos['curp_encontrada'] = datos['acta_curps'][0]
                    nuevo = sp.procesar_expediente_extraido(self.db, alumno, tipo, sha, {'espacio': espacio, **datos}, self.actor)
                    documentos.append(nuevo['documento_id'])
                except sp.ProcedimientoError:
                    pass  # El mismo archivo ya estaba registrado para este alumno.
            else:
                identificador = str(uuid.uuid4())
                with self.db:
                    self.db.execute("INSERT INTO documento(id, tipo, tutor_id, archivo_sha256, origen, estado, recibido) "
                                    "VALUES(?,?,?,?,'buzon','recibido',?)", (identificador, tipo, tutor, sha, _ahora()))
                documentos.append(identificador)
        return {'alumno': alumno, 'tutor': tutor, 'documentos': documentos}

    def proponer(self, ids, resultado):
        """Lo que encontró el validador queda como propuesta (C10): la decide una persona."""
        contenido = {'estado': resultado['estado'], 'extraidos': resultado.get('extraidos', {}),
                     'reglas': sorted({h['regla'] for h in resultado['hallazgos']} | {g['regla'] for g in resultado['grises']}
                                      | {n['regla'] for n in resultado['no_leidos']})}
        with self.db:
            self.db.execute("INSERT INTO sugerencia_ia(id, objeto_tipo, objeto_id, tipo, contenido, fecha) VALUES(?, 'alumno', ?, 'validacion', ?, ?)",
                            (str(uuid.uuid4()), ids['alumno'], json.dumps(contenido, ensure_ascii=False), _ahora()))

    def decidir(self, ids, decision, motivo=None):
        """La decisión del administrador sobre cada documento, con sp_revisardocumento."""
        resultado = 'validado' if decision == 'autorizado' else 'rechazado'
        for documento in ids['documentos']:
            estado, version = self.db.execute('SELECT estado, version FROM documento WHERE id = ?', (documento,)).fetchone()
            if estado in ('recibido', 'validado', 'rechazado') and estado != resultado:
                sp.sp_revisardocumento(self.db, documento, resultado, self.actor, version, motivo)
        with self.db:
            self.db.execute("UPDATE sugerencia_ia SET estado = ?, decidio = ? WHERE objeto_id = ? AND estado = 'propuesta'",
                            ('aceptada' if decision == 'autorizado' else 'rechazada', self.actor, ids['alumno']))

    def resumen(self):
        """Cuántas filas hay en las tablas que toca el entorno de pruebas."""
        return {t: self.db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                for t in ('alumno', 'tutor', 'archivo', 'documento', 'revision_documento', 'sugerencia_ia', 'bitacora')}
