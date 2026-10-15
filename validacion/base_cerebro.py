"""La base de datos del cerebro (PC 4), en PostgreSQL.

Guarda el padrón de alumnos que manda SIDP-Validador.exe y una anotación de cada lectura. Con él, el
cerebro compara lo que lee contra los nombres y CURP reales de la escuela: si el OCR o la letra a mano
dejan una CURP con una o dos letras distintas, o un apellido mal escrito, propone al alumno correcto.
Siempre es propuesta: la persona confirma.

PostgreSQL escucha solo en 127.0.0.1 (como Ollama): nadie de la red entra a la base; todo pasa por el
cerebro, que pide su clave. La dirección con la contraseña vive fuera del repositorio, en
%USERPROFILE%\\.sidp\\base_cerebro.txt, con esta forma:
    postgresql://sidp:CONTRASEÑA@127.0.0.1:5432/sidp_cerebro

Sin PostgreSQL el cerebro funciona igual, solo que sin comparar contra el padrón.

En la PC 4, desde la raíz del repositorio:
    python -m validacion.base_cerebro      # crea las tablas (si faltan) y dice cuántos alumnos hay
"""
import json
import os
import re
import sys
import threading
import urllib.parse
from pathlib import Path

from validacion import extraer
from validacion.expediente import mayusculas

ESQUEMA = Path(__file__).with_name('base_cerebro.sql')
ARCHIVO = Path.home() / '.sidp' / 'base_cerebro.txt'
CURP_MAXIMO = 2       # Letras distintas que se aceptan para proponer una CURP del padrón.
NOMBRE_MINIMO = 0.6   # Parecido mínimo para proponer a un alumno por su nombre.


class ErrorBase(Exception):
    pass


def direccion(archivo=ARCHIVO):
    """La dirección de la base: la variable SIDP_BASE o el archivo de la PC 4. None si no hay."""
    if os.environ.get('SIDP_BASE'):
        return os.environ['SIDP_BASE'].strip()
    archivo = Path(archivo)
    return archivo.read_text(encoding='utf-8').lstrip('\ufeff').strip() or None if archivo.exists() else None  # Sin la marca BOM de PowerShell.


def normalizar(texto):
    """Mayúsculas, sin acentos ni letras griegas, solo letras y números separados por un espacio."""
    return ' '.join(re.sub(r'[^A-Z0-9Ñ]+', ' ', mayusculas(texto)).split())


class BaseCerebro:
    def __init__(self, url):
        try:
            import pg8000.dbapi
        except ImportError:
            raise ErrorBase('falta pg8000: python -m pip install -r validacion/requisitos.txt')
        partes = urllib.parse.urlsplit(url)
        try:
            self.conexion = pg8000.dbapi.connect(
                user=urllib.parse.unquote(partes.username or 'sidp'), password=urllib.parse.unquote(partes.password or ''),
                host=partes.hostname or '127.0.0.1', port=partes.port or 5432, database=partes.path.lstrip('/') or 'sidp_cerebro',
                timeout=10)
        except Exception as error:
            raise ErrorBase(f'no se pudo conectar a PostgreSQL ({type(error).__name__})')
        self.conexion.autocommit = True
        self._candado = threading.Lock()  # Una conexión para todo el cerebro: una consulta a la vez.

    def _consulta(self, sql, parametros=()):
        with self._candado:
            cursor = self.conexion.cursor()
            cursor.execute(sql, parametros) if parametros else cursor.execute(sql)
            try:
                return cursor.fetchall()
            except Exception:  # Sentencias sin filas (CREATE, INSERT).
                return []

    def preparar(self):
        """Crea las extensiones, tablas y funciones que falten. No borra nada."""
        self._consulta(ESQUEMA.read_text(encoding='utf-8'))
        return self

    def resumen(self):
        version = self._consulta('SHOW server_version')[0][0]
        alumnos = self._consulta('SELECT count(*) FROM padron_alumno WHERE activo')[0][0]
        lecturas = self._consulta('SELECT count(*) FROM lectura')[0][0]
        return {'motor': f'PostgreSQL {version.split()[0]}', 'alumnos': alumnos, 'lecturas': lecturas}

    def cargar(self, ciclo, alumnos):
        """alumnos: [{curp, primer_apellido, segundo_apellido, nombres, grado, letra}]. Devuelve cuántos se cargaron."""
        datos = [{**a, 'curp': str(a.get('curp') or '').upper(),
                  'nombre_completo': normalizar(' '.join(filter(None, (a.get('nombres'), a.get('primer_apellido'),
                                                                        a.get('segundo_apellido')))))}
                 for a in alumnos if a.get('curp') and a.get('nombres') and a.get('primer_apellido')]
        return self._consulta('SELECT sidp_cargar_padron(CAST(%s AS jsonb), %s)', (json.dumps(datos), str(ciclo)))[0][0]

    @staticmethod
    def _alumno(fila, extra):
        curp, valor, primer, segundo, nombres, grado, letra = fila
        return {'curp': curp, **extra(valor), 'primer_apellido': primer, 'segundo_apellido': segundo, 'nombres': nombres,
                'grado': grado, 'letra': letra}

    def sugerir(self, texto):
        """Los alumnos del padrón que corresponden a lo leído: por CURP (casi igual) o por nombre (parecido)."""
        sugerencias, vistas = [], set()
        for leida in extraer.curps(texto, exigir_digito=False):
            for fila in self._consulta('SELECT * FROM sidp_curp_cercana(%s, %s)', (leida, CURP_MAXIMO)):
                sugerencias.append(self._alumno(fila, lambda d: {'por': 'curp', 'leida': leida, 'distancia': d}))
                vistas.add(fila[0])
        limpio = normalizar(texto)
        if len(limpio) >= 5:
            for fila in self._consulta('SELECT * FROM sidp_nombre_cercano(%s, %s)', (limpio, NOMBRE_MINIMO)):
                if fila[0] not in vistas:
                    sugerencias.append(self._alumno(fila, lambda p: {'por': 'nombre', 'parecido': round(float(p), 2)}))
        return sugerencias

    def anotar(self, metodo, texto, sugerencias):
        """Una fila por página leída: cuánto se leyó y qué tan cerca quedó del padrón. Para medir y mejorar."""
        mejor = sugerencias[0] if sugerencias else {}
        self._consulta('INSERT INTO lectura (metodo, caracteres, curp_leida, curp_padron, distancia, parecido) '
                       'VALUES (%s, %s, %s, %s, %s, %s)',
                       (metodo, len((texto or '').strip()), mejor.get('leida'), mejor.get('curp'), mejor.get('distancia'),
                        mejor.get('parecido')))


def abrir(archivo=ARCHIVO):
    """(base, None) si PostgreSQL respondió y quedó lista; (None, motivo) si no."""
    url = direccion(archivo)
    if not url:
        return None, f'no hay dirección de la base (falta {archivo})'
    try:
        return BaseCerebro(url).preparar(), None
    except ErrorBase as error:
        return None, str(error)
    except Exception as error:
        return None, f'PostgreSQL respondió con un error: {error}'


def main(argumentos=None):
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    base, problema = abrir(Path(argumentos[0]) if argumentos else ARCHIVO)
    if problema:
        print(f'Sin base de datos: {problema}')
        return 1
    resumen = base.resumen()
    print(f'Base lista: {resumen["motor"]}, {resumen["alumnos"]} alumnos en el padrón, {resumen["lecturas"]} lecturas anotadas.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
