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
    python -m validacion.base_cerebro cargar LISTA.pdf    # carga la lista oficial de la SEP (o la lista revisada .csv)
    python -m validacion.base_cerebro informe             # números del 911, grupos y alertas (sin nombres)
    python -m validacion.base_cerebro borrar --si-borrar-todo   # deja la base vacía, para empezar de nuevo
    python -m validacion.base_cerebro respaldar           # copia completa con pg_dump en C:\\SIDP-datos\\respaldos
    python -m validacion.base_cerebro optimizar           # limpia, actualiza estadísticas y rehace índices (no borra datos)
    python -m validacion.base_cerebro analisis            # el análisis con pandas, solo números
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
CARPETA_RESPALDOS = Path('C:/SIDP-datos/respaldos') if os.name == 'nt' else Path.home() / 'SIDP-datos' / 'respaldos'
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
        self._cortada = (OSError, pg8000.dbapi.InterfaceError)  # La conexión se cayó, no la consulta.
        self.url = url
        self.conexion = self._conectar()
        self._candado = threading.Lock()  # Una conexión para todo el cerebro: una consulta a la vez.

    def _conectar(self):
        import pg8000.dbapi
        partes = urllib.parse.urlsplit(self.url)
        try:
            conexion = pg8000.dbapi.connect(
                user=urllib.parse.unquote(partes.username or 'sidp'), password=urllib.parse.unquote(partes.password or ''),
                host=partes.hostname or '127.0.0.1', port=partes.port or 5432, database=partes.path.lstrip('/') or 'sidp_cerebro',
                timeout=30)
        except Exception as error:
            raise ErrorBase(f'no se pudo conectar a PostgreSQL ({type(error).__name__})')
        conexion.autocommit = True
        return conexion

    def _consulta(self, sql, parametros=()):
        with self._candado:
            try:
                return self._ejecutar(sql, parametros)
            except self._cortada:
                # PostgreSQL se reinició o cortó la conexión: sin esto, el cerebro fallaba en todo hasta reiniciarlo.
                try:
                    self.conexion.close()
                except Exception:
                    pass
                self.conexion = self._conectar()
                return self._ejecutar(sql, parametros)

    def _ejecutar(self, sql, parametros):
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

    def borrar_todo(self):
        """Deja la base vacía con el esquema nuevo. Solo a mano, desde la consola de la PC 4: la base misma no deja borrar."""
        self._consulta('DROP SCHEMA IF EXISTS sidp CASCADE; DROP TABLE IF EXISTS public.padron_alumno_v1, public.lectura_v1, '
                       'public.padron_alumno, public.lectura')
        return self.preparar()

    # ---------------------------------------------------------------- Expediente del alumno (datos sacados de los documentos)

    def _alumno_id(self, curp):
        filas = self._consulta('SELECT id FROM sidp.alumno WHERE curp = %s', ((curp or '').upper(),))
        if not filas:
            raise ErrorBase('Ese alumno no está en la base de la PC 4')
        return filas[0][0]

    def expediente_alumno(self, curp):
        """Todo lo que se sabe del alumno, por categoría: lo que muestra su expediente en el panel."""
        alumno = self._alumno_id(curp)
        fila = self._consulta(
            "SELECT curp, nombres, primer_apellido, segundo_apellido, fecha_nacimiento, sexo, estado, curp_renapo, grado, letra, inscripcion "
            "FROM sidp.v_alumnos WHERE id = %s", (alumno,))[0]
        claves = ('curp', 'nombres', 'primer_apellido', 'segundo_apellido', 'fecha_nacimiento', 'sexo', 'estado', 'curp_renapo', 'grado', 'letra',
                  'inscripcion')
        ficha = dict(zip(claves, fila))
        ficha['fecha_nacimiento'] = ficha['fecha_nacimiento'].isoformat() if ficha['fecha_nacimiento'] else None
        datos = {}
        for id_dato, categoria, campo, valor, detalle, confianza, metodo, documento, estado in self._consulta(
                'SELECT id, categoria, campo, valor, detalle, confianza, metodo, documento, estado FROM sidp.v_datos '
                'WHERE alumno_id = %s ORDER BY categoria, campo, id', (alumno,)):
            datos.setdefault(categoria, []).append({'id': id_dato, 'campo': campo, 'valor': valor, 'detalle': detalle, 'confianza': confianza,
                                                    'metodo': metodo, 'documento': documento, 'estado': estado})
        tutores = [dict(zip(('nombres', 'primer_apellido', 'segundo_apellido', 'curp', 'telefono', 'correo', 'domicilio', 'parentesco'), t))
                   for t in self._consulta('SELECT t.nombres, t.primer_apellido, t.segundo_apellido, t.curp, t.telefono, t.correo, t.domicilio, '
                                           'at.parentesco FROM sidp.alumno_tutor at JOIN sidp.tutor t ON t.id = at.tutor_id '
                                           'WHERE at.alumno_id = %s AND at.vigente', (alumno,))]
        trabajos = [dict(zip(('id', 'estado', 'resumen', 'creado', 'problema'), (t[0], t[1], t[2], t[3].isoformat(timespec='minutes'), t[4])))
                    for t in self._consulta('SELECT id, estado, resumen, creado, problema FROM sidp.trabajo WHERE alumno_id = %s ORDER BY id DESC LIMIT 20', (alumno,))]
        return {'alumno': ficha, 'datos': datos, 'tutores': tutores, 'trabajos': trabajos}

    def por_confirmar(self, limite=300):
        """Los datos dudosos de todos los alumnos, para confirmarlos de corrido."""
        filas = self._consulta(
            "SELECT d.id, a.curp, a.primer_apellido || ' ' || a.segundo_apellido || ' ' || a.nombres, i.grado, i.letra, d.categoria, d.campo, "
            "d.valor, d.detalle, d.documento FROM sidp.dato d JOIN sidp.alumno a ON a.id = d.alumno_id "
            "LEFT JOIN sidp.v_alumnos i ON i.id = a.id WHERE d.estado = 'por_confirmar' "
            "ORDER BY i.grado, i.letra, a.primer_apellido, d.id LIMIT %s", (limite,))
        return [dict(zip(('id', 'curp', 'alumno', 'grado', 'letra', 'categoria', 'campo', 'valor', 'detalle', 'documento'), f)) for f in filas]

    def confirmar_dato(self, id_dato, valor, persona, descartar=False):
        return self._uno('SELECT sidp.confirmar_dato(%s, %s, %s, %s)', (int(id_dato), valor or '', persona or 'administrador', bool(descartar)))

    def agregar_dato(self, curp, categoria, campo, valor, persona, detalle=None):
        """Un dato que escribe una persona (por ejemplo, un teléfono nuevo): queda confirmado."""
        from validacion import campos as campos_mod
        from validacion import estandar
        nombre = campos_mod.clave_de(campo)
        if not estandar.permitido(categoria, nombre):
            raise ErrorBase('Ese dato no es de los que pide el gobierno ni de los que la escuela necesita: no se guarda.')
        try:
            valor = estandar.valor_de(categoria, nombre, valor)
        except ValueError as error:
            raise ErrorBase(str(error))
        return self._uno('SELECT sidp.guardar_dato(%s, %s, %s, %s, CAST(%s AS jsonb), %s, %s, %s, %s, %s, %s)',
                         (self._alumno_id(curp), categoria, nombre, valor, json.dumps(detalle or {}, ensure_ascii=False), 'confirmado',
                          'persona', None, None, persona or 'administrador', nombre in campos_mod.VARIOS))

    def agregar_varios(self, datos, persona):
        """Varios datos de una vez (lo del 911 de todo un grupo). Los vacíos no se tocan; cada uno queda confirmado."""
        guardados = 0
        for dato in list(datos)[:3000]:
            if str(dato.get('valor') or '').strip():
                self.agregar_dato(dato['curp'], dato['categoria'], dato['campo'], dato['valor'], persona)
                guardados += 1
        return {'guardados': guardados}

    def dar_baja_alumno(self, curp, motivo, persona):
        """El alumno se va de la escuela: deja de contar en listas y análisis, pero su expediente se queda."""
        alumno = self._alumno_id(curp)
        if not (motivo or '').strip():
            raise ErrorBase('La baja necesita un motivo')
        ciclo = self._uno("SELECT ciclo FROM sidp.v_inscritos WHERE id = %s", (alumno,))
        if ciclo:
            self._consulta('SELECT sidp.dar_baja(%s, %s, %s, %s)', (alumno, ciclo, motivo, persona or 'administrador'))
        self._consulta("UPDATE sidp.alumno SET estado = 'baja' WHERE id = %s", (alumno,))
        return {'baja': curp}

    def borrar_alumno(self, curp, motivo, persona):
        """Quita al alumno de la base (por ejemplo, se cargó por error). La bitácora guarda quién y por qué."""
        self._consulta('SELECT sidp.borrar_alumno(%s, %s, %s)', (self._alumno_id(curp), persona or 'administrador', motivo))
        return {'borrado': curp}

    # ---------------------------------------------------------------- Inventario

    def inventario(self):
        """Categorías y todas las piezas (las de baja también, marcadas): lo que muestra la pestaña Inventario."""
        categorias = [{'clave': c, 'nombre': n, 'prefijo': p} for c, n, p in
                      self._consulta('SELECT clave, nombre, prefijo FROM sidp.inventario_categoria ORDER BY orden')]
        piezas = [{'codigo': c, 'estado': e, 'ubicacion': u, 'numero_serie': s, 'notas': n, 'lote': l, 'categoria': cat,
                   'nombre': nom, 'caracteristicas': car, 'creado': cr.isoformat() if cr else None}
                  for c, e, u, s, n, l, cat, nom, car, cr in self._consulta(
                      'SELECT codigo, estado, ubicacion, numero_serie, notas, lote, categoria, nombre, caracteristicas, creado '
                      'FROM sidp.v_inventario ORDER BY categoria, nombre, codigo')]
        return {'categorias': categorias, 'piezas': piezas}

    def inventario_alta(self, categoria, nombre, caracteristicas, cantidad, ubicacion, series, actor):
        try:
            cantidad = int(cantidad)
        except (TypeError, ValueError):
            raise ErrorBase('la cantidad debe ser un número')
        if not 1 <= cantidad <= 500:
            raise ErrorBase('la cantidad va de 1 a 500 piezas por alta')
        if not str(nombre or '').strip():
            raise ErrorBase('falta el nombre (por ejemplo: mesa binaria)')
        if not str(actor or '').strip():
            raise ErrorBase('falta quién da de alta')
        datos = {str(k).strip(): str(v).strip() for k, v in (caracteristicas or {}).items() if str(k).strip() and str(v).strip()}
        series = [str(x or '').strip() for x in (series or [])][:cantidad]
        return self._uno('SELECT sidp.inventario_alta(%s, %s, CAST(%s AS jsonb), %s, %s, CAST(%s AS text[]), %s)',
                         (categoria, nombre, json.dumps(datos, ensure_ascii=False), cantidad, ubicacion or '', series, actor))

    def inventario_cambiar(self, codigo, estado, ubicacion, notas, actor):
        if estado and estado not in ('bueno', 'regular', 'malo', 'baja'):
            raise ErrorBase('el estado es bueno, regular, malo o baja')
        return self._uno('SELECT sidp.inventario_cambiar(%s, %s, %s, %s, %s)', (codigo, estado or '', ubicacion or '', notas or '', actor))

    # ---------------------------------------------------------------- Mantenimiento

    def tamano(self):
        return self._uno('SELECT pg_database_size(current_database())')

    def optimizar(self):
        """Limpia lo que PostgreSQL ya no usa, actualiza sus estadísticas y rehace los índices. No borra datos."""
        antes = self.tamano()
        self._consulta('VACUUM (ANALYZE)')
        self._consulta('REINDEX SCHEMA sidp')
        return {'antes_mb': round(antes / 1024 / 1024, 1), 'despues_mb': round(self.tamano() / 1024 / 1024, 1)}

    def respaldar(self, carpeta):
        """Una copia completa de la base con pg_dump (formato que restaura pg_restore). Devuelve la ruta y el tamaño."""
        import shutil
        import subprocess
        programa = shutil.which('pg_dump')
        if not programa and os.name == 'nt':
            candidatos = sorted(Path('C:/Program Files/PostgreSQL').glob('*/bin/pg_dump.exe'), key=lambda p: int(p.parts[-3]) if p.parts[-3].isdigit() else 0)
            programa = str(candidatos[-1]) if candidatos else None
        if not programa:
            raise ErrorBase('no se encontró pg_dump (viene con PostgreSQL, en su carpeta bin)')
        partes = urllib.parse.urlsplit(self.url)
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f'sidp_cerebro_{datetime.datetime.now():%Y%m%d_%H%M%S}.dump'
        entorno = {**os.environ, 'PGPASSWORD': urllib.parse.unquote(partes.password or '')}
        resultado = subprocess.run([programa, '-h', partes.hostname or '127.0.0.1', '-p', str(partes.port or 5432),
                                    '-U', urllib.parse.unquote(partes.username or 'sidp'), '-Fc', '-f', str(destino),
                                    partes.path.lstrip('/') or 'sidp_cerebro'], env=entorno, capture_output=True, text=True)
        if resultado.returncode != 0 or not destino.is_file():
            raise ErrorBase(f'pg_dump falló: {resultado.stderr.strip()[:300]}')
        return {'archivo': str(destino), 'mb': round(destino.stat().st_size / 1024 / 1024, 2)}

    def alumnos(self, ciclo=None):
        """Los alumnos inscritos por grupo (el último ciclo si no se dice): lo que el panel del .exe trae de aquí."""
        filas = self._consulta(
            "SELECT ciclo, grado, letra, curp, primer_apellido, coalesce(segundo_apellido, ''), nombres FROM sidp.v_inscritos "
            "WHERE ciclo = coalesce(%s, (SELECT max(ciclo) FROM sidp.v_inscritos)) AND grado IS NOT NULL "
            "ORDER BY grado, letra, primer_apellido, segundo_apellido, nombres", (ciclo,))
        grupos = {}
        for _, grado, letra, curp, primero, segundo, nombres in filas:
            grupos.setdefault((grado, letra), {'grado': grado, 'letra': letra, 'filas': []})['filas'].append(
                {'curp': curp or '', 'primer_apellido': primero, 'segundo_apellido': segundo, 'nombres': nombres})
        return {'ciclo': filas[0][0] if filas else ciclo, 'grupos': list(grupos.values())}

    def cargar(self, ciclo, alumnos, origen='validador', actor='SIDP-Validador'):
        """alumnos: [{curp, primer_apellido, segundo_apellido, nombres, grado, letra}] -> lo que pasó (cuántos nuevos...)."""
        return self._uno('SELECT sidp.cargar_alumnos(CAST(%s AS jsonb), %s, %s, %s)',
                         (json.dumps(list(alumnos), ensure_ascii=False), str(ciclo), origen, actor))

    def importar_lista(self, contenido, ciclo, actor='lista oficial', es_csv=False):
        """La lista oficial de la SEP (PDF con toda la escuela) o una lista revisada en CSV: se carga una sola vez."""
        if es_csv:
            grupos = extraer.grupos_de_csv(contenido.decode('utf-8-sig', errors='replace'))
        else:
            from validacion.servicio import texto_por_hoja
            textos = texto_por_hoja(contenido)
            if not textos:
                raise ErrorBase('el PDF no tiene texto: debe ser la lista exportada, no un escaneo')
            grupos = extraer.grupos_de_hojas([(f'hoja {n}', t) for n, t in enumerate(textos, 1)], int(ciclo[:4]))
        if not grupos or any(g['grado'] is None or g['letra'] is None for g in grupos):
            raise ErrorBase('no se encontraron los grupos (grado y letra) en el archivo')
        filas = [{**{k: f[k] for k in ('curp', 'primer_apellido', 'segundo_apellido', 'nombres')}, 'grado': g['grado'], 'letra': g['letra']}
                 for g in grupos for f in g['filas']]
        # La huella es de lo leído, no del archivo: con un lector mejor, el mismo PDF corrige los nombres.
        leido = json.dumps(filas, ensure_ascii=False, sort_keys=True)
        resultado = self._uno('SELECT sidp.importar(%s, %s, CAST(%s AS jsonb), %s, %s, %s)',
                              (hashlib.sha256(leido.encode()).hexdigest(), 'lista_oficial', leido, ciclo, 'lista_oficial', actor))
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
    parser.add_argument('accion', nargs='?', default='estado', choices=('estado', 'cargar', 'informe', 'borrar', 'respaldar', 'optimizar', 'analisis'))
    parser.add_argument('archivo', nargs='?', type=Path, help='con "cargar": la lista oficial en PDF o la lista revisada en CSV (fuera del repositorio)')
    parser.add_argument('--ciclo', default=ciclo_de(datetime.date.today()), help='por ejemplo 2026-2027')
    parser.add_argument('--base', type=Path, default=ARCHIVO, help='archivo con la dirección de PostgreSQL')
    parser.add_argument('--si-borrar-todo', action='store_true', help='con "borrar": confirma que se borra todo')
    parser.add_argument('--carpeta', type=Path, default=CARPETA_RESPALDOS, help='con "respaldar": dónde dejar la copia')
    args = parser.parse_args(argumentos)
    base, problema = abrir(args.base)
    if problema:
        print(f'Sin base de datos: {problema}')
        return 1
    if args.accion == 'borrar':
        if not args.si_borrar_todo:
            print('Esto borra todos los alumnos, documentos y la bitácora. Para hacerlo: '
                  'python -m validacion.base_cerebro borrar --si-borrar-todo')
            return 1
        base.borrar_todo()
        print('Base borrada: quedó vacía, con el esquema nuevo.')
    if args.accion == 'respaldar':
        try:
            copia = base.respaldar(args.carpeta)
        except ErrorBase as error:
            print(f'No se respaldó: {error}')
            return 1
        print(f'Respaldo listo: {copia["archivo"]} ({copia["mb"]} MB). Se restaura con pg_restore.')
        return 0
    if args.accion == 'optimizar':
        hecho = base.optimizar()
        print(f'Base optimizada: de {hecho["antes_mb"]} MB a {hecho["despues_mb"]} MB, estadísticas e índices al día.')
    if args.accion == 'analisis':
        from validacion import analisis_datos
        resultado = analisis_datos.analizar(base)
        print(f'Análisis con {resultado["motor"]}, ciclo {resultado["ciclo"]}:')
        for frase in resultado['hallazgos']:
            print('  - ' + frase)
        return 0
    if args.accion == 'cargar':
        if not args.archivo or not args.archivo.is_file():
            print('Falta la lista: python -m validacion.base_cerebro cargar RUTA\\DE\\LA\\LISTA.pdf (o .csv)')
            return 1
        try:
            resultado = base.importar_lista(args.archivo.read_bytes(), args.ciclo, es_csv=args.archivo.suffix.lower() == '.csv')
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
