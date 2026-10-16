"""El expediente en la base de prueba: las 39 tablas del diseño integral y los procedimientos de Maximiliano.

Cuando un padre sube su expediente, se registran el alumno, el tutor, cada archivo (por su
sha256, sin sobrescribir) y cada documento. Lo que el validador extrajo queda en
sugerencia_ia como propuesta: la CURP no se confirma sola. La decisión del administrador
pasa por sp_revisardocumento, que deja la revisión y la bitácora. El vínculo del tutor con el
alumno se aplica solo al autorizar.

La CURP se valida ante RENAPO con la constancia que descarga una persona (validacion/renapo.py):
al coincidir, alumno.curp_confirmada pasa a 1 con sp_validar_curp_renapo.
"""
import datetime
import hashlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path

from database import procedimientos as sp
from validacion import comparador, renapo

RAIZ = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))  # Dentro del .exe, los datos incluidos.
DISENO = RAIZ / 'database' / 'diseno_integral.sql'
# Espacio de la página de padres -> (tipo_documento del diseño, de quién es).
TIPO_DISENO = {'acta_alumno': ('acta', 'alumno'), 'certificado_medico': ('certificado_medico', 'alumno'),
               'boleta': ('boleta_anterior', 'alumno'), 'ine_tutor': ('ine_tutor', 'tutor'),
               'comprobante': ('comprobante_domicilio', 'tutor'), 'constancia_curp': ('curp', 'alumno')}
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
        self.tipos_escuela = {}  # Documentos que agregó la escuela con una plantilla: clave -> (tipo, de quién).

    def usar_plantillas(self, plantillas):
        """Cada plantilla de la escuela es un tipo de documento en la base (tipo_documento), para poder registrarlo."""
        for plantilla in plantillas:
            if plantilla.get('fabrica'):
                continue
            clave, nombre = plantilla['clave'], plantilla['nombre']
            if self.db.execute('SELECT 1 FROM tipo_documento WHERE nombre = ? AND clave != ?', (nombre, clave)).fetchone():
                nombre = f'{nombre} (escuela)'  # El nombre es único en la base.
            with self.db:
                self.db.execute('INSERT INTO tipo_documento(clave, nombre, aplica_a, obligatorio_nuevo, caducidad) VALUES(?,?,?,?,?) '
                                'ON CONFLICT(clave) DO UPDATE SET nombre = excluded.nombre, obligatorio_nuevo = excluded.obligatorio_nuevo, '
                                'caducidad = excluded.caducidad, vigente = 1',
                                (clave, nombre, plantilla['de'], int(plantilla['obligatorio']),
                                 'fecha' if 'fecha_reciente' in plantilla['reglas'] else 'nunca'))
            self.tipos_escuela[clave] = (clave, plantilla['de'])

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

    def alumno_por(self, curp, nombre):
        """El alumno con esa CURP; si no, el único alumno sin CURP que se llama exactamente igual (sin acentos)."""
        curp = curp if curp and comparador.desglose_curp(curp) else None
        if curp:
            fila = self.db.execute('SELECT id FROM alumno WHERE curp = ?', (curp,)).fetchone()
            if fila:
                return fila[0]
        buscado = comparador.normalizar(nombre or '')
        iguales = [i for i, n, p, s in self.db.execute("SELECT id, nombres, primer_apellido, segundo_apellido FROM alumno WHERE curp IS NULL AND estado = 'activo'")
                   if comparador.normalizar(' '.join(x for x in (n, p, s) if x)) == buscado] if buscado else []
        return iguales[0] if len(iguales) == 1 else None

    def nuevo_alumno(self, datos, origen='lista_de_grupo'):
        desglose = comparador.desglose_curp(datos['curp']) if datos.get('curp') else None
        # Con una CURP bien formada, la fecha de nacimiento y el sexo salen de ella (dato para el 911).
        return self._insertar('alumno', {'curp': datos['curp'] if desglose else None, 'nombres': datos['nombres'],
                                         'primer_apellido': datos['primer_apellido'], 'segundo_apellido': datos.get('segundo_apellido') or None,
                                         'fecha_nacimiento': desglose and desglose['fecha'], 'sexo': desglose and desglose['sexo']}, origen)

    def completar_alumno(self, alumno_id, datos, origen='escaneo'):
        """El alumno de la lista recibe lo que confirmó la persona al escanear (nombre corregido, CURP, fecha, sexo)."""
        fila = self.db.execute('SELECT curp, nombres, primer_apellido, segundo_apellido, fecha_nacimiento, sexo, version FROM alumno WHERE id = ?',
                               (alumno_id,)).fetchone()
        if not fila:
            raise sp.ProcedimientoError('Ese alumno no existe.')
        antes = dict(zip(('curp', 'nombres', 'primer_apellido', 'segundo_apellido', 'fecha_nacimiento', 'sexo'), fila[:6]))
        desglose = comparador.desglose_curp(datos['curp']) if datos.get('curp') else None
        curp = datos['curp'] if desglose else None
        if curp and curp != antes['curp'] and self.db.execute('SELECT 1 FROM alumno WHERE curp = ? AND id != ?', (curp, alumno_id)).fetchone():
            raise sp.ProcedimientoError(f'La CURP {curp} ya es de otro alumno.')
        despues = {'curp': curp or antes['curp'], 'nombres': datos.get('nombres') or antes['nombres'],
                   'primer_apellido': datos.get('primer_apellido') or antes['primer_apellido'],
                   'segundo_apellido': datos.get('segundo_apellido') or antes['segundo_apellido'],
                   'fecha_nacimiento': datos.get('fecha_nacimiento') or antes['fecha_nacimiento'] or (desglose and desglose['fecha']),
                   'sexo': datos.get('sexo') if datos.get('sexo') in ('H', 'M') else antes['sexo'] or (desglose and desglose['sexo'])}
        cambios = {k: v for k, v in despues.items() if v != antes[k]}
        if cambios:
            with self.db:
                self.db.execute(f'UPDATE alumno SET {", ".join(f"{k} = ?" for k in cambios)}, version = version + 1 WHERE id = ?',
                                (*cambios.values(), alumno_id))
                self.db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, antes, despues) VALUES(?,?,?,?,?,?,?)',
                                (_ahora(), origen, 'alumno.completado', 'alumno', alumno_id,
                                 json.dumps({k: antes[k] for k in cambios}, ensure_ascii=False), json.dumps(cambios, ensure_ascii=False)))
        return alumno_id

    def _insertar(self, tabla, columnas, origen):
        identificador = str(uuid.uuid4())
        columnas = {'id': identificador, **columnas}
        with self.db:
            self.db.execute(f'INSERT INTO {tabla}({", ".join(columnas)}) VALUES({", ".join("?" * len(columnas))})',
                            tuple(columnas.values()))
            self.db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, despues) VALUES(?,?,?,?,?,?)',
                            (_ahora(), origen, f'{tabla}.registrado', tabla, identificador,
                             json.dumps({k: v for k, v in columnas.items() if k != 'id'}, ensure_ascii=False)))
        return identificador

    def _persona(self, tabla, datos, curp=None):
        curp = curp if curp and comparador.desglose_curp(curp) else None  # Una CURP mal escrita no entra como dato.
        if curp:
            fila = self.db.execute(f'SELECT id FROM {tabla} WHERE curp = ?', (curp,)).fetchone()
            if fila:
                return fila[0]
        identificador = str(uuid.uuid4())
        columnas = {'id': identificador, 'curp': curp, 'nombres': datos['nombres'], 'primer_apellido': datos['primer_apellido'],
                    'segundo_apellido': datos.get('segundo_apellido') or None}
        if tabla == 'alumno':  # Del escaneo vienen también la fecha de nacimiento y el sexo.
            columnas.update(fecha_nacimiento=datos.get('fecha_nacimiento') or None,
                            sexo=datos.get('sexo') if datos.get('sexo') in ('H', 'M') else None)
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

    def registrar(self, captura, archivos, extraidos=None, alumno_id=None):
        """captura: lo que escribió el padre; archivos: [(espacio, ruta relativa a la carpeta de datos, contenido)].

        extraidos: lo que el validador encontró (resultado['extraidos']); cada documento recibe lo suyo.
        Devuelve los identificadores para guardarlos junto al expediente.
        """
        extraidos = extraidos or {}
        tipos = {**TIPO_DISENO, **self.tipos_escuela}
        if alumno_id:  # El alumno de la lista de su grupo que eligió la persona.
            alumno = self.completar_alumno(alumno_id, {**captura['alumno'], 'curp': captura['alumno'].get('curp', '').upper()})
        else:
            datos_alumno = {**captura['alumno'], 'curp': captura['alumno'].get('curp', '').upper()}
            nombre = ' '.join(filter(None, (datos_alumno.get('nombres'), datos_alumno.get('primer_apellido'), datos_alumno.get('segundo_apellido'))))
            # Si ya está en la lista de su grupo con el mismo nombre (o la misma CURP), se usa ese alumno y solo se
            # llenan los datos que le faltan; el nombre de la lista no cambia.
            alumno = self.alumno_por(datos_alumno['curp'], nombre)
            if alumno:
                self.completar_alumno(alumno, {k: datos_alumno.get(k) for k in ('curp', 'fecha_nacimiento', 'sexo')},
                                      'escaneo' if captura.get('origen') == 'escaneo' else 'pagina_padres')
            else:
                alumno = self._persona('alumno', datos_alumno, datos_alumno['curp'])
        datos_tutor = captura.get('tutor') or {}
        tutor = self._persona('tutor', datos_tutor, str(datos_tutor.get('curp') or '').upper()) if datos_tutor.get('nombres') else None
        parentesco = datos_tutor.get('parentesco', 'otro')
        # El vínculo con el alumno es solo una solicitud: se aplica cuando el administrador autoriza.
        # Así nadie queda como tutor de un niño con solo escribir su CURP.
        parentesco = parentesco if parentesco in ('madre', 'padre', 'tutor_legal', 'abuelo') else 'otro'
        documentos = []
        for espacio, ruta, contenido in archivos:
            tipo, dueno = tipos.get(espacio, (None, None))
            mime = MIME.get(Path(ruta).suffix.lower())
            if not tipo or not mime or (dueno == 'tutor' and not tutor):
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
                                    "VALUES(?,?,?,?,?,'recibido',?)", (identificador, tipo, tutor, sha,
                                                                       'escaneo' if captura.get('origen') == 'escaneo' else 'buzon', _ahora()))
                documentos.append(identificador)
        return {'alumno': alumno, 'tutor': tutor, 'parentesco': parentesco, 'documentos': documentos}

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
        if decision == 'autorizado' and 'parentesco' in ids and ids['tutor']:  # Expedientes anteriores ya traían el vínculo.
            sp.sp_asignar_tutor(self.db, ids['alumno'], ids['tutor'], ids['parentesco'], self.actor)

    def _ultimo_renapo(self, alumno_id):
        fila = self.db.execute("SELECT accion, despues, fecha FROM bitacora WHERE objeto_tipo = 'alumno' AND objeto_id = ? "
                               "AND accion LIKE 'alumno.renapo_%' ORDER BY secuencia DESC LIMIT 1", (alumno_id,)).fetchone()
        return (fila[0].split('renapo_', 1)[1], json.loads(fila[1] or '{}'), fila[2]) if fila else (None, {}, None)

    def curps(self):
        """Cada alumno con el estado de su CURP ante RENAPO; primero lo que falta por hacer."""
        orden = {'no_coincide': 0, 'sin_validar': 1, 'no_encontrada': 2, 'sin_curp': 3, 'validada': 4}
        filas = []
        for identificador, curp, confirmada, *nombre in self.db.execute(
                'SELECT id, curp, curp_confirmada, nombres, primer_apellido, segundo_apellido FROM alumno'):
            ultimo, detalle, fecha = self._ultimo_renapo(identificador)
            estado = 'validada' if confirmada else 'sin_curp' if not curp else ultimo if ultimo in ('no_coincide', 'no_encontrada') else 'sin_validar'
            filas.append({'alumno': identificador, 'curp': curp, 'nombre': ' '.join(n for n in nombre if n), 'estado': estado,
                          'texto': renapo.ESTADOS[estado], 'detalle': detalle.get('motivo') if estado == 'no_coincide' else None,
                          'fecha': fecha if estado != 'sin_validar' else None})
        return sorted(filas, key=lambda f: (orden[f['estado']], f['nombre']))

    def validar_constancia(self, contenido, guardar):
        """La constancia de RENAPO que arrastró la persona: encuentra al alumno por la CURP y compara el nombre.

        guardar(): guarda el PDF y devuelve su ruta; solo se llama si la constancia es de un alumno.
        """
        lectura = renapo.leer_constancia(contenido)
        alumnos = {f['curp']: f for f in self.curps() if f['curp']}
        encontrados = [alumnos[c] for c in lectura['curps'] if c in alumnos]
        if not encontrados:
            parecidos = [f for f in alumnos.values() if not renapo.faltan_del_nombre(lectura['texto'], f['nombre'])]
            curp = lectura['curps'][0]
            if len(parecidos) == 1:
                alumno = parecidos[0]
                self._guardar_archivo(guardar(), contenido)
                motivo = (f'La constancia trae la CURP {curp}, pero el padre escribió {alumno["curp"]}. '
                          'Confirma con el padre cuál es la correcta.')
                self._constancia(alumno['alumno'], contenido, 'rechazado', motivo)
                return {'estado': 'no_coincide', 'alumno': alumno['nombre'], 'mensaje': motivo}
            raise renapo.ErrorConstancia(f'Ningún alumno tiene la CURP {curp}. Revisa que hayas buscado la CURP correcta.')
        alumno = encontrados[0]
        if alumno['estado'] == 'validada':
            return {'estado': 'validada', 'alumno': alumno['nombre'], 'mensaje': f'La CURP de {alumno["nombre"]} ya estaba validada.'}
        self._guardar_archivo(guardar(), contenido)
        faltan = renapo.faltan_del_nombre(lectura['texto'], alumno['nombre'])
        if faltan:
            motivo = (f'En la constancia de RENAPO no aparece {", ".join(faltan)}. '
                      f'Revisa con el padre cómo está escrito el nombre ({alumno["nombre"]}).')
            self._constancia(alumno['alumno'], contenido, 'rechazado', motivo)
            return {'estado': 'no_coincide', 'alumno': alumno['nombre'], 'mensaje': motivo}
        partes = self.db.execute('SELECT primer_apellido, segundo_apellido, nombres FROM alumno WHERE id = ?', (alumno['alumno'],)).fetchone()
        corregido = renapo.nombre_de_renapo(lectura['texto'], alumno['curp'], *partes)
        if corregido:  # En la lista venía pegado ("GARCIALOPEZ"): queda como lo escribe RENAPO.
            self.completar_alumno(alumno['alumno'], corregido, origen='constancia RENAPO')
        self._constancia(alumno['alumno'], contenido, 'validado')
        nombre = ' '.join(x for x in (corregido['nombres'], corregido['primer_apellido'], corregido['segundo_apellido']) if x) if corregido else None
        return {'estado': 'validada', 'alumno': nombre or alumno['nombre'], 'corregido': corregido,
                'mensaje': f'Listo: la CURP de {nombre or alumno["nombre"]} quedó validada en RENAPO.'
                           + (f' En la lista el nombre venía pegado ({alumno["nombre"]}); quedó como lo escribe RENAPO.' if corregido else '')}

    def _guardar_archivo(self, ruta, contenido):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO archivo(sha256, tamano, tipo_mime, ruta_relativa, creado) VALUES(?,?,?,?,?)',
                            (hashlib.sha256(contenido).hexdigest(), len(contenido), 'application/pdf', ruta, _ahora()))

    def _constancia(self, alumno_id, contenido, resultado, motivo=None):
        version = self.db.execute('SELECT version FROM alumno WHERE id = ?', (alumno_id,)).fetchone()[0]
        try:
            sp.sp_validar_curp_renapo(self.db, alumno_id, hashlib.sha256(contenido).hexdigest(), resultado, self.actor, version, motivo)
        except sp.ProcedimientoError as error:
            raise renapo.ErrorConstancia(str(error)) from error

    def renapo_no_encontrada(self, alumno_id):
        """La persona buscó la CURP en RENAPO y no apareció: queda anotado para hablar con el padre."""
        fila = self.db.execute('SELECT curp FROM alumno WHERE id = ?', (alumno_id,)).fetchone()
        if not fila:
            raise renapo.ErrorConstancia('No existe ese alumno.')
        with self.db:
            self.db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, despues) VALUES(?,?,?,?,?,?)',
                            (_ahora(), self.actor, 'alumno.renapo_no_encontrada', 'alumno', alumno_id,
                             json.dumps({'curp': fila[0]}, ensure_ascii=False)))

    def resumen(self):
        """Cuántas filas hay en las tablas que toca el entorno de pruebas."""
        return {t: self.db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                for t in ('alumno', 'tutor', 'archivo', 'documento', 'revision_documento', 'sugerencia_ia', 'bitacora')}
