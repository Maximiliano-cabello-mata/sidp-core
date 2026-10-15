"""Bandeja del administrador: revisa los expedientes de una carpeta y guarda quién autorizó o rechazó.

La usan SIDP-Validador.exe (validacion/aplicacion.py) y la página de demostración, que corre
este mismo código en el navegador con expedientes inventados. Las decisiones van a una base
SQLite en la carpeta (`decisiones.db`): solo se agregan, nunca se cambian ni se borran, y la
última de cada expediente es la que cuenta.
"""
import datetime
import hashlib
import json
import sqlite3
from pathlib import Path

from validacion import cerebro_red, expediente, lector, modelo, prueba, renapo

ESQUEMA = """
CREATE TABLE IF NOT EXISTS decision (
  secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
  expediente TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('autorizado', 'rechazado')),
  motivo TEXT,
  quien TEXT NOT NULL CHECK (length(trim(quien)) > 0),
  fecha TEXT NOT NULL,
  estado_sistema TEXT NOT NULL,
  reglas TEXT NOT NULL CHECK (json_valid(reglas)),
  CHECK (decision = 'autorizado' OR length(trim(coalesce(motivo, ''))) > 0)
);
CREATE TRIGGER IF NOT EXISTS decision_sin_cambios BEFORE UPDATE ON decision
BEGIN SELECT RAISE(ABORT, 'Las decisiones no se modifican: registre una nueva'); END;
CREATE TRIGGER IF NOT EXISTS decision_sin_borrar BEFORE DELETE ON decision
BEGIN SELECT RAISE(ABORT, 'Las decisiones no se borran'); END;
"""
LISTO = 'listo para autorizar'
ESPACIOS = ('acta_alumno', 'certificado_medico', 'boleta', 'ine_tutor', 'acta_tutor', 'comprobante')
ACEPTADOS = lector.PDF | lector.IMAGEN
MAXIMO_ARCHIVO = 15 * 1024 * 1024


class ErrorBandeja(Exception):
    """Algo que la persona hizo mal (falta el motivo, no existe el expediente)."""


def reglas_de(resultado):
    return sorted({h['regla'] for h in resultado['hallazgos']} | {g['regla'] for g in resultado['grises']}
                  | {n['regla'] for n in resultado['no_leidos']})


def reporte_para_padre(resultado, motivo):
    """Texto que recibiría el padre cuando se rechaza: qué revisar, sin mencionar reglas internas."""
    lineas = ['Su expediente de inscripción necesita correcciones.', '', f'Motivo: {motivo}', '']
    puntos = [f'{h["documento"]}: {h["detalle"]}' for h in resultado['hallazgos']]
    puntos += [f'{n["documento"]}: no se pudo leer; suba una copia más clara' for n in resultado['no_leidos']]
    puntos += [f'{g["documento"]}: revise que el nombre o domicilio esté escrito igual que en el documento'
               for g in resultado['grises']]
    if puntos:
        lineas += ['Revise:'] + [f'- {p}' for p in puntos]
    return '\n'.join(lineas)


class Bandeja:
    def __init__(self, carpeta, hoy=None, usar_modelo=True, nombre_modelo=None, url=None, base=None, editable=False,
                 registro=None):
        self.carpeta = Path(carpeta)
        self.hoy = hoy or datetime.date.today()
        self.opciones = {'usar_modelo': usar_modelo}
        if nombre_modelo:
            self.opciones['nombre_modelo'] = nombre_modelo
        if url:
            self.opciones['url'] = url
        self.editable = editable  # Solo la demostración deja cambiar la captura y los textos.
        self.registro = registro  # validacion.registro.Registro: la base con las 39 tablas, si se usa.
        self.cerebro = None  # (url, clave) del cerebro de la PC 4; sin él, los procesos corren aquí.
        self.resultados = {}
        for identificador in self.expedientes():  # Lo ya revisado sobrevive a cerrar el programa.
            guardado = self.carpeta / 'expedientes' / identificador / 'resultado.json'
            if guardado.exists():
                self.resultados[identificador] = json.loads(guardado.read_text(encoding='utf-8'))
        self.libro = sqlite3.connect(str(base or self.carpeta / 'decisiones.db'), check_same_thread=False)
        self.libro.executescript(ESQUEMA)

    def expedientes(self):
        carpeta = self.carpeta / 'expedientes'
        return sorted(p.name for p in carpeta.iterdir() if p.is_dir()) if carpeta.is_dir() else []

    def _carpeta(self, identificador):
        if identificador not in self.expedientes():
            raise ErrorBandeja(f'No existe el expediente {identificador}')
        return self.carpeta / 'expedientes' / identificador

    def conectar_cerebro(self, url, clave):
        """None si el cerebro respondió; si no, el motivo. Sin url, se desconecta."""
        if not url:
            self.cerebro = None
            return None
        problema = modelo.salud_remota(url, clave)
        self.cerebro = None if problema else (url, clave)
        return problema

    def revisar(self, identificador):
        """El cerebro de la PC 4 procesa todo; si no responde, los procesos corren aquí y nada se detiene."""
        carpeta = self._carpeta(identificador)
        resultado = None
        if self.cerebro:
            try:
                resultado = cerebro_red.validar_en_cerebro(carpeta, self.hoy, *self.cerebro)
                resultado['id'] = identificador
            except Exception as error:
                aviso = f'el cerebro no respondió ({error}); se revisó en esta PC'
        if resultado is None:
            resultado = expediente.revisar(carpeta, self.hoy, **self.opciones)
            resultado['procesado_en'] = aviso if self.cerebro else 'esta PC'
        self.resultados[identificador] = resultado
        (carpeta / 'resultado.json').write_text(json.dumps(resultado, ensure_ascii=False), encoding='utf-8')
        return resultado

    def _ids(self, identificador):
        archivo = self._carpeta(identificador) / 'registro.json'
        return json.loads(archivo.read_text(encoding='utf-8')) if archivo.exists() else None

    def recibir(self, captura, archivos):
        """Expediente nuevo desde la página de padres. archivos: [(espacio, nombre original, contenido)].

        Cada envío es una carpeta nueva: nada se sobrescribe.
        """
        alumno, tutor = captura.get('alumno', {}), captura.get('tutor', {})
        for persona, campos in ((alumno, ('nombres', 'primer_apellido')), (tutor, ('nombres', 'primer_apellido'))):
            if not all(str(persona.get(c, '')).strip() for c in campos):
                raise ErrorBandeja('Faltan el nombre o el primer apellido')
        if not archivos:
            raise ErrorBandeja('No se subió ningún documento')
        for persona in (alumno, tutor):  # El validador compara el nombre completo.
            persona['nombre'] = ' '.join(str(persona.get(c, '')).strip() for c in ('nombres', 'primer_apellido', 'segundo_apellido')).strip()
        alumno['curp'] = str(alumno.get('curp', '')).strip().upper()
        carpeta_expedientes = self.carpeta / 'expedientes'
        carpeta_expedientes.mkdir(parents=True, exist_ok=True)
        numero = max([int(n) for n in self.expedientes() if n.isdigit()] or [0]) + 1
        identificador = f'{numero:04d}'
        destino = carpeta_expedientes / identificador
        destino.mkdir()
        guardados, cuenta = [], {}
        for espacio, nombre, contenido in archivos:
            extension = Path(nombre).suffix.lower()
            if espacio not in ESPACIOS or extension not in ACEPTADOS or not 0 < len(contenido) <= MAXIMO_ARCHIVO:
                raise ErrorBandeja(f'Archivo no aceptado: {nombre} (PDF o foto, hasta 15 MB)')
            cuenta[espacio] = cuenta.get(espacio, 0) + 1
            archivo = destino / f'{espacio}_{cuenta[espacio]}{extension}'
            archivo.write_bytes(contenido)
            guardados.append((espacio, archivo.relative_to(self.carpeta).as_posix(), contenido))
        (destino / 'captura.json').write_text(json.dumps(captura, ensure_ascii=False, indent=1), encoding='utf-8')
        resultado = self.revisar(identificador)
        if self.registro:
            ids = self.registro.registrar(captura, guardados, resultado.get('extraidos'))
            self.registro.proponer(ids, resultado)
            (destino / 'registro.json').write_text(json.dumps(ids), encoding='utf-8')
        return {'expediente': identificador, 'estado': resultado['estado']}

    def revisar_todo(self):
        for identificador in self.expedientes():
            self.revisar(identificador)
        return self.estado()

    def decisiones(self):
        filas = self.libro.execute(
            'SELECT expediente, decision, motivo, quien, fecha FROM decision WHERE secuencia IN '
            '(SELECT max(secuencia) FROM decision GROUP BY expediente)').fetchall()
        return {f[0]: {'decision': f[1], 'motivo': f[2], 'quien': f[3], 'fecha': f[4]} for f in filas}

    def decidir(self, identificador, decision, motivo='', quien='administrador'):
        resultado = self.resultados.get(identificador) or self.revisar(identificador)
        motivo = (motivo or '').strip()
        if decision not in ('autorizado', 'rechazado'):
            raise ErrorBandeja('La decisión debe ser autorizado o rechazado')
        if decision == 'rechazado' and not motivo:
            raise ErrorBandeja('Para rechazar hay que escribir el motivo')
        with self.libro:
            self.libro.execute('INSERT INTO decision(expediente, decision, motivo, quien, fecha, estado_sistema, reglas) '
                              'VALUES(?,?,?,?,?,?,?)',
                              (identificador, decision, motivo or None, quien,
                               datetime.datetime.now().isoformat(timespec='seconds'), resultado['estado'],
                               json.dumps(reglas_de(resultado))))
        ids = self._ids(identificador)
        if self.registro and ids:
            self.registro.decidir(ids, decision, motivo or None)
        respuesta = {'expediente': identificador, 'decision': decision}
        if decision == 'rechazado':
            respuesta['reporte_para_padre'] = reporte_para_padre(resultado, motivo)
        return respuesta

    def detalle(self, identificador):
        carpeta = self._carpeta(identificador)
        try:
            captura = json.loads((carpeta / 'captura.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            captura = {}
        archivos = [a.name for a in sorted(carpeta.iterdir()) if a.is_file() and a.suffix != '.json' and not a.name.startswith('.')]
        textos = {a: (carpeta / a).read_text(encoding='utf-8', errors='replace') for a in archivos if a.endswith('.txt')} if self.editable else {}
        return {'id': identificador, 'captura': captura, 'archivos': archivos, 'textos': textos,
                'resultado': self.resultados.get(identificador), 'decision': self.decisiones().get(identificador)}

    def reescribir(self, identificador, captura, textos):
        """Solo en la demostración: cambia la captura o el texto de un documento y vuelve a revisar."""
        if not self.editable:
            raise ErrorBandeja('Aquí no se pueden cambiar los documentos')
        carpeta = self._carpeta(identificador)
        (carpeta / 'captura.json').write_text(json.dumps(captura, ensure_ascii=False, indent=1), encoding='utf-8')
        for nombre, texto in textos.items():
            if Path(nombre).name != nombre or not nombre.endswith('.txt') or not (carpeta / nombre).exists():
                raise ErrorBandeja(f'Documento no válido: {nombre}')
            (carpeta / nombre).write_text(texto, encoding='utf-8')
        return self.revisar(identificador)

    def curps(self):
        """La lista de CURP por validar ante RENAPO (vacía sin la base de 39 tablas)."""
        return {'pagina_oficial': renapo.PAGINA_OFICIAL, 'alumnos': self.registro.curps() if self.registro else []}

    def constancia_renapo(self, nombre, contenido):
        """La constancia que la persona descargó de RENAPO y arrastró al panel. Se guarda sin sobrescribir."""
        if not self.registro:
            raise ErrorBandeja('Aquí no hay base de datos de alumnos')
        def guardar():
            carpeta = self.carpeta / 'renapo'
            carpeta.mkdir(exist_ok=True)
            archivo = carpeta / f'constancia_{hashlib.sha256(contenido).hexdigest()[:16]}.pdf'
            if not archivo.exists():
                archivo.write_bytes(contenido)
            return archivo.relative_to(self.carpeta).as_posix()
        try:
            return self.registro.validar_constancia(contenido, guardar)
        except renapo.ErrorConstancia as error:
            raise ErrorBandeja(str(error)) from error

    def renapo_no_encontrada(self, alumno_id):
        if not self.registro:
            raise ErrorBandeja('Aquí no hay base de datos de alumnos')
        try:
            self.registro.renapo_no_encontrada(alumno_id)
        except renapo.ErrorConstancia as error:
            raise ErrorBandeja(str(error)) from error
        return self.curps()

    def base(self):
        """Filas en la base de las 39 tablas, para ver que los datos sí llegaron."""
        return self.registro.resumen() if self.registro else None

    def estado(self):
        marcas = prueba.etiquetas(self.carpeta)
        decisiones = self.decisiones()
        revisados = [self.resultados[i] for i in self.expedientes() if i in self.resultados]
        medidas = prueba.medir(revisados, marcas)
        filas = []
        for identificador in self.expedientes():
            resultado = self.resultados.get(identificador)
            marca = marcas.get(identificador)
            filas.append({'id': identificador, 'estado': resultado and resultado['estado'],
                          'reglas': reglas_de(resultado) if resultado else [],
                          'etiqueta': marca and ('falso' if marca['falso'] else 'verdadero'),
                          'trampa': marca and marca['trampa'], 'decision': decisiones.get(identificador)})
        autorizados_falsos = sum(1 for f in filas if f['etiqueta'] == 'falso' and f['decision']
                                 and f['decision']['decision'] == 'autorizado')
        return {'carpeta': str(self.carpeta), 'hoy': self.hoy.isoformat(), 'expedientes': filas,
                'medidas': {'revisados': len(revisados), 'listos': sum(r['estado'] == LISTO for r in revisados),
                            'revision': sum(r['estado'] != LISTO for r in revisados), 'etiquetados': medidas['etiquetados'],
                            'falsos': medidas['falsos'], 'falsos_detectados': medidas['falsos_detectados'],
                            'falsos_pasaron': medidas['falsos_pasaron'], 'verdaderos': medidas['verdaderos'],
                            'falsas_alarmas': medidas['falsas_alarmas'],
                            'autorizados': sum(1 for d in decisiones.values() if d['decision'] == 'autorizado'),
                            'rechazados': sum(1 for d in decisiones.values() if d['decision'] == 'rechazado'),
                            'falsos_autorizados': autorizados_falsos}}
