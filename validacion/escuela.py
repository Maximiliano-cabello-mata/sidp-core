"""Los datos de la escuela que llevan los documentos oficiales: el 911, las constancias y las listas de grupo.

Viven en la base del servidor (tabla escuela del diseño integral, una sola fila) y se escriben en el panel, en
Ajustes > Datos de la escuela. Nunca van al repositorio: es público y la clave del centro de trabajo (CCT) es de la escuela.
El motor de documentos (validacion/documentos.py) los recibe con cada pedido; la PC 4 no los guarda.
"""
import re
import unicodedata

CCT = re.compile(r'15[A-Z]PR\d{4}[A-Z]')  # Estado de México (15), primaria (PR): por ejemplo 15EPR0000X.
TURNOS = {'matutino': 'Matutino', 'vespertino': 'Vespertino', 'tiempo_completo': 'Tiempo completo'}
CAMPOS = ('nombre', 'cct', 'turno', 'zona_escolar', 'municipio', 'domicilio', 'director', 'subdirector')
NUEVAS = ('municipio', 'director', 'subdirector')  # No estaban en la primera versión de la tabla.
NECESARIOS = (('nombre', 'el nombre'), ('cct', 'la clave CCT'), ('turno', 'el turno'), ('municipio', 'el municipio'),
              ('director', 'el nombre del director'))


class ErrorEscuela(Exception):
    """Un dato de la escuela que no se puede guardar; el mensaje es para la persona."""


def _limpio(texto):
    return ' '.join(str(texto or '').split())


def _turno(texto):
    texto = unicodedata.normalize('NFKD', _limpio(texto).lower()).encode('ascii', 'ignore').decode().replace(' ', '_')
    return texto if texto in TURNOS else None


def faltan(datos):
    """Lo que le falta a la escuela para que los documentos salgan completos (en palabras)."""
    return [texto for campo, texto in NECESARIOS if not (datos or {}).get(campo)]


class Escuela:
    def __init__(self, db):
        self.db = db
        columnas = {fila[1] for fila in db.execute('PRAGMA table_info(escuela)')}
        for columna in NUEVAS:
            if columna not in columnas:
                db.execute(f'ALTER TABLE escuela ADD COLUMN {columna} TEXT')

    def datos(self):
        fila = self.db.execute(f'SELECT {", ".join(CAMPOS)} FROM escuela WHERE id = 1').fetchone()
        datos = dict(zip(CAMPOS, fila)) if fila else dict.fromkeys(CAMPOS)
        return {**datos, 'turno_texto': TURNOS.get(datos['turno']), 'completa': not faltan(datos), 'faltan': faltan(datos)}

    def guardar(self, pedido):
        datos = {campo: _limpio(pedido.get(campo)) or None for campo in CAMPOS}
        datos['cct'] = re.sub(r'[\s-]', '', datos['cct'] or '').upper() or None
        datos['turno'] = _turno(datos['turno'])
        if not datos['nombre']:
            raise ErrorEscuela('Escribe el nombre de la escuela, como aparece en el sello.')
        if not datos['cct'] or not CCT.fullmatch(datos['cct']):
            raise ErrorEscuela('La clave del centro de trabajo (CCT) tiene 10 letras y números y empieza con 15, '
                               'por ejemplo 15EPR0000X. Está en el sello de la escuela y en las boletas.')
        if not datos['turno']:
            raise ErrorEscuela('Elige el turno de la escuela.')
        valores = [datos[c] for c in CAMPOS]
        with self.db:
            self.db.execute(f'INSERT INTO escuela (id, {", ".join(CAMPOS)}) VALUES (1, {", ".join("?" * len(CAMPOS))}) '
                            f'ON CONFLICT(id) DO UPDATE SET {", ".join(f"{c} = excluded.{c}" for c in CAMPOS)}, version = version + 1',
                            valores)
        return self.datos()
