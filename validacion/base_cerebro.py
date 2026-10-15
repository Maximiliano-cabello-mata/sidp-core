"""La base de datos de la PC 4, en PostgreSQL: el expediente escolar completo para procesar.

Guarda alumnos, grupos, tutores, inscripciones, documentos (su huella, no el archivo), revisiones,
lecturas del cerebro y una bitácora de todo cambio. Los procesos viven dentro de la base (esquema
`sidp`, ver base_cerebro.sql y docs/arquitectura/base_cerebro.md): CURP, edades, 911, faltantes,
alertas, posibles duplicados y la comparación de lo leído contra los alumnos reales. Lo que sale de
aquí es propuesta o aviso; una persona decide.

PostgreSQL escucha solo en 127.0.0.1 (como Ollama): nadie de la red entra a la base; todo pasa por el
cerebro, que pide su clave. La dirección con la contraseña vive fuera del repositorio, en
%USERPROFILE%\\.sidp\\base_cerebro.txt, con esta forma:
    postgresql://sidp:CONTRASEÑA@127.0.0.1:5432/sidp_cerebro

Sin PostgreSQL el cerebro funciona igual, solo que sin comparar contra los alumnos.

En la PC 4, desde la raíz del repositorio:
    python -m validacion.base_cerebro                     # crea o actualiza la base y dice cómo está
    python -m validacion.base_cerebro cargar LISTA.pdf    # carga la lista oficial de la SEP (toda la escuela)
    python -m validacion.base_cerebro informe             # números del 911, grupos y alertas (sin nombres)
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import threading
import urllib.parse
from pathlib import Path

from validacion import extraer
from validacion.expediente import mayusculas

ESQUEMA = Path(__file__).with_name('base_cerebro.sql')
ARCHIVO = Path.home() / '.sidp' / 'base_cerebro.txt'
CURP_MAXIMO = 2       # Letras distintas que se aceptan para proponer una CURP de la base.
NOMBRE_MINIMO = 0.6   # Parecido mínimo para proponer a un alumno por su nombre.


class ErrorBase(Exception):
    pass


def direccion(archivo=ARCHIVO):
    """La dirección de la base: la variable SIDP_BASE o el archivo de la PC 4. None si no hay."""
    if os.environ.get('SIDP_BASE'):
        return os.environ['SIDP_BASE'].strip()
    archivo = Path(archivo)
    return archivo.read_text(encoding='utf-8').lstrip('﻿').strip() or None if archivo.exists() else None  # Sin la marca BOM de PowerShell.


def normalizar(texto):
    """Mayúsculas, sin acentos ni letras griegas, solo letras y números separados por un espacio."""
    return ' '.join(re.sub(r'[^A-Z0-9Ñ]+', ' ', mayusculas(texto)).split())


def ciclo_de(fecha):
    return f'{fecha.year}-{fecha.year + 1}' if fecha.month >= 8 else f'{fecha.year - 1}-{fecha.year}'


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
                timeout=30)
        except Exception as error:
            raise ErrorBase(f'no se pudo conectar a PostgreSQL ({type(error).__name__})')
        self.conexion.autocommit = True
        self._candado = threading.Lock()  # Una conexión para todo el cerebro: una consulta a la vez.

    def _consulta(self, sql, parametros=()):
        with self._candado:
            cursor = self.conexion.cursor()
            cursor.execute(sql, parametros) if parametros else cursor.execute(sql)
            try:
                return [list(fila) for fila in cursor.fetchall()]
            except Exception:  # Sentencias sin filas (CREATE, INSERT).
                return []

    def _uno(self, sql, parametros=()):
        return self._consulta(sql, parametros)[0][0]

    def preparar(self):
        """Crea o actualiza el esquema `sidp`: lo que falta se agrega y ningún dato se borra."""
        self._consulta(ESQUEMA.read_text(encoding='utf-8'))
        return self

    def resumen(self):
        return self._uno('SELECT sidp.resumen()')

    def cargar(self, ciclo, alumnos, origen='validador', actor='SIDP-Validador'):
        """alumnos: [{curp, primer_apellido, segundo_apellido, nombres, grado, letra}] -> lo que pasó (cuántos nuevos...)."""
        return self._uno('SELECT sidp.cargar_alumnos(CAST(%s AS jsonb), %s, %s, %s)',
                         (json.dumps(list(alumnos), ensure_ascii=False), str(ciclo), origen, actor))

    def importar_lista(self, contenido, ciclo, actor='lista oficial'):
        """La lista oficial de la SEP (PDF con toda la escuela): la lee aquí y la carga una sola vez."""
        from validacion.servicio import texto_por_hoja
        textos = texto_por_hoja(contenido)
        if not textos:
            raise ErrorBase('el PDF no tiene texto: debe ser la lista exportada, no un escaneo')
        grupos = extraer.grupos_de_hojas([(f'hoja {n}', t) for n, t in enumerate(textos, 1)], int(ciclo[:4]))
        if not grupos or any(g['grado'] is None for g in grupos):
            raise ErrorBase('no se encontraron los grupos en el PDF')
        filas = [{**{k: f[k] for k in ('curp', 'primer_apellido', 'segundo_apellido', 'nombres')}, 'grado': g['grado'], 'letra': g['letra']}
                 for g in grupos for f in g['filas']]
        resultado = self._uno('SELECT sidp.importar(%s, %s, CAST(%s AS jsonb), %s, %s, %s)',
                              (hashlib.sha256(contenido).hexdigest(), 'lista_oficial', json.dumps(filas, ensure_ascii=False),
                               ciclo, 'lista_oficial', actor))
        return {**resultado, 'grupos_leidos': [{'grupo': f'{g["grado"]}° {g["letra"]}', 'alumnos': len(g['filas']),
                                                'dudosos': sum(f['dudoso'] for f in g['filas'])} for g in grupos]}

    def informe(self):
        """Solo números: matrícula 911 por grado, sexo y edad; grupos; alertas por tipo."""
        return {'resumen': self.resumen(),
                'matricula_911': [{'grado': g, 'sexo': s, 'edad': e, 'alumnos': n} for g, s, e, n in self._consulta(
                    'SELECT grado, sexo, edad, alumnos FROM sidp.v_matricula_911 '
                    'WHERE ciclo = (SELECT max(ciclo) FROM sidp.v_inscritos) ORDER BY grado, sexo, edad')],
                'faltantes': dict(self._consulta('SELECT tipo, count(*) FROM (SELECT unnest(faltan) AS tipo FROM sidp.v_faltantes) x '
                                                 'GROUP BY tipo ORDER BY tipo'))}

    @staticmethod
    def _alumno(fila, extra):
        alumno_id, curp, valor, primer, segundo, nombres, grado, letra = fila
        return {'alumno_id': alumno_id, 'curp': curp, **extra(valor), 'primer_apellido': primer, 'segundo_apellido': segundo,
                'nombres': nombres, 'grado': grado, 'letra': letra}

    def sugerir(self, texto):
        """Los alumnos de la base que corresponden a lo leído: por CURP (casi igual) o por nombre (parecido)."""
        sugerencias, vistas = [], set()
        for leida in extraer.curps(texto, exigir_digito=False):
            for fila in self._consulta('SELECT * FROM sidp.curp_cercana(%s, %s)', (leida, CURP_MAXIMO)):
                sugerencias.append(self._alumno(fila, lambda d: {'por': 'curp', 'leida': leida, 'distancia': d}))
                vistas.add(fila[0])
        limpio = normalizar(texto)
        if len(limpio) >= 5:
            for fila in self._consulta('SELECT * FROM sidp.nombre_cercano(%s, %s)', (limpio, NOMBRE_MINIMO)):
                if fila[0] not in vistas:
                    sugerencias.append(self._alumno(fila, lambda p: {'por': 'nombre', 'parecido': round(float(p), 2)}))
        return sugerencias

    def anotar(self, metodo, texto, sugerencias, tipo=None):
        """Una fila por página leída: cuánto se leyó y qué tan cerca quedó de un alumno. Para medir y mejorar."""
        mejor = sugerencias[0] if sugerencias else {}
        self._consulta('SELECT sidp.registrar_lectura(%s, %s, %s, %s, %s, %s, %s)',
                       (metodo, len((texto or '').strip()), tipo, mejor.get('leida'), mejor.get('alumno_id'),
                        mejor.get('distancia'), mejor.get('parecido')))


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


def _imprimir_resumen(resumen):
    print(f'Base lista: {resumen["motor"]}, esquema {resumen["esquema"]}, {resumen["alumnos"]} alumnos inscritos, '
          f'{resumen["documentos"]} documentos, {resumen["lecturas"]} lecturas anotadas.')
    for grupo in resumen['grupos']:
        print(f'  {grupo["grupo"]}: {grupo["alumnos"]} alumnos ({grupo["hombres"]} H, {grupo["mujeres"]} M), '
              f'{grupo["extraedad"]} con extraedad')
    if resumen['alertas']:
        print('Alertas para revisar: ' + ', '.join(f'{tipo} {n}' for tipo, n in sorted(resumen['alertas'].items())))


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.base_cerebro')
    parser.add_argument('accion', nargs='?', default='estado', choices=('estado', 'cargar', 'informe'))
    parser.add_argument('archivo', nargs='?', type=Path, help='con "cargar": el PDF de la lista oficial (fuera del repositorio)')
    parser.add_argument('--ciclo', default=ciclo_de(datetime.date.today()), help='por ejemplo 2026-2027')
    parser.add_argument('--base', type=Path, default=ARCHIVO, help='archivo con la dirección de PostgreSQL')
    args = parser.parse_args(argumentos)
    base, problema = abrir(args.base)
    if problema:
        print(f'Sin base de datos: {problema}')
        return 1
    if args.accion == 'cargar':
        if not args.archivo or not args.archivo.is_file():
            print('Falta el PDF: python -m validacion.base_cerebro cargar RUTA\\DE\\LA\\LISTA.pdf')
            return 1
        try:
            resultado = base.importar_lista(args.archivo.read_bytes(), args.ciclo)
        except ErrorBase as error:
            print(f'No se cargó: {error}')
            return 1
        if resultado['ya_importado']:
            print('Ese mismo archivo ya se había cargado: no se cambió nada.')
        for grupo in resultado['grupos_leidos']:
            print(f'  Leído {grupo["grupo"]}: {grupo["alumnos"]} alumnos, {grupo["dudosos"]} renglones dudosos')
        print(f'Ciclo {args.ciclo}: {resultado["nuevos"]} alumnos nuevos, {resultado["actualizados"]} actualizados, '
              f'{resultado["inscritos"]} inscritos, {resultado["cambios_de_grupo"]} cambios de grupo, '
              f'{len(resultado["rechazados"])} renglones rechazados, {resultado["no_vinieron"]} inscritos que no vienen en la lista.')
        for rechazo in resultado['rechazados']:
            print(f'  Renglón {rechazo["renglon"]}: {rechazo["motivo"]}')
    if args.accion == 'informe':
        datos = base.informe()
        _imprimir_resumen(datos['resumen'])
        print('Matrícula (estadística 911), edad al 31 de diciembre:')
        for fila in datos['matricula_911']:
            print(f'  {fila["grado"]}° {fila["sexo"]} {fila["edad"]} años: {fila["alumnos"]}')
        if datos['faltantes']:
            print('Documentos que faltan validar: ' + ', '.join(f'{tipo} {n}' for tipo, n in datos['faltantes'].items()))
        return 0
    _imprimir_resumen(base.resumen())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
