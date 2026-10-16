"""SIDP se actualiza solo, sin que el servidor de la escuela dependa del repositorio: la PC 4 guarda la versión
nueva y el servidor la toma de ahí.

Camino de una versión nueva:
1. Al fusionar a main, GitHub compila SIDP.exe y lo publica como versión v1.0.N (Releases).
2. La PC 4 revisa cada hora la última versión publicada, la baja a C:\\SIDP-datos\\actualizaciones y comprueba su
   huella (sha256). También se puede poner a mano (por ejemplo, sin internet):
       python -m validacion.actualizar publicar RUTA\\SIDP.exe --version 1.0.N
3. El servidor (SIDP.exe instalado) le pregunta a la PC 4 cada hora. Si hay una versión mayor, la baja junto a
   SIDP.exe, comprueba la huella y, cuando nadie ha hecho cambios en SIDP en 10 minutos, cambia el programa y se
   reinicia solo (unos segundos). Si la versión nueva no contesta, regresa sola a la anterior y ya no reintenta
   esa versión.

No se borra nada importante: en la PC 4 se guardan todas las versiones; en el servidor la anterior queda como
SIDP.anterior.exe (para regresar a mano, ver docs/guias/PLAN_DE_EMERGENCIA.md).

    python -m validacion.actualizar estado                       # qué versión tiene guardada la PC 4
    python -m validacion.actualizar publicar SIDP.exe --version 1.0.N
    python -m validacion.actualizar github                       # revisa GitHub una vez
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPOSITORIO = 'Maximiliano-cabello-mata/sidp-core'
NOMBRE = 'SIDP.exe'
MAXIMO = 300 * 1024 * 1024
CADA = 3600       # Segundos entre revisiones (PC 4 contra GitHub y servidor contra PC 4).
QUIETO = 600      # Segundos sin cambios en SIDP antes de reiniciarlo con la versión nueva.
ESPERA_NUEVA = 90  # Segundos que se espera a que la versión nueva conteste.


class ErrorActualizacion(Exception):
    """Algo no cuadra con la versión nueva; el mensaje es para la persona."""


def numero(version):
    """'1.0.123' -> (1, 0, 123); None si no tiene esa forma."""
    if not isinstance(version, str) or not re.fullmatch(r'\d{1,6}(\.\d{1,6}){1,3}', version.strip()):
        return None
    return tuple(int(p) for p in version.strip().split('.'))


def mayor(nueva, actual):
    a, b = numero(nueva), numero(actual or '0.0.0')
    return a is not None and b is not None and a > b


def huella(contenido):
    return hashlib.sha256(contenido).hexdigest()


# --- En la PC 4 ----------------------------------------------------------------------------------------------

def carpeta_pc4():
    if os.environ.get('SIDP_ACTUALIZACIONES'):
        return Path(os.environ['SIDP_ACTUALIZACIONES'])
    return Path('C:/SIDP-datos/actualizaciones') if os.name == 'nt' else Path.home() / 'SIDP-datos' / 'actualizaciones'


def disponible(carpeta):
    """La versión que la PC 4 ofrece: {version, sha256, tamano, archivo, origen, guardada} o None."""
    indice = Path(carpeta) / 'actual.json'
    try:
        datos = json.loads(indice.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return datos if numero(datos.get('version')) and (Path(carpeta) / datos.get('archivo', '')).is_file() else None


def publicar(carpeta, contenido, version, origen='a mano', forzar=False):
    """Guarda una versión de SIDP.exe en la PC 4 y la deja como la que se ofrece. Nunca sobrescribe otra."""
    if not numero(version):
        raise ErrorActualizacion(f'La versión "{version}" no tiene la forma 1.0.123.')
    if not 1024 <= len(contenido) <= MAXIMO or contenido[:2] != b'MZ':
        raise ErrorActualizacion('Eso no es un programa de Windows (SIDP.exe).')
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    actual = disponible(carpeta)
    if actual and not forzar and not mayor(version, actual['version']):
        return actual
    archivo = carpeta / f'SIDP-{version}.exe'
    if archivo.exists() and huella(archivo.read_bytes()) != huella(contenido):
        raise ErrorActualizacion(f'Ya hay un {archivo.name} distinto; no se sobrescribe.')
    if not archivo.exists():
        temporal = archivo.with_suffix('.parcial')
        temporal.write_bytes(contenido)
        temporal.replace(archivo)
    datos = {'version': version, 'sha256': huella(contenido), 'tamano': len(contenido), 'archivo': archivo.name,
             'origen': origen, 'guardada': time.strftime('%Y-%m-%d %H:%M')}
    temporal = carpeta / 'actual.json.parcial'
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    temporal.replace(carpeta / 'actual.json')
    return datos


def _bajar(url, espera, cabeceras=None):
    solicitud = urllib.request.Request(url, headers={'User-Agent': 'SIDP-PC4', **(cabeceras or {})})
    with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
        return respuesta.read(MAXIMO + 1)


def de_github(carpeta, repositorio=REPOSITORIO, espera=600):
    """Si GitHub tiene una versión mayor que la guardada, la baja y la publica. Devuelve la versión nueva o None."""
    datos = json.loads(_bajar(f'https://api.github.com/repos/{repositorio}/releases/latest', 60,
                              {'Accept': 'application/vnd.github+json'}))
    version = str(datos.get('tag_name') or '').lstrip('vV')
    actual = disponible(carpeta)
    if not numero(version) or (actual and not mayor(version, actual['version'])):
        return None
    activo = next((a for a in datos.get('assets') or [] if a.get('name') == NOMBRE), None)
    if not activo:
        return None
    contenido = _bajar(activo['browser_download_url'], espera)
    esperada = str(activo.get('digest') or '')
    if esperada.startswith('sha256:') and esperada[7:] != huella(contenido):
        raise ErrorActualizacion(f'La huella de {NOMBRE} {version} bajado de GitHub no coincide; no se guardó.')
    publicar(carpeta, contenido, version, origen=f'GitHub {datos.get("tag_name")}')
    return version


def vigilar_github(carpeta, repositorio=REPOSITORIO, cada=CADA, primera=300):
    time.sleep(primera)
    while True:
        try:
            nueva = de_github(carpeta, repositorio)
            if nueva:
                print(f'{time.strftime("%Y-%m-%d %H:%M")} Actualización {nueva} guardada en {carpeta}', flush=True)
        except Exception as error:  # Sin internet o GitHub no contesta: se intenta en una hora.
            print(f'{time.strftime("%Y-%m-%d %H:%M")} No se pudo revisar GitHub: {type(error).__name__}', flush=True)
        time.sleep(cada)


# --- En el servidor (SIDP.exe instalado) ---------------------------------------------------------------------

def programa_instalado():
    """La ruta de SIDP.exe si esto corre como el programa instalado (no desde el código fuente)."""
    if getattr(sys, 'frozen', False) and Path(sys.executable).name.lower() == NOMBRE.lower():
        return Path(sys.executable)
    return None


class Actualizador:
    """Pregunta a la PC 4 si hay versión nueva, la baja y la pone cuando SIDP está quieto."""

    def __init__(self, app, programa, version_actual, cada=CADA, quieto=QUIETO, espera_nueva=ESPERA_NUEVA, iniciar=None, contesta=None):
        self.app, self.programa = app, Path(programa)
        self.cada, self.quieto, self.espera_nueva = cada, quieto, espera_nueva
        self.iniciar = iniciar or _iniciar
        self.contesta = contesta or _contesta
        self.registro = Path(app.carpeta) / 'actualizacion.json'
        self.ultima_revision = 0.0
        self.estado = {'version': version_actual, 'disponible': None, 'lista': None, 'revisado': None, 'problema': None,
                       'fallida': self._leer().get('fallida')}

    def _leer(self):
        try:
            return json.loads(self.registro.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _anotar(self, **cambios):
        datos = {**self._leer(), **cambios}
        self.registro.write_text(json.dumps(datos, ensure_ascii=False), encoding='utf-8')

    @property
    def nuevo(self):
        return self.programa.with_name('SIDP.nuevo.exe')

    @property
    def anterior(self):
        return self.programa.with_name('SIDP.anterior.exe')

    def revisar(self, url, clave, ahora=None):
        """Una vez por hora: ¿hay versión mayor en la PC 4? Si sí, la baja y la deja lista."""
        ahora = ahora or time.time()
        if self.estado['lista'] or not url or not clave or ahora - self.ultima_revision < self.cada:
            return self.estado
        self.ultima_revision = ahora
        from validacion import cerebro_red
        try:
            ofrece = cerebro_red.pedir_a_cerebro(url, clave, '/actualizacion', espera=30)
        except Exception as error:
            self.estado.update(problema=f'No se pudo preguntar a la PC 4: {error}', revisado=time.strftime('%H:%M'))
            return self.estado
        version = (ofrece or {}).get('version')
        self.estado.update(disponible=version, revisado=time.strftime('%H:%M'), problema=None)
        if not mayor(version, self.estado['version']) or version == self.estado['fallida']:
            return self.estado
        try:
            contenido = cerebro_red.bajar_de_cerebro(url, clave, '/actualizacion/programa', espera=600)
            if huella(contenido) != ofrece.get('sha256') or len(contenido) != ofrece.get('tamano') or contenido[:2] != b'MZ':
                raise ErrorActualizacion('el archivo llegó incompleto o distinto')
            temporal = self.nuevo.with_suffix('.parcial')
            temporal.write_bytes(contenido)
            temporal.replace(self.nuevo)
        except Exception as error:
            self.estado['problema'] = f'No se pudo bajar la versión {version}: {error}'
            return self.estado
        self.estado['lista'] = version
        print(f'{time.strftime("%Y-%m-%d %H:%M")} Versión {version} lista; se pone cuando nadie use SIDP.', flush=True)
        return self.estado

    def quieto_ahora(self, ahora=None):
        return (ahora or time.time()) - getattr(self.app, 'ultimo_cambio', 0) >= self.quieto

    def aplicar(self, apagar):
        """Cambia SIDP.exe por la versión nueva y la arranca. apagar() detiene este servidor y libera el puerto.
        Devuelve 'puesta' si la nueva contestó; 'regresada' si no contestó y se volvió a arrancar la anterior (esa
        versión ya no se reintenta); None si no había nada que poner. Con 'puesta' o 'regresada', este proceso ya
        no sirve: quien llamó debe terminarlo."""
        version = self.estado['lista']
        if not version or not self.nuevo.exists():
            return None
        try:
            if self.anterior.exists():
                self.anterior.unlink()
            self.programa.replace(self.anterior)  # Windows deja renombrar el programa que está corriendo.
        except OSError as error:
            self.estado.update(lista=None, problema=f'No se pudo cambiar SIDP.exe: {error}')
            return None
        try:
            self.nuevo.replace(self.programa)
        except OSError as error:
            self.anterior.replace(self.programa)
            self.estado.update(lista=None, problema=f'No se pudo cambiar SIDP.exe: {error}')
            return None
        apagar()
        proceso = self.iniciar(self.programa, self.argumentos())
        if self.contesta(version, self.espera_nueva, self.app.puerto):
            self._anotar(puesta=version, cuando=time.strftime('%Y-%m-%d %H:%M'))
            print(f'{time.strftime("%Y-%m-%d %H:%M")} SIDP actualizado a {version}.', flush=True)
            return 'puesta'
        _parar(proceso)
        time.sleep(2)
        self.programa.replace(self.programa.with_name('SIDP.fallido.exe'))
        self.anterior.replace(self.programa)
        self._anotar(fallida=version, cuando=time.strftime('%Y-%m-%d %H:%M'))
        self.estado.update(fallida=version, lista=None, problema=f'La versión {version} no arrancó; se regresó a la anterior.')
        print(f'{time.strftime("%Y-%m-%d %H:%M")} {self.estado["problema"]}', flush=True)
        self.iniciar(self.programa, self.argumentos())
        return 'regresada'

    def argumentos(self):
        """Los mismos datos y puerto que este proceso, sin ventana."""
        return ['--segundo-plano', '--carpeta', str(Path(self.app.carpeta).parent), '--puerto', str(self.app.puerto)]


def _iniciar(programa, argumentos):
    banderas = 0x00000008 | 0x00000200 if os.name == 'nt' else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([str(programa), *argumentos], creationflags=banderas, close_fds=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _parar(proceso):
    """El .exe de un solo archivo arranca un segundo proceso: en Windows se para el árbol completo."""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(proceso.pid), '/T', '/F'], capture_output=True, timeout=30)
        else:
            proceso.kill()
    except Exception:
        pass


def _contesta(version, espera, puerto):
    limite = time.monotonic() + espera
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{puerto}/api/hola', timeout=3) as respuesta:
                if json.load(respuesta).get('version') == version:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.actualizar')
    parser.add_argument('accion', choices=('estado', 'publicar', 'github'))
    parser.add_argument('archivo', nargs='?', type=Path)
    parser.add_argument('--version')
    parser.add_argument('--carpeta', type=Path, default=carpeta_pc4())
    parser.add_argument('--forzar', action='store_true', help='publicar aunque no sea mayor (para regresar a una anterior)')
    args = parser.parse_args(argumentos)
    try:
        if args.accion == 'publicar':
            if not args.archivo or not args.archivo.is_file() or not args.version:
                print('Uso: python -m validacion.actualizar publicar RUTA\\SIDP.exe --version 1.0.N')
                return 1
            datos = publicar(args.carpeta, args.archivo.read_bytes(), args.version, forzar=args.forzar)
            print(f'La PC 4 ofrece SIDP {datos["version"]} ({datos["tamano"] // 1024} KB, {datos["origen"]}).')
            return 0
        if args.accion == 'github':
            nueva = de_github(args.carpeta)
            print(f'Guardada la versión {nueva} de GitHub.' if nueva else 'No hay versión nueva en GitHub.')
    except (ErrorActualizacion, OSError, ValueError) as error:
        print(error)
        return 1
    datos = disponible(args.carpeta)
    print(f'La PC 4 ofrece SIDP {datos["version"]} ({datos["origen"]}, {datos["guardada"]}).' if datos
          else f'La PC 4 todavía no tiene ninguna versión en {args.carpeta}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
