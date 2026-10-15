"""Grupos y sus alumnos, a partir de las listas que ya tiene la escuela.

El trabajo empieza por las listas de cada grupo (una hoja por grupo, impresa o escrita a mano):
se escanean, el sistema propone los renglones y la persona corrige y guarda. Así cada expediente
que se escanee después se liga a un alumno que ya está en su grado y grupo.

Los nombres no siempre se leen bien (letra a mano, OCR). Por eso, para ligar un expediente con
un alumno de la lista, se compara el nombre sin importar el orden ni los acentos y se proponen
los parecidos; la persona elige. Nunca se liga solo.
"""
import datetime
import difflib
import json
import uuid

from database import procedimientos as sp
from validacion import comparador

LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
PARECIDO_SEGURO = 0.9   # Arriba de esto se propone como "es este alumno".
PARECIDO_MINIMO = 0.6   # Arriba de esto se muestra como posible.


class ErrorGrupo(Exception):
    """Algo que la persona debe corregir; el mensaje es para ella."""


def _ahora():
    return datetime.datetime.now().isoformat(timespec='seconds')


def nombre_completo(nombres, primero, segundo=None):
    return ' '.join(p for p in (nombres, primero, segundo) if p)


def parecido(a, b):
    """0 a 1: qué tanto se parecen dos nombres, sin importar el orden de las palabras ni los acentos."""
    a, b = comparador.normalizar(a or ''), comparador.normalizar(b or '')
    if not a or not b:
        return 0.0
    directo = difflib.SequenceMatcher(None, a, b).ratio()
    ordenado = difflib.SequenceMatcher(None, ' '.join(sorted(a.split())), ' '.join(sorted(b.split()))).ratio()
    return round(max(directo, ordenado), 3)


def ciclo_de(hoy):
    """El ciclo escolar de una fecha: de agosto a julio."""
    inicio = hoy.year if hoy.month >= 8 else hoy.year - 1
    return f'{inicio}-{inicio + 1}', f'{inicio}-08-01', f'{inicio + 1}-07-31'


class Grupos:
    def __init__(self, registro, hoy=None):
        self.registro = registro
        self.db = registro.db
        self.hoy = hoy or datetime.date.today()

    def ciclo(self):
        nombre, inicio, fin = ciclo_de(self.hoy)
        fila = self.db.execute('SELECT id FROM ciclo WHERE nombre = ?', (nombre,)).fetchone()
        if fila:
            return fila[0], nombre
        identificador = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO ciclo(id, nombre, inicio, fin) VALUES(?,?,?,?)', (identificador, nombre, inicio, fin))
        return identificador, nombre

    def lista(self):
        """Los grupos del ciclo actual con cuántos alumnos tienen y cuántos ya tienen documentos."""
        ciclo, nombre = self.ciclo()
        filas = self.db.execute(
            "SELECT g.id, g.grado, g.letra, COUNT(DISTINCT i.id), "
            "COUNT(DISTINCT CASE WHEN d.id IS NOT NULL THEN i.alumno_id END), "
            "COUNT(DISTINCT CASE WHEN a.curp IS NULL THEN i.alumno_id END) "
            "FROM grupo g LEFT JOIN inscripcion i ON i.grupo_id = g.id AND i.estado IN ('incompleta','completa') "
            "LEFT JOIN alumno a ON a.id = i.alumno_id "
            "LEFT JOIN documento d ON d.alumno_id = i.alumno_id "
            "WHERE g.ciclo_id = ? GROUP BY g.id ORDER BY g.grado, g.letra", (ciclo,)).fetchall()
        return {'ciclo': nombre, 'grupos': [{'id': i, 'grado': g, 'letra': l, 'nombre': f'{g}° {l}', 'alumnos': n,
                                             'con_documentos': c, 'sin_curp': s} for i, g, l, n, c, s in filas]}

    @staticmethod
    def validar_grupo(grado, letra):
        try:
            grado = int(grado)
        except (TypeError, ValueError):
            grado = 0
        letra = str(letra or '').strip().upper()
        if not 1 <= grado <= 6:
            raise ErrorGrupo('Elige el grado, de 1° a 6°.')
        if len(letra) != 1 or letra not in LETRAS:
            raise ErrorGrupo('Elige la letra del grupo (A, B, C...).')
        return grado, letra

    def crear(self, grado, letra):
        grado, letra = self.validar_grupo(grado, letra)
        ciclo, _ = self.ciclo()
        fila = self.db.execute('SELECT id FROM grupo WHERE ciclo_id = ? AND grado = ? AND letra = ?', (ciclo, grado, letra)).fetchone()
        if fila:
            return fila[0]
        identificador = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO grupo(id, ciclo_id, grado, letra) VALUES(?,?,?,?)', (identificador, ciclo, grado, letra))
            self.db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, despues) VALUES(?,?,?,?,?,?)',
                            (_ahora(), self.registro.actor, 'grupo.creado', 'grupo', identificador,
                             json.dumps({'grado': grado, 'letra': letra}, ensure_ascii=False)))
        return identificador

    def _grupo(self, grupo_id):
        fila = self.db.execute('SELECT grado, letra, ciclo_id FROM grupo WHERE id = ?', (grupo_id,)).fetchone()
        if not fila:
            raise ErrorGrupo('Ese grupo no existe.')
        return fila

    def alumnos(self, grupo_id):
        """Los alumnos de un grupo, por apellido, con lo que ya se sabe de cada uno."""
        grado, letra, _ = self._grupo(grupo_id)
        filas = self.db.execute(
            "SELECT a.id, a.nombres, a.primer_apellido, a.segundo_apellido, a.curp, a.curp_confirmada, a.sexo, a.fecha_nacimiento, "
            "(SELECT COUNT(*) FROM documento d WHERE d.alumno_id = a.id), "
            "(SELECT COUNT(*) FROM documento d WHERE d.alumno_id = a.id AND d.estado = 'validado'), "
            "(SELECT t.nombres || ' ' || t.primer_apellido || COALESCE(' ' || t.segundo_apellido, '') || '|' || COALESCE(t.telefono, '') "
            " FROM alumno_tutor x JOIN tutor t ON t.id = x.tutor_id WHERE x.alumno_id = a.id ORDER BY x.principal DESC LIMIT 1) "
            "FROM inscripcion i JOIN alumno a ON a.id = i.alumno_id "
            "WHERE i.grupo_id = ? AND i.estado IN ('incompleta','completa') "
            "ORDER BY a.primer_apellido, a.segundo_apellido, a.nombres", (grupo_id,)).fetchall()
        alumnos = []
        for i, n, p, s, curp, confirmada, sexo, fecha, documentos, validados, tutor in filas:
            tutor_nombre, _, telefono = (tutor or '|').partition('|')
            alumnos.append({'id': i, 'nombre': nombre_completo(n, p, s), 'nombres': n, 'primer_apellido': p, 'segundo_apellido': s or '',
                            'curp': curp, 'curp_confirmada': bool(confirmada), 'sexo': sexo, 'fecha_nacimiento': fecha,
                            'documentos': documentos, 'validados': validados, 'tutor': tutor_nombre or None, 'telefono': telefono or None})
        return {'grupo': {'id': grupo_id, 'grado': grado, 'letra': letra, 'nombre': f'{grado}° {letra}'}, 'alumnos': alumnos}

    @staticmethod
    def revisar_filas(filas):
        """Los renglones limpios de una lista; un renglón incompleto o con CURP mal formada detiene todo, con su número."""
        limpias = []
        for numero, fila in enumerate(filas, 1):
            datos = {k: ' '.join(str(fila.get(k) or '').split()).upper() for k in ('nombres', 'primer_apellido', 'segundo_apellido', 'curp')}
            if not any(datos.values()):
                continue
            if not datos['nombres'] or not datos['primer_apellido']:
                raise ErrorGrupo(f'Renglón {numero}: faltan el nombre o el primer apellido.')
            if datos['curp'] and not comparador.desglose_curp(datos['curp']):
                raise ErrorGrupo(f'Renglón {numero}: la CURP {datos["curp"]} no tiene la forma correcta. Corrígela o déjala vacía.')
            limpias.append(datos)
        if not limpias:
            raise ErrorGrupo('La lista está vacía.')
        return limpias

    def guardar_lista(self, grupo_id, filas):
        """Agrega a un grupo los alumnos de su lista. filas: [{nombres, primer_apellido, segundo_apellido, curp}].

        Si un alumno ya existe (misma CURP, o mismo nombre sin CURP), no se duplica.
        """
        grado, _, ciclo = self._grupo(grupo_id)
        limpias = self.revisar_filas(filas)
        agregados, ya_estaban = 0, 0
        for datos in limpias:
            alumno = self.registro.alumno_por(datos['curp'], nombre_completo(datos['nombres'], datos['primer_apellido'], datos['segundo_apellido']))
            if not alumno:
                alumno = self.registro.nuevo_alumno(datos, 'lista_de_grupo')
            if self.db.execute("SELECT 1 FROM inscripcion WHERE alumno_id = ? AND ciclo_id = ? AND estado <> 'cancelada'",
                               (alumno, ciclo)).fetchone():
                ya_estaban += 1
                continue
            sp.sp_inscribir_alumno(self.db, alumno, ciclo, grupo_id, 'nuevo_ingreso' if grado == 1 else 'reinscripcion',
                                   self.registro.actor, origen='importacion')
            agregados += 1
        return {'agregados': agregados, 'ya_estaban': ya_estaban, **self.alumnos(grupo_id)}

    def ubicar(self, alumno_id, grupo_id=None, mismo_que=None):
        """Pone en su grupo a un alumno que llegó por la página de padres y no estaba en las listas.

        mismo_que: el alumno de la lista que es la misma persona. Ese renglón de la lista (sin documentos)
        se cancela y este alumno toma su lugar en el grupo; nada se borra y queda en la bitácora.
        """
        ciclo, _ = self.ciclo()
        if not self.db.execute("SELECT 1 FROM alumno WHERE id = ? AND estado = 'activo'", (alumno_id,)).fetchone():
            raise ErrorGrupo('Ese alumno no existe.')
        if self.ubicacion(alumno_id):
            raise ErrorGrupo(f'Ese alumno ya está en {self.ubicacion(alumno_id)}.')
        if mismo_que:
            fila = self.db.execute("SELECT id, grupo_id FROM inscripcion WHERE alumno_id = ? AND ciclo_id = ? AND estado IN ('incompleta','completa')",
                                   (mismo_que, ciclo)).fetchone()
            if not fila or mismo_que == alumno_id:
                raise ErrorGrupo('Ese alumno de la lista ya no está en un grupo: vuelve a cargar.')
            if self.db.execute('SELECT 1 FROM documento WHERE alumno_id = ?', (mismo_que,)).fetchone():
                raise ErrorGrupo('El alumno de la lista ya tiene documentos propios: no se pueden juntar aquí. Avisa a quien administra el sistema.')
            inscripcion, grupo_id = fila
        else:
            self._grupo(grupo_id or '')
        grado = self._grupo(grupo_id)[0]
        if mismo_que:
            with self.db:
                self.db.execute("UPDATE inscripcion SET estado = 'cancelada', version = version + 1 WHERE id = ?", (inscripcion,))
                self.db.execute("UPDATE alumno SET estado = 'archivado', version = version + 1 WHERE id = ?", (mismo_que,))
                self.db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, antes, despues) VALUES(?,?,?,?,?,?,?)',
                                (_ahora(), self.registro.actor, 'alumno.unido', 'alumno', alumno_id,
                                 json.dumps({'renglon_de_lista': mismo_que}), json.dumps({'alumno': alumno_id, 'grupo': grupo_id})))
        sp.sp_inscribir_alumno(self.db, alumno_id, ciclo, grupo_id, 'nuevo_ingreso' if grado == 1 else 'reinscripcion',
                               self.registro.actor, origen='captura')
        return self.ubicacion(alumno_id)

    def parecidos(self, nombre, curp=None, buscar=False):
        """Alumnos de las listas que podrían ser esta persona, del más parecido al menos."""
        if not nombre and not curp:
            return []
        ciclo, _ = self.ciclo()
        candidatos = []
        busqueda = comparador.normalizar(nombre or '').split() if buscar else []
        for i, n, p, s, c, grado, letra, grupo_id in self.db.execute(
                "SELECT a.id, a.nombres, a.primer_apellido, a.segundo_apellido, a.curp, g.grado, g.letra, g.id FROM inscripcion x "
                "JOIN alumno a ON a.id = x.alumno_id JOIN grupo g ON g.id = x.grupo_id "
                "WHERE x.ciclo_id = ? AND x.estado IN ('incompleta','completa')", (ciclo,)):
            completo = nombre_completo(n, p, s)
            puntos = 1.0 if curp and c == curp else parecido(nombre, completo)
            if busqueda:  # Al buscar, "luis hern" encuentra a LUIS HERNANDEZ RAMOS.
                palabras = comparador.normalizar(completo).split()
                if all(any(p.startswith(b) for p in palabras) for b in busqueda):
                    puntos = max(puntos, 0.8)
            if c and curp and c != curp:
                puntos = min(puntos, 0.5)  # Las dos CURP existen y son distintas: no es la misma persona.
            if puntos >= PARECIDO_MINIMO:
                candidatos.append({'id': i, 'nombre': completo, 'curp': c, 'grupo': f'{grado}° {letra}', 'grupo_id': grupo_id,
                                   'parecido': puntos, 'seguro': puntos >= PARECIDO_SEGURO})
        return sorted(candidatos, key=lambda c: (-c['parecido'], c['nombre']))[:8 if buscar else 5]

    def ubicacion(self, alumno_id):
        """'3° A' del alumno en el ciclo actual, o None."""
        ciclo, _ = self.ciclo()
        fila = self.db.execute("SELECT g.grado, g.letra FROM inscripcion i JOIN grupo g ON g.id = i.grupo_id "
                               "WHERE i.alumno_id = ? AND i.ciclo_id = ? AND i.estado IN ('incompleta','completa')",
                               (alumno_id, ciclo)).fetchone()
        return f'{fila[0]}° {fila[1]}' if fila else None

    def conteo(self):
        """Alumnos por grado y sexo (base de la hoja del 911). Los que no tienen sexo cuentan aparte."""
        ciclo, nombre = self.ciclo()
        filas = self.db.execute(
            "SELECT g.grado, COALESCE(a.sexo, '?'), COUNT(*) FROM inscripcion i JOIN grupo g ON g.id = i.grupo_id "
            "JOIN alumno a ON a.id = i.alumno_id WHERE i.ciclo_id = ? AND i.estado IN ('incompleta','completa') "
            "GROUP BY g.grado, a.sexo", (ciclo,)).fetchall()
        tabla = {grado: {'H': 0, 'M': 0, '?': 0} for grado in range(1, 7)}
        for grado, sexo, cuantos in filas:
            tabla[grado][sexo if sexo in ('H', 'M') else '?'] += cuantos
        grupos = dict(self.db.execute('SELECT grado, COUNT(*) FROM grupo WHERE ciclo_id = ? GROUP BY grado', (ciclo,)).fetchall())
        return {'ciclo': nombre, 'grados': [{'grado': g, 'hombres': t['H'], 'mujeres': t['M'], 'sin_dato': t['?'],
                                             'total': sum(t.values()), 'grupos': grupos.get(g, 0)} for g, t in tabla.items()]}

    def padron(self):
        """(ciclo, alumnos con CURP del ciclo con su grado y grupo): lo que se manda a la base del cerebro."""
        ciclo, nombre = self.ciclo()
        filas = self.db.execute(
            "SELECT a.curp, a.primer_apellido, COALESCE(a.segundo_apellido, ''), a.nombres, g.grado, g.letra "
            "FROM inscripcion i JOIN grupo g ON g.id = i.grupo_id JOIN alumno a ON a.id = i.alumno_id "
            "WHERE i.ciclo_id = ? AND i.estado IN ('incompleta','completa') AND a.curp IS NOT NULL", (ciclo,)).fetchall()
        return nombre, [{'curp': c, 'primer_apellido': p, 'segundo_apellido': s, 'nombres': n, 'grado': g, 'letra': l}
                        for c, p, s, n, g, l in filas]

    def exportar_alumnos(self):
        """Todos los alumnos del ciclo como renglones para CSV o Excel."""
        ciclo, _ = self.ciclo()
        encabezado = ['Grado', 'Grupo', 'Primer apellido', 'Segundo apellido', 'Nombre(s)', 'CURP', 'CURP validada en RENAPO',
                      'Sexo', 'Fecha de nacimiento', 'Tutor', 'Parentesco', 'Teléfono', 'Documentos', 'Documentos validados']
        filas = self.db.execute(
            "SELECT g.grado, g.letra, a.primer_apellido, COALESCE(a.segundo_apellido, ''), a.nombres, COALESCE(a.curp, ''), "
            "CASE a.curp_confirmada WHEN 1 THEN 'Sí' ELSE 'No' END, COALESCE(a.sexo, ''), COALESCE(a.fecha_nacimiento, ''), "
            "COALESCE((SELECT t.nombres || ' ' || t.primer_apellido || COALESCE(' ' || t.segundo_apellido, '') FROM alumno_tutor x "
            "  JOIN tutor t ON t.id = x.tutor_id WHERE x.alumno_id = a.id ORDER BY x.principal DESC LIMIT 1), ''), "
            "COALESCE((SELECT x.parentesco FROM alumno_tutor x WHERE x.alumno_id = a.id ORDER BY x.principal DESC LIMIT 1), ''), "
            "COALESCE((SELECT t.telefono FROM alumno_tutor x JOIN tutor t ON t.id = x.tutor_id WHERE x.alumno_id = a.id "
            "  ORDER BY x.principal DESC LIMIT 1), ''), "
            "(SELECT COUNT(*) FROM documento d WHERE d.alumno_id = a.id), "
            "(SELECT COUNT(*) FROM documento d WHERE d.alumno_id = a.id AND d.estado = 'validado') "
            "FROM inscripcion i JOIN grupo g ON g.id = i.grupo_id JOIN alumno a ON a.id = i.alumno_id "
            "WHERE i.ciclo_id = ? AND i.estado IN ('incompleta','completa') "
            "ORDER BY g.grado, g.letra, a.primer_apellido, a.segundo_apellido, a.nombres", (ciclo,)).fetchall()
        return [encabezado] + [list(f) for f in filas]
