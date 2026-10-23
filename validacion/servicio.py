"""Bandeja del administrador: revisa los expedientes de una carpeta y guarda quién autorizó o rechazó.

La usan SIDP-Validador.exe (validacion/aplicacion.py) y la página de demostración, que corre
este mismo código en el navegador con expedientes inventados. Las decisiones van a una base
SQLite en la carpeta (`decisiones.db`): solo se agregan, nunca se cambian ni se borran, y la
última de cada expediente es la que cuenta.
"""
import base64
import datetime
import hashlib
import io
import json
import secrets
import shutil
import sqlite3
from pathlib import Path

from validacion import archivero, campos as campos_mod, cerebro_red, codigo_barras, comparador, documentos, expediente, extraer, hoja, lector
from validacion import libro_grados, modelo, prueba, renapo, respaldo
from validacion.grupos import ErrorGrupo, Grupos, ciclo_de
from validacion import plantillas as plantillas_mod

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
EN_PAPEL = 'validado en papel'  # Expedientes que la escuela ya revisó y solo se escanean.
MAXIMO_ESCANEO = 60 * 1024 * 1024
MAXIMO_CLASIFICAR = 3  # Hojas no reconocidas por lote que la IA de la PC 4 mira para decir qué documento parecen.
MAXIMO_TANDA = 40 * 1024 * 1024  # Lo que se manda al cerebro de una vez (en base64 crece un tercio).
ESPACIOS = ('acta_alumno', 'certificado_medico', 'boleta', 'ine_tutor', 'acta_tutor', 'comprobante')
ACEPTADOS = lector.PDF | lector.IMAGEN
MAXIMO_ARCHIVO = 15 * 1024 * 1024


def partir_pdf(contenido):
    """Cada hoja de un PDF como un PDF aparte (los escáneres juntan todo el expediente en uno)."""
    try:
        import pypdf
        lector_pdf = pypdf.PdfReader(io.BytesIO(contenido))
        if len(lector_pdf.pages) <= 1:
            return [contenido]
        hojas = []
        for pagina in lector_pdf.pages:
            escritor = pypdf.PdfWriter()
            escritor.add_page(pagina)
            salida = io.BytesIO()
            escritor.write(salida)
            hojas.append(salida.getvalue())
        return hojas
    except Exception:  # Sin pypdf o PDF raro: se queda entero.
        return [contenido]


def texto_por_hoja(contenido):
    """El texto de cada hoja de un PDF, respetando columnas (así un renglón de una tabla queda en un renglón), o None."""
    try:
        import logging
        import pypdf
        logging.getLogger('pypdf').setLevel(logging.ERROR)  # Avisos de texto girado en los formatos de la SEP.
        lector_pdf = pypdf.PdfReader(io.BytesIO(contenido))
        return [pagina.extract_text(extraction_mode='layout') or '' for pagina in lector_pdf.pages]
    except Exception:  # Sin pypdf, PDF dañado o versión vieja de pypdf: se lee con el lector normal.
        return None


def unir_pdf(partes):
    if len(partes) == 1:
        return partes[0]
    import pypdf
    escritor = pypdf.PdfWriter()
    for parte in partes:
        for pagina in pypdf.PdfReader(io.BytesIO(parte)).pages:
            escritor.add_page(pagina)
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def sp_error():
    from database.procedimientos import ProcedimientoError
    return ProcedimientoError


class ErrorBandeja(Exception):
    """Algo que la persona hizo mal (falta el motivo, no existe el expediente)."""


def con_padron(propuesta, paginas):
    """Usa las sugerencias de la base del cerebro: si la CURP leída no es de nadie pero se parece a la de un
    alumno de las listas, o no se leyó la CURP pero el nombre sí, se propone ese alumno con un aviso."""
    sugerencias = [s for p in paginas if p.get('tipo') in ('acta_alumno', 'constancia_curp') for s in p.get('sugerencias') or []]
    if not sugerencias:
        return
    alumno, avisos = propuesta['alumno'], propuesta['avisos']
    nombre = lambda s: ' '.join(filter(None, (s['nombres'], s['primer_apellido'], s['segundo_apellido'])))
    por_curp = sorted((s for s in sugerencias if s['por'] == 'curp'), key=lambda s: s['distancia'])
    if any(s['distancia'] == 0 and s['curp'] == alumno.get('curp') for s in por_curp):
        return  # La CURP leída es de un alumno de las listas: nada que corregir.
    elegido = next((s for s in por_curp if s['leida'] == alumno.get('curp')), None) or (por_curp[0] if not alumno.get('curp') and por_curp else None)
    if elegido:
        avisos.insert(0, f'La CURP leída {elegido["leida"]} no es de nadie en las listas; la más parecida ({elegido["distancia"]} '
                         f'letra(s) distinta(s)) es {elegido["curp"]}, de {nombre(elegido)} ({elegido["grado"]}° {elegido["letra"]}). '
                         'Se propuso esa: compárala con el acta.')
    elif not alumno.get('curp'):
        por_nombre = sorted((s for s in sugerencias if s['por'] == 'nombre'), key=lambda s: -s['parecido'])
        if not por_nombre or (len(por_nombre) > 1 and por_nombre[1]['parecido'] >= por_nombre[0]['parecido'] - 0.05):
            return  # Dos alumnos igual de parecidos (hermanos, por ejemplo): que elija la persona.
        elegido = por_nombre[0]
        avisos.insert(0, f'No se leyó la CURP, pero el nombre se parece a {nombre(elegido)} ({elegido["grado"]}° {elegido["letra"]}) '
                         'de las listas. Se propusieron sus datos: compáralos con el acta.')
    else:
        return
    alumno.update({k: elegido[k] for k in ('curp', 'nombres', 'primer_apellido', 'segundo_apellido')})
    desglose = comparador.desglose_curp(elegido['curp'])
    if desglose:
        alumno.update(fecha_nacimiento=desglose['fecha'], sexo=desglose['sexo'])
    if elegido.get('leida'):  # Los avisos sobre la CURP mal leída ya no aplican.
        propuesta['avisos'] = avisos[:1] + [a for a in avisos[1:] if elegido['leida'] not in a]
    propuesta['padron'] = elegido


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
                 registro=None, expedientes=None):
        self.carpeta = Path(carpeta)
        # En el servidor instalado: los PDF de cada alumno en carpetas por grupo (validacion/archivero.py).
        self.expedientes_alumno = Path(expedientes) if expedientes else None
        self.archivero = archivero.Archivero(expedientes) if expedientes else None
        self.archivo_aviso = None
        self.datos_aviso = None  # Si la PC 4 no ha recibido algún expediente para sacarle los datos.
        self.hoy = hoy or datetime.date.today()
        self.opciones = {'usar_modelo': usar_modelo}
        if nombre_modelo:
            self.opciones['nombre_modelo'] = nombre_modelo
        if url:
            self.opciones['url'] = url
        self.editable = editable  # Solo la demostración deja cambiar la captura y los textos.
        self.registro = registro  # validacion.registro.Registro: la base con las 39 tablas, si se usa.
        self.cerebro = None  # (url, clave) del cerebro de la PC 4; sin él, los procesos corren aquí.
        self.padron_aviso = None  # Cómo quedó el padrón en la base del cerebro (PostgreSQL de la PC 4).
        self.traidos_aviso = None  # Cuántos alumnos se trajeron de la PC 4.
        self.respaldo_aviso = None  # Cuándo se copió por última vez a la PC 4.
        self.resultados = {}
        for identificador in self.expedientes():  # Lo ya revisado sobrevive a cerrar el programa.
            guardado = self.carpeta / 'expedientes' / identificador / 'resultado.json'
            if guardado.exists():
                self.resultados[identificador] = json.loads(guardado.read_text(encoding='utf-8'))
        self.libro = sqlite3.connect(str(base or self.carpeta / 'decisiones.db'), check_same_thread=False)
        self.libro.executescript(ESQUEMA)
        self.plantillas = plantillas_mod.Plantillas(self.carpeta / 'plantillas')
        self.grupos = Grupos(registro, self.hoy) if registro else None
        if self.registro:
            self.registro.usar_plantillas(self.plantillas.activas())

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
        if self.cerebro:
            self.traer_alumnos()  # Primero se trae la lista de la PC 4; luego se le manda lo que haya aquí.
            self.enviar_padron()
        return problema

    def traer_alumnos(self):
        """Los alumnos de la base de la PC 4 entran a las listas de grupo de aquí.

        Si un alumno ya estaba (misma CURP), toma el nombre de la PC 4, con su bitácora; si no, se agrega a su grupo.
        Un alumno validado con su constancia de RENAPO se queda con el nombre de RENAPO: ese nombre es el que va a la PC 4.
        """
        if not (self.cerebro and self.grupos):
            return None
        try:
            datos = cerebro_red.alumnos_de_cerebro(*self.cerebro)
        except Exception as error:
            detalle = getattr(error, 'code', None) == 503 and 'el cerebro no tiene PostgreSQL todavía' or str(error)
            self.traidos_aviso = f'No se trajeron los alumnos de la PC 4 ({detalle}).'
            return self.traidos_aviso
        agregados = corregidos = 0
        for grupo in datos.get('grupos', []):
            try:
                grupo_id = self.grupos.crear(grupo['grado'], grupo['letra'])
                filas = self.grupos.revisar_filas(grupo['filas'])
            except ErrorGrupo:
                continue
            for fila in filas:
                alumno = self.registro.alumno_por(fila['curp'], None) if fila['curp'] else None
                if alumno and not self.registro.db.execute('SELECT curp_confirmada FROM alumno WHERE id = ?', (alumno,)).fetchone()[0]:
                    antes = self.registro.db.execute('SELECT version FROM alumno WHERE id = ?', (alumno,)).fetchone()[0]
                    self.registro.completar_alumno(alumno, fila, 'PC 4')
                    corregidos += self.registro.db.execute('SELECT version FROM alumno WHERE id = ?', (alumno,)).fetchone()[0] != antes
            agregados += self.grupos.guardar_lista(grupo_id, filas)['agregados']
        self.traidos_aviso = (f'De la PC 4: {sum(len(g.get("filas", [])) for g in datos.get("grupos", []))} alumnos '
                              f'({agregados} nuevos aquí, {corregidos} con el nombre corregido).')
        return self.traidos_aviso

    def enviar_padron(self):
        """Manda los alumnos de las listas a la base del cerebro, para que compare lo que lee contra ellos."""
        if not (self.cerebro and self.grupos):
            return None
        ciclo, alumnos = self.grupos.padron()
        try:
            respuesta = cerebro_red.padron_a_cerebro(ciclo, alumnos, *self.cerebro)
            self.padron_aviso = f'Padrón en la base del cerebro ({respuesta.get("motor", "PostgreSQL")}): {respuesta.get("alumnos", 0)} alumnos.'
        except Exception as error:
            detalle = getattr(error, 'code', None) == 503 and 'el cerebro no tiene PostgreSQL todavía' or str(error)
            self.padron_aviso = f'El padrón no llegó a la base del cerebro ({detalle}); el cerebro lee igual, sin compararlo.'
        return self.padron_aviso

    def revisar(self, identificador):
        """El cerebro de la PC 4 procesa todo; si no responde, los procesos corren aquí y nada se detiene."""
        carpeta = self._carpeta(identificador)
        if self.resultados.get(identificador, {}).get('estado') == EN_PAPEL:
            return self.resultados[identificador]  # Ya lo revisó una persona en papel: no se vuelve a revisar.
        resultado = None
        if self.cerebro:
            try:
                resultado = cerebro_red.validar_en_cerebro(carpeta, self.hoy, *self.cerebro, plantillas=self.plantillas.activas())
                resultado['id'] = identificador
            except Exception as error:
                aviso = f'el cerebro no respondió ({error}); se revisó en esta PC'
        if resultado is None:
            resultado = expediente.revisar(carpeta, self.hoy, plantillas=self.plantillas.activas(), **self.opciones)
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
        espacios = set(ESPACIOS) | {d['clave'] for d in self.documentos_padres()}
        for espacio, nombre, contenido in archivos:  # Todo se revisa antes de crear la carpeta.
            if espacio not in espacios or Path(nombre).suffix.lower() not in ACEPTADOS or not 0 < len(contenido) <= MAXIMO_ARCHIVO:
                raise ErrorBandeja(f'Archivo no aceptado: {nombre} (PDF o foto, hasta 15 MB)')
        carpeta_expedientes = self.carpeta / 'expedientes'
        carpeta_expedientes.mkdir(parents=True, exist_ok=True)
        numero = max([int(n) for n in self.expedientes() if n.isdigit()] or [0]) + 1
        identificador = f'{numero:04d}'
        destino = carpeta_expedientes / identificador
        destino.mkdir()
        guardados, cuenta = [], {}
        for espacio, nombre, contenido in archivos:
            extension = Path(nombre).suffix.lower()
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

    def _leer(self, archivos):
        """Texto de cada archivo [(nombre, contenido)]: en el cerebro si está conectado; si no, en esta PC."""
        if self.cerebro:
            try:
                paginas, tanda, procesado_en = [], [], 'cerebro'
                for numero, archivo in enumerate(archivos):  # En tandas, para no pasar el límite del cerebro.
                    tanda.append(archivo)
                    if numero == len(archivos) - 1 or sum(len(c) for _, c in tanda) + len(archivos[numero + 1][1]) > MAXIMO_TANDA:
                        respuesta = cerebro_red.leer_en_cerebro(tanda, *self.cerebro)
                        paginas += respuesta['paginas']
                        procesado_en, tanda = respuesta['procesado_en'], []
                return paginas, procesado_en
            except Exception as error:
                aviso = f'el cerebro no respondió ({error}); se leyó en esta PC'
        lecturas = []
        temporal = self.carpeta / 'escaneos' / f'.leyendo_{secrets.token_hex(4)}'
        temporal.mkdir(parents=True)
        try:
            for numero, (nombre, contenido) in enumerate(archivos):
                ruta = temporal / f'{numero:03d}{Path(nombre).suffix.lower()}'
                ruta.write_bytes(contenido)
                lectura = lector.leer(ruta)
                lecturas.append({'nombre': nombre, 'texto': lectura['texto'], 'qr': lectura['qr'], 'problemas': lectura['problemas']})
        finally:
            shutil.rmtree(temporal, ignore_errors=True)
        return lecturas, aviso if self.cerebro else 'esta PC'

    def escaneo_leer(self, archivos):
        """Escaneos de un alumno [(nombre, contenido)]: cada página se lee, se reconoce y se proponen los datos.

        Las páginas esperan en escaneos/<lote>/ hasta que la persona guarda (o descarta).
        """
        if not archivos:
            raise ErrorBandeja('No se subió ningún archivo')
        lote = secrets.token_hex(6)
        carpeta = self.carpeta / 'escaneos' / lote
        carpeta.mkdir(parents=True)
        paginas = []
        for nombre, contenido in archivos:
            extension = Path(nombre).suffix.lower()
            if extension not in ACEPTADOS or not 0 < len(contenido) <= MAXIMO_ESCANEO:
                shutil.rmtree(carpeta, ignore_errors=True)
                raise ErrorBandeja(f'Archivo no aceptado: {nombre} (PDF o foto, hasta 60 MB)')
            partes = partir_pdf(contenido) if extension in lector.PDF else [contenido]
            for numero, parte in enumerate(partes, 1):
                archivo = f'p{len(paginas) + 1:03d}{extension}'
                (carpeta / archivo).write_bytes(parte)
                paginas.append({'archivo': archivo, 'origen': f'{Path(nombre).name} · hoja {numero}' if len(partes) > 1 else Path(nombre).name})
        lecturas, procesado_en = self._leer([(p['archivo'], (carpeta / p['archivo']).read_bytes()) for p in paginas])
        for pagina, lectura in zip(paginas, lecturas):
            pagina.update(texto=lectura['texto'], qr=lectura['qr'], problemas=lectura['problemas'],
                          sugerencias=lectura.get('sugerencias') or [])
        extraer.agrupar(paginas, self.plantillas.activas())
        self._clasificar(carpeta, paginas)
        propuesta = extraer.proponer(paginas, self.hoy)
        con_padron(propuesta, paginas)
        sin_texto = [p['origen'] for p in paginas if len(p['texto'].strip()) < lector.MINIMO_TEXTO]
        if sin_texto:
            propuesta['avisos'].insert(0, 'No se pudo leer: ' + ', '.join(sin_texto)
                                       + ('' if self.cerebro else '. Conecta el cerebro de la PC 4 para leer escaneos.'))
        (carpeta / 'lote.json').write_text(json.dumps({'paginas': [{k: p[k] for k in ('archivo', 'origen', 'tipo')} for p in paginas],
                                                       'extraidos': propuesta['extraidos']}, ensure_ascii=False), encoding='utf-8')
        alumno = propuesta['alumno']
        parecidos = self.grupos.parecidos(' '.join(filter(None, (alumno.get('nombres'), alumno.get('primer_apellido'),
                                                                   alumno.get('segundo_apellido')))), alumno.get('curp')) if self.grupos else []
        return {'lote': lote, 'procesado_en': procesado_en, 'tipos': self._tipos_escaneo(), 'propuesta': propuesta, 'parecidos': parecidos,
                'paginas': [{k: p[k] for k in ('archivo', 'origen', 'tipo', 'reconocido', 'ia') if k in p} for p in paginas]}

    def _clasificar(self, carpeta, paginas):
        """Las hojas que no se reconocieron por sus textos fijos: la IA de la PC 4 las mira y dice qué documento parecen.

        Solo propone: la persona que escanea ve "La IA cree que es..." y confirma o cambia el tipo. Sin PC 4, nada cambia.
        """
        dudosas = [p for p in paginas if not p['reconocido'] and len(p['texto'].strip()) >= lector.MINIMO_TEXTO][:MAXIMO_CLASIFICAR]
        if not (self.cerebro and dudosas):
            return
        activas = {p['clave']: p for p in self.plantillas.activas()}
        tipos = [{'clave': clave, 'nombre': nombre, 'senas': (activas.get(clave) or {}).get('textos', [])[:5]}
                 for clave, nombre in self._tipos_escaneo().items()]
        for pagina in dudosas:
            try:
                visto = cerebro_red.pedir_a_cerebro(*self.cerebro, '/clasificar', {
                    'nombre': pagina['archivo'], 'tipos': tipos,
                    'contenido': base64.b64encode((carpeta / pagina['archivo']).read_bytes()).decode()}, 330)
            except (cerebro_red.ErrorCerebro, OSError, ValueError):
                return  # La IA no está o tardó demasiado: la persona elige el tipo, como siempre.
            pagina['ia'] = {k: visto.get(k) for k in ('tipo', 'titulo', 'motivo')}
            pagina['tipo'] = visto.get('tipo') if visto.get('tipo') in {t['clave'] for t in tipos} else 'otro'
        anterior = None  # Las hojas que siguen a una que la IA reconoció (su reverso) van con ella.
        for pagina in paginas:
            if not pagina['reconocido'] and 'ia' not in pagina and anterior:
                pagina['tipo'] = anterior
            anterior = pagina['tipo']

    # --- Grupos y listas (lo primero que se escanea) ---

    def _con_grupos(self, accion):
        if not self.grupos:
            raise ErrorBandeja('No hay base de datos para los grupos')
        try:
            return accion()
        except (ErrorGrupo, sp_error()) as error:
            raise ErrorBandeja(str(error))

    def _quien(self, identificador):
        """Nombre del alumno de un expediente y su grupo, para ordenar los expedientes por grado."""
        archivo = self.carpeta / 'expedientes' / identificador / 'registro.json'
        alumno = json.loads(archivo.read_text(encoding='utf-8')).get('alumno') if archivo.exists() else None
        if not alumno or not self.registro:
            captura = self.carpeta / 'expedientes' / identificador / 'captura.json'
            datos = json.loads(captura.read_text(encoding='utf-8')).get('alumno', {}) if captura.exists() else {}
            nombre = datos.get('nombre') or ' '.join(filter(None, (datos.get('nombres'), datos.get('primer_apellido')))) or None
            # Un expediente sin registro en la base (los del ejemplo) muestra su grupo si el nombre está igual en una lista.
            en_lista = self.registro.alumno_por(None, nombre) if self.registro and nombre else None
            return {'alumno': nombre, 'grupo': en_lista and self.grupos.ubicacion(en_lista), 'alumno_id': None}
        fila = self.registro.db.execute('SELECT nombres, primer_apellido, segundo_apellido FROM alumno WHERE id = ?', (alumno,)).fetchone()
        return {'alumno': ' '.join(x for x in (fila or ()) if x) or None, 'grupo': self.grupos.ubicacion(alumno), 'alumno_id': alumno}

    def grupos_lista(self):
        return self._con_grupos(self.grupos.lista)

    def _expedientes_por_alumno(self):
        salida = {}
        decisiones = self.decisiones()
        for identificador in self.expedientes():
            archivo = self.carpeta / 'expedientes' / identificador / 'registro.json'
            if archivo.exists():
                alumno = json.loads(archivo.read_text(encoding='utf-8')).get('alumno')
                resultado = self.resultados.get(identificador) or {}
                decision = decisiones.get(identificador)
                salida.setdefault(alumno, []).append({'id': identificador, 'estado': resultado.get('estado'),
                                                      'decision': decision and decision['decision']})
        return salida

    def grupo_alumnos(self, grupo_id):
        datos = self._con_grupos(lambda: self.grupos.alumnos(grupo_id))
        por_alumno = self._expedientes_por_alumno()
        for alumno in datos['alumnos']:
            alumno['expedientes'] = por_alumno.get(alumno['id'], [])
        return datos

    def lista_leer(self, archivos=(), texto='', apellidos_primero=True):
        """Listas de grupo, escaneadas o escritas: propone los grupos con sus renglones. No guarda nada.

        Un PDF puede traer varios grupos (el formato EIA de la SEP trae toda la escuela, una hoja por grupo):
        cada hoja se lee aparte. El grado sale de lo escrito en la hoja o, si hay CURP, de la edad de la mayoría.
        """
        sin_texto, procesado_en, hojas, por_leer, de_csv = [], None, [], [], []
        for nombre, contenido in archivos:
            if nombre.lower().endswith('.csv'):  # Una lista ya revisada (por ejemplo, la que descarga el panel).
                leidos = extraer.grupos_de_csv(contenido.decode('utf-8-sig', errors='replace'))
                if not leidos:
                    raise ErrorBandeja(f'{nombre}: el CSV necesita las columnas Grado, Grupo, Primer apellido, Segundo apellido, Nombre(s) y CURP')
                de_csv += leidos
                procesado_en = procesado_en or 'esta PC'
                continue
            textos = texto_por_hoja(contenido) if nombre.lower().endswith('.pdf') else None
            if textos and sum(len(t.strip()) for t in textos) >= lector.MINIMO_TEXTO:
                hojas += [(f'{nombre} · hoja {numero}', t) for numero, t in enumerate(textos, 1)]
                procesado_en = procesado_en or 'esta PC'
            else:
                por_leer.append((nombre, contenido))
        if por_leer:  # Escaneos y fotos: el lector de siempre (el cerebro, si está conectado).
            lecturas, procesado_en = self._leer(self._muestras(por_leer))
            sin_texto = [n for (n, _), l in zip(por_leer, lecturas) if len(l['texto'].strip()) < lector.MINIMO_TEXTO]
            hojas += [(l.get('nombre') or 'escaneo', l['texto']) for l in lecturas]
        if str(texto or '').strip():
            hojas.append(('escrita', texto))
        if not hojas and not de_csv:
            raise ErrorBandeja('Sube la lista escaneada o escribe los nombres, uno por renglón')
        grupos = de_csv + (extraer.grupos_de_hojas(hojas, int(ciclo_de(self.hoy)[0][:4]), apellidos_primero) if hojas else [])
        if not grupos:
            raise ErrorBandeja('No se encontraron nombres de alumnos. Revisa que sea la lista del grupo o escribe los nombres.')
        primero = grupos[0]
        return {'grupos': grupos, 'filas': primero['filas'], 'grado': primero['grado'],
                'letra': None if primero['letra_supuesta'] else primero['letra'],
                'procesado_en': procesado_en, 'sin_texto': sin_texto}

    # ---------------------------------------------------------------- PC 4: inventario, análisis y respaldo

    def _pc4(self, ruta, datos=None, espera=120):
        if not self.cerebro:
            raise ErrorBandeja('Primero conecta el cerebro de la PC 4 en Ajustes: esto vive en la PC 4.')
        try:
            return cerebro_red.pedir_a_cerebro(*self.cerebro, ruta, datos, espera)
        except cerebro_red.ErrorCerebro as error:
            raise ErrorBandeja(f'La PC 4 dice: {error}')
        except OSError as error:
            raise ErrorBandeja(f'La PC 4 no respondió ({error}). Revisa que el cerebro esté abierto.')

    def inventario(self):
        return self._pc4('/inventario')

    def inventario_alta(self, datos):
        return self._pc4('/inventario/alta', datos)

    def inventario_cambiar(self, datos):
        return self._pc4('/inventario/cambiar', datos)

    def analisis_pc4(self, con_ia=False):
        return self._pc4('/analisis?ia=1' if con_ia else '/analisis', espera=660 if con_ia else 120)

    def respaldar(self):
        """Copia a la PC 4 lo nuevo o cambiado de la carpeta de datos de este .exe (bases y expedientes)."""
        if not self.cerebro:
            raise ErrorBandeja('Primero conecta el cerebro de la PC 4 en Ajustes.')
        try:
            hecho = respaldo.respaldar_en_cerebro(self.carpeta, *self.cerebro)
        except Exception as error:
            self.respaldo_aviso = f'El respaldo en la PC 4 falló ({error}).'
            raise ErrorBandeja(self.respaldo_aviso)
        self.respaldo_aviso = (f'Respaldo en la PC 4 al día ({datetime.datetime.now():%d/%m %H:%M}): {hecho["archivos"]} archivos, '
                               f'{hecho["enviados"]} nuevos o cambiados.')
        return {'aviso': self.respaldo_aviso, **hecho}

    def lista_traer(self):
        """El botón "Traer la lista de la PC 4": los alumnos de la base del cerebro entran aquí."""
        if not self.grupos:
            raise ErrorBandeja('Las listas de grupo necesitan la base de datos de SIDP.')
        if not self.cerebro:
            raise ErrorBandeja('Primero conecta el cerebro de la PC 4 en Ajustes.')
        aviso = self.traer_alumnos()
        if aviso.startswith('No se trajeron'):
            raise ErrorBandeja(aviso)
        return {'aviso': aviso, 'padron': self.enviar_padron(), **self.grupos.lista()}

    def lista_guardar(self, datos):
        """Guarda una lista (grado, letra, filas) o varias a la vez (grupos: [{grado, letra, filas}])."""
        varios = datos.get('grupos')
        if varios is not None:
            if not varios:
                raise ErrorBandeja('No hay grupos para guardar')
            for numero, grupo in enumerate(varios, 1):  # Primero se revisa todo; así no queda guardada solo una parte.
                try:
                    self.grupos.revisar_filas(grupo.get('filas') or [])
                    self.grupos.validar_grupo(grupo.get('grado'), grupo.get('letra'))
                except ErrorGrupo as error:
                    raise ErrorBandeja(f'Grupo {numero}: {error}')
            claves = [(int(g['grado']), str(g['letra']).upper()) for g in varios]
            if len(set(claves)) < len(claves):
                raise ErrorBandeja('Hay dos grupos con el mismo grado y letra: cambia la letra de uno')
            resumen = [self._guardar_un_grupo(g) for g in varios]
            return {'guardados': [{'grupo': r['grupo']['nombre'], 'agregados': r['agregados'], 'ya_estaban': r['ya_estaban']} for r in resumen],
                    'agregados': sum(r['agregados'] for r in resumen), 'ya_estaban': sum(r['ya_estaban'] for r in resumen),
                    'padron': self.enviar_padron(), **self.grupos.lista()}
        return {**self._guardar_un_grupo(datos), 'padron': self.enviar_padron(), **self.grupos.lista()}

    def _guardar_un_grupo(self, datos):
        def guardar():
            grupo = self.grupos.crear(datos.get('grado'), datos.get('letra'))
            return self.grupos.guardar_lista(grupo, datos.get('filas') or [])
        return self._con_grupos(guardar)

    def grupo_crear(self, grado, letra):
        self._con_grupos(lambda: self.grupos.crear(grado, letra))
        return self.grupos.lista()

    def buscar_alumno(self, nombre, curp=None):
        nombre, curp = str(nombre or '').strip(), str(curp or '').strip().upper()
        if not curp and len(nombre) == 18 and comparador.desglose_curp(nombre.upper()):
            nombre, curp = '', nombre.upper()  # En el buscador se puede escribir la CURP.
        return {'parecidos': self._con_grupos(lambda: self.grupos.parecidos(nombre, curp or None, buscar=True))}

    def ubicar_alumno(self, alumno_id, grupo_id=None, mismo_que=None):
        return {'grupo': self._con_grupos(lambda: self.grupos.ubicar(str(alumno_id or ''), grupo_id or None, mismo_que or None))}

    # --- Análisis: lo que se exporta para el 911, el SAID y la escuela ---

    def analisis(self):
        datos = self._con_grupos(self.grupos.conteo)
        filas = self.grupos.exportar_alumnos()[1:]
        datos['faltan'] = {'sin_curp': sum(1 for f in filas if not f[5]), 'curp_sin_validar': sum(1 for f in filas if f[5] and f[6] != 'Sí'),
                           'sin_sexo': sum(1 for f in filas if not f[7]), 'sin_fecha': sum(1 for f in filas if not f[8]),
                           'sin_documentos': sum(1 for f in filas if not f[12]), 'total': len(filas)}
        return datos

    def exportar(self, que, formato='xlsx'):
        """(nombre de archivo, contenido, tipo) para descargar desde el panel."""
        if formato not in ('xlsx', 'csv'):
            raise ErrorBandeja('Formato no válido')
        if que == 'por_grado':
            return self.libro_por_grado()
        if que == 'alumnos':
            filas = self._con_grupos(self.grupos.exportar_alumnos)
            hojas = [('Todos', filas)]
            for grupo in sorted({(f[0], f[1]) for f in filas[1:]}):
                hojas.append((f'{grupo[0]}° {grupo[1]}', [filas[0]] + [f for f in filas[1:] if (f[0], f[1]) == grupo]))
        elif que == 'conteo':
            conteo = self._con_grupos(self.grupos.conteo)
            filas = [['Grado', 'Grupos', 'Hombres', 'Mujeres', 'Sin dato de sexo', 'Total']]
            filas += [[f'{g["grado"]}°', g['grupos'], g['hombres'], g['mujeres'], g['sin_dato'], g['total']] for g in conteo['grados']]
            filas.append(['Total', *[sum(g[k] for g in conteo['grados']) for k in ('grupos', 'hombres', 'mujeres', 'sin_dato', 'total')]])
            hojas = [(f'Matrícula {conteo["ciclo"]}', filas)]
        else:
            raise ErrorBandeja('No existe esa exportación')
        nombre = f'sidp_{que}_{self.hoy.isoformat()}.{formato}'
        if formato == 'csv':
            return nombre, hoja.csv_excel(hojas[0][1]), 'text/csv; charset=utf-8'
        return nombre, hoja.xlsx(hojas), hoja.MIME_XLSX

    def libro_por_grado(self):
        """El Excel por grado con gráficas: las listas de aquí y, si la PC 4 contesta, lo que el escaneo sacó de cada alumno."""
        from urllib.parse import quote
        filas = self._con_grupos(self.grupos.exportar_alumnos)[1:]
        _, ciclo = self._con_grupos(self.grupos.ciclo)
        expedientes = {}
        for fila in filas if self.cerebro else ():
            if not fila[5]:
                continue
            try:
                expedientes[fila[5]] = cerebro_red.pedir_a_cerebro(*self.cerebro, '/alumno?curp=' + quote(fila[5]), None, 20)
            except cerebro_red.ErrorCerebro:
                continue  # Ese alumno todavía no está en la base de la PC 4.
            except OSError:
                break  # La PC 4 dejó de contestar: el Excel sale con lo de aquí.
        alumnos = [libro_grados.alumno(f, int(ciclo[:4]), expedientes.get(f[5])) for f in filas]
        try:
            contenido = libro_grados.libro(alumnos, ciclo, self.hoy)
        except libro_grados.ErrorLibro as error:
            raise ErrorBandeja(str(error))
        return f'sidp_por_grado_{self.hoy.isoformat()}.xlsx', contenido, hoja.MIME_XLSX

    def _tipos_escaneo(self):
        propias = {p['clave']: p['nombre'] for p in self.plantillas.activas() if not p.get('fabrica')}
        return {**{k: v for k, v in extraer.ESPACIOS.items() if k != 'otro'}, **propias, 'otro': extraer.ESPACIOS['otro']}

    # --- Plantillas de documentos (las agrega un administrativo desde el panel) ---

    def documentos_padres(self):
        """Lo que la página de padres pide, en orden: los de fábrica y luego los de la escuela."""
        return [{'clave': p['clave'], 'nombre': p['nombre'], 'de': p['de'], 'obligatorio': p['obligatorio']}
                for p in self.plantillas.activas() if p['para_padres']]

    def lista_plantillas(self):
        return {'plantillas': list(self.plantillas.todas().values()), 'reglas': plantillas_mod.REGLAS, 'de': plantillas_mod.DE_QUIEN,
                'campos': {'tipos': campos_mod.TIPOS, 'categorias': campos_mod.CATEGORIAS, 'de': campos_mod.DE_NOMBRES}}

    def _muestras(self, archivos):
        if not archivos:
            raise ErrorBandeja('Sube una muestra del documento (PDF o foto)')
        for nombre, contenido in archivos:
            if Path(nombre).suffix.lower() not in ACEPTADOS or not 0 < len(contenido) <= plantillas_mod.MAXIMO_MUESTRA:
                raise ErrorBandeja(f'Muestra no aceptada: {nombre} (PDF o foto, hasta 15 MB)')
        return [(Path(nombre).name, contenido) for nombre, contenido in archivos]

    def plantilla_leer(self, archivos):
        """Lee una o varias muestras y propone los textos fijos. No guarda nada."""
        lecturas, procesado_en = self._leer(self._muestras(archivos))
        textos = [l['texto'] for l in lecturas]
        sin_texto = [n for (n, _), t in zip(archivos, textos) if len(t.strip()) < lector.MINIMO_TEXTO]
        return {'textos': plantillas_mod.proponer_textos([t for t in textos if len(t.strip()) >= lector.MINIMO_TEXTO]),
                'procesado_en': procesado_en, 'sin_texto': sin_texto,
                'parecido': {p['nombre']: plantillas_mod.cuantos_dice('\n'.join(textos), p) for p in self.plantillas.activas()
                             if plantillas_mod.cuantos_dice('\n'.join(textos), p)}}

    def plantilla_guardar(self, datos, archivos=(), quien='administrador'):
        try:
            plantilla = self.plantillas.guardar(datos, quien, self._muestras(archivos) if archivos else ())
        except plantillas_mod.ErrorPlantilla as error:
            raise ErrorBandeja(str(error))
        if self.registro:
            self.registro.usar_plantillas([plantilla])
        return {'guardada': plantilla, **self.lista_plantillas()}

    def plantilla_muestra(self, clave, archivo):
        actual = self.plantillas.todas().get(clave)
        if not actual or Path(archivo).name not in actual.get('muestras', []):
            raise ErrorBandeja('No existe esa muestra')
        return self.plantillas.carpeta / clave / Path(archivo).name

    def plantilla_activa(self, clave, activa, quien='administrador'):
        """Dar de baja (o volver a pedir) un documento. Es otra versión: lo anterior queda."""
        actual = self.plantillas.todas().get(clave)
        if not actual:
            raise ErrorBandeja('No existe esa plantilla')
        return self.plantilla_guardar({**actual, 'activa': bool(activa)}, quien=quien)

    def _lote(self, lote):
        carpeta = self.carpeta / 'escaneos' / str(lote)
        if not lote or Path(str(lote)).name != lote or not (carpeta / 'lote.json').exists():
            raise ErrorBandeja('Ese escaneo ya no existe: vuelve a subirlo')
        return carpeta

    def escaneo_pagina(self, lote, archivo):
        ruta = self._lote(lote) / Path(archivo).name
        if ruta.suffix == '.json' or not ruta.is_file():
            raise ErrorBandeja('No existe esa página')
        return ruta

    def escaneo_descartar(self, lote):
        shutil.rmtree(self._lote(lote))
        return {'descartado': lote}

    def escaneo_guardar(self, lote, datos, quien='administrador'):
        """Guarda el expediente escaneado con los datos que confirmó la persona. Queda validado en papel."""
        carpeta_lote = self._lote(lote)
        guardado = json.loads((carpeta_lote / 'lote.json').read_text(encoding='utf-8'))
        alumno = {k: str(v or '').strip() for k, v in (datos.get('alumno') or {}).items()}
        tutor = {k: str(v or '').strip() for k, v in (datos.get('tutor') or {}).items()}
        if not alumno.get('nombres') or not alumno.get('primer_apellido'):
            raise ErrorBandeja('Faltan el nombre o el primer apellido del alumno')
        for persona, quien_es in ((alumno, 'del alumno'), (tutor, 'del tutor')):
            persona['curp'] = persona.get('curp', '').upper()
            if persona['curp'] and not comparador.desglose_curp(persona['curp']):
                raise ErrorBandeja(f'La CURP {quien_es} no tiene la forma correcta: corrígela o déjala vacía')
            persona['nombre'] = ' '.join(filter(None, (persona.get('nombres'), persona.get('primer_apellido'), persona.get('segundo_apellido'))))
        tipos = datos.get('paginas') or {}
        alumno_id = str(datos.get('alumno_id') or '') or None  # El alumno de la lista de su grupo, si la persona lo eligió.
        if alumno_id and not (self.registro and self.registro.db.execute('SELECT 1 FROM alumno WHERE id = ?', (alumno_id,)).fetchone()):
            raise ErrorBandeja('Ese alumno ya no está en las listas: elígelo otra vez')
        if alumno_id and alumno['curp'] and self.registro.db.execute('SELECT 1 FROM alumno WHERE curp = ? AND id != ?',
                                                                     (alumno['curp'], alumno_id)).fetchone():
            raise ErrorBandeja(f'La CURP {alumno["curp"]} ya es de otro alumno: revisa que elegiste al alumno correcto')
        grupo_id = None if alumno_id else str(datos.get('grupo_id') or '') or None  # Alumno nuevo: el grupo donde va.
        if grupo_id and not (self.registro and self.registro.db.execute('SELECT 1 FROM grupo WHERE id = ?', (grupo_id,)).fetchone()):
            raise ErrorBandeja('Ese grupo ya no existe: elígelo otra vez')
        captura = {'alumno': alumno, 'tutor': tutor if tutor.get('nombres') and tutor.get('primer_apellido') else {}, 'origen': 'escaneo'}
        carpeta_expedientes = self.carpeta / 'expedientes'
        carpeta_expedientes.mkdir(parents=True, exist_ok=True)
        numero = max([int(n) for n in self.expedientes() if n.isdigit()] or [0]) + 1
        identificador = f'{numero:04d}'
        destino = carpeta_expedientes / identificador
        destino.mkdir()
        por_tipo, validos = {}, self._tipos_escaneo()
        for pagina in guardado['paginas']:
            tipo = tipos.get(pagina['archivo'], pagina['tipo'])
            por_tipo.setdefault(tipo if tipo in validos else 'otro', []).append(carpeta_lote / pagina['archivo'])
        guardados, documentos = [], {}
        for tipo, rutas in por_tipo.items():
            pdfs = [r for r in rutas if r.suffix == '.pdf']
            partes = ([('pdf', unir_pdf([r.read_bytes() for r in pdfs]))] if pdfs else []) + [(r.suffix[1:], r.read_bytes()) for r in rutas if r.suffix != '.pdf']
            for numero, (extension, contenido) in enumerate(partes, 1):
                archivo = destino / f'{tipo}_{numero}.{extension}'
                archivo.write_bytes(contenido)
                guardados.append((tipo, archivo.relative_to(self.carpeta).as_posix(), contenido))
                documentos.setdefault(tipo, {'archivos': [], 'paginas': 0})
                documentos[tipo]['archivos'].append(archivo.name)
            documentos[tipo]['paginas'] = len(rutas)
        (destino / 'captura.json').write_text(json.dumps(captura, ensure_ascii=False, indent=1), encoding='utf-8')
        resultado = {'id': identificador, 'estado': EN_PAPEL, 'hallazgos': [], 'grises': [], 'no_leidos': [],
                     'extraidos': guardado.get('extraidos', {}), 'documentos': documentos, 'procesado_en': 'escaneo', 'segundos': 0}
        (destino / 'resultado.json').write_text(json.dumps(resultado, ensure_ascii=False), encoding='utf-8')
        self.resultados[identificador] = resultado
        if self.registro:
            ids = self.registro.registrar(captura, guardados, resultado['extraidos'], alumno_id=alumno_id)
            (destino / 'registro.json').write_text(json.dumps(ids), encoding='utf-8')
            if grupo_id and not self.grupos.ubicacion(ids['alumno']):
                self._con_grupos(lambda: self.grupos.ubicar(ids['alumno'], grupo_id))
        self.decidir(identificador, 'autorizado', 'Validado en papel por la escuela (escaneo)', quien)
        shutil.rmtree(carpeta_lote, ignore_errors=True)
        return {'expediente': identificador, 'alumno': alumno['nombre'], **self._quien(identificador)}

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
        if decision == 'autorizado':
            self.archivar(identificador)
            self.encargar_datos(identificador)
        if decision == 'rechazado':
            respuesta['reporte_para_padre'] = reporte_para_padre(resultado, motivo)
        return respuesta

    def archivar(self, identificador):
        """Copia los documentos autorizados a la carpeta del alumno, en PDF. Si falla, avisa y no detiene nada."""
        if not self.archivero:
            return None
        carpeta = self.carpeta / 'expedientes' / identificador
        quien = self._quien(identificador)
        try:
            captura = json.loads((carpeta / 'captura.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            captura = {}
        datos = captura.get('alumno') or {}
        nombre, curp = None, (datos.get('curp') or '').upper()
        if quien['alumno_id'] and self.registro:
            fila = self.registro.db.execute('SELECT primer_apellido, segundo_apellido, nombres, curp FROM alumno WHERE id = ?',
                                            (quien['alumno_id'],)).fetchone()
            if fila:
                nombre, curp = ' '.join(x for x in fila[:3] if x), fila[3] or curp
        nombre = nombre or ' '.join(filter(None, (datos.get('primer_apellido'), datos.get('segundo_apellido'), datos.get('nombres')))) or quien['alumno']
        if not nombre:
            return None
        nombres = {**{k: v for k, (v, *_resto) in expediente.TIPOS.items()}, **self._tipos_escaneo()}
        documentos = {}
        for archivo in sorted(carpeta.iterdir()):
            if not archivo.is_file() or archivo.suffix.lower() not in ('.pdf', *archivero.IMAGENES):
                continue
            tipo = archivo.stem.rsplit('_', 1)[0] if archivo.stem.rsplit('_', 1)[-1].isdigit() else archivo.stem
            documentos.setdefault(nombres.get(tipo, tipo.replace('_', ' ').capitalize()), []).append((archivo.suffix, archivo.read_bytes()))
        try:
            destino, hecho = self.archivero.archivar(curp or f'expediente-{identificador}', nombre.upper(), quien['grupo'], documentos)
        except Exception as error:
            self.archivo_aviso = f'No se pudo copiar el expediente {identificador} a la carpeta de alumnos: {error}'
            return None
        self.archivo_aviso = None
        return {'carpeta': str(destino), 'documentos': hecho}

    # --- Sacar los datos en la PC 4 (validacion/taller.py) ---

    def _pendientes(self):
        carpeta = self.carpeta / 'pendientes_pc4'
        carpeta.mkdir(exist_ok=True)
        return carpeta

    def encargar_datos(self, identificador):
        """Le encarga a la PC 4 sacar los datos de un expediente autorizado. Si no está, queda pendiente y se manda solo después."""
        (self._pendientes() / f'{identificador}.json').write_text(json.dumps({'expediente': identificador}), encoding='utf-8')
        if self.cerebro:
            self.enviar_pendientes()

    def _pedido_datos(self, identificador):
        carpeta = self.carpeta / 'expedientes' / identificador
        quien = self._quien(identificador)
        curp = None
        if quien['alumno_id'] and self.registro:
            fila = self.registro.db.execute('SELECT curp FROM alumno WHERE id = ?', (quien['alumno_id'],)).fetchone()
            curp = fila and fila[0]
        if not curp:
            try:
                curp = (json.loads((carpeta / 'captura.json').read_text(encoding='utf-8')).get('alumno') or {}).get('curp')
            except (OSError, ValueError):
                curp = None
        if not curp or not carpeta.is_dir():
            return None
        plantillas = self.plantillas.todas()
        nombres = self._tipos_escaneo()
        documentos = []
        for archivo in sorted(carpeta.iterdir()):
            if not archivo.is_file() or archivo.suffix.lower() not in ('.pdf', *archivero.IMAGENES):
                continue
            tipo = archivo.stem.rsplit('_', 1)[0] if archivo.stem.rsplit('_', 1)[-1].isdigit() else archivo.stem
            lista = campos_mod.de_documento(tipo, plantillas.get(tipo))
            if not lista:
                continue
            documentos.append({'archivo': archivo.name, 'tipo': tipo, 'nombre': nombres.get(tipo, tipo), 'campos': lista,
                               'contenido': base64.b64encode(archivo.read_bytes()).decode()})
        return {'curp': curp.upper(), 'expediente': identificador, 'documentos': documentos} if documentos else None

    def enviar_pendientes(self):
        """Manda a la PC 4 los expedientes que esperan que les saquen los datos. Devuelve cuántos se mandaron."""
        if not self.cerebro:
            return 0
        enviados, padron = 0, False
        for archivo in sorted(self._pendientes().glob('*.json')):
            identificador = archivo.stem
            pedido = self._pedido_datos(identificador)
            if pedido is None:
                archivo.unlink()  # Sin CURP o sin documentos con campos: no hay qué sacar.
                continue
            try:
                cerebro_red.pedir_a_cerebro(*self.cerebro, '/trabajo', pedido, 300)
            except cerebro_red.ErrorCerebro as error:
                if error.code != 409 or padron:
                    self.datos_aviso = f'La PC 4 no recibió el expediente {identificador}: {error}'
                    continue
                padron = True  # El alumno es nuevo: primero va la lista de alumnos y luego otra vez el expediente.
                self.enviar_padron()
                try:
                    cerebro_red.pedir_a_cerebro(*self.cerebro, '/trabajo', pedido, 300)
                except Exception as otro:
                    self.datos_aviso = f'La PC 4 no recibió el expediente {identificador}: {otro}'
                    continue
            except OSError as error:
                self.datos_aviso = f'La PC 4 no respondió; los datos se sacan cuando vuelva ({error}).'
                break
            archivo.unlink()
            enviados += 1
        if enviados:
            self.datos_aviso = None
        return enviados

    def trabajos_pc4(self):
        estado = self._pc4('/trabajos')
        estado['pendientes_de_enviar'] = len(list(self._pendientes().glob('*.json')))
        estado['aviso'] = self.datos_aviso
        return estado

    def alumno_pc4(self, curp):
        """El expediente completo del alumno: sus datos (PC 4) y sus PDF (carpeta de este servidor)."""
        from urllib.parse import quote
        datos = self._pc4('/alumno?curp=' + quote((curp or '').upper()))
        datos['pdf'] = []
        if self.archivero:
            ruta = self.archivero._indice().get((curp or '').upper())
            carpeta = self.archivero.raiz / ruta if ruta else None
            if carpeta and carpeta.is_dir():
                datos['carpeta'] = str(carpeta)
                datos['pdf'] = [{'nombre': a.stem, 'ruta': a.relative_to(self.archivero.raiz).as_posix()} for a in sorted(carpeta.glob('*.pdf'))]
        return datos

    def pdf(self, ruta):
        """Un PDF de la carpeta de expedientes (para verlo desde el panel)."""
        if not self.archivero:
            raise ErrorBandeja('Aquí no hay carpeta de expedientes')
        raiz = self.archivero.raiz.resolve()
        try:
            destino = (raiz / respaldo.ruta_segura(ruta)).resolve()
        except ValueError:
            raise ErrorBandeja('No existe ese documento')
        if destino.suffix.lower() != '.pdf' or not destino.is_file() or raiz not in destino.parents:
            raise ErrorBandeja('No existe ese documento')
        return destino.read_bytes()

    def dato_confirmar(self, datos):
        return self._pc4('/dato/confirmar', datos)

    def dato_varios(self, datos, quien):
        return self._pc4('/dato/varios', {'datos': list(datos.get('datos') or []), 'persona': quien})

    # --- Documentos oficiales (validacion/documentos.py): los arma la PC 4; si no contesta, salen de aquí ---

    def documentos_lista(self, escuela):
        datos = {'escuela': {'completa': escuela['completa'], 'faltan': escuela['faltan']}, 'documentos': documentos.catalogo(), 'faltan': []}
        try:
            datos.update({k: v for k, v in self._pc4('/documentos', espera=60).items() if k in ('faltan', 'ciclo', 'alumnos')})
        except ErrorBandeja as error:
            datos['aviso'] = (f'{error} Mientras, los documentos salen con las listas de grupo de aquí, sin lo que sacó el escaneo '
                              '(salud, repetidores, becas).')
        return datos

    def _grupo_de(self, grupo_id):
        grupo = self._con_grupos(lambda: self.grupos.alumnos(grupo_id))
        return grupo['grupo']['grado'], grupo['grupo']['letra'], grupo['alumnos']

    def documento_preparar(self, pedido):
        """De qué grupo o alumno es el documento y, por si la PC 4 no contesta, los alumnos de las listas de aquí."""
        preparado = {'clave': pedido.get('clave'), 'formato': pedido.get('formato'), 'grado': None, 'letra': None, 'curp': None}
        if pedido.get('grupo_id'):
            preparado['grado'], preparado['letra'], alumnos = self._grupo_de(pedido['grupo_id'])
            if pedido.get('alumno_id'):
                preparado['curp'] = next((a['curp'] for a in alumnos if str(a['id']) == str(pedido['alumno_id'])), None)
                if not preparado['curp']:
                    raise ErrorBandeja('Ese alumno no tiene CURP en la lista: agrégala en «Alumnos y grupos».')
        _, ciclo = self._con_grupos(self.grupos.ciclo)
        preparado['ciclo'] = ciclo
        preparado['registros'] = documentos.de_lista(self._con_grupos(self.grupos.exportar_alumnos)[1:], ciclo, self.hoy)
        return preparado

    def documento_generar(self, preparado, escuela):
        """(nombre, contenido, tipo) del documento: de la PC 4 con todos los datos o, si no contesta, de las listas de aquí."""
        lugar = {k: preparado[k] for k in ('grado', 'letra', 'curp')}
        if self.cerebro:
            pedido = {'clave': preparado['clave'], 'formato': preparado['formato'], 'escuela': escuela, **lugar}
            try:
                r = cerebro_red.pedir_a_cerebro(*self.cerebro, '/documento', pedido, 180)
                return r['nombre'], base64.b64decode(r['contenido']), r['tipo']
            except cerebro_red.ErrorCerebro as error:
                if error.code != 503:  # 503: la PC 4 sin base de datos; sale con lo de aquí.
                    raise ErrorBandeja(f'La PC 4 dice: {error}')
            except OSError:
                pass  # La PC 4 no contesta: sale con lo de aquí.
        try:
            return documentos.generar(preparado['clave'], preparado['formato'], preparado['registros'], escuela, preparado['ciclo'],
                                      self.hoy, **lugar)
        except documentos.ErrorDocumento as error:
            raise ErrorBandeja(str(error))

    def documentos_completar(self, grupo_id):
        """Los alumnos de un grupo con lo del 911 que pone la escuela (repite, beca, lengua...), para completarlo."""
        from urllib.parse import urlencode
        grado, letra, _ = self._grupo_de(grupo_id)
        return self._pc4('/registros?' + urlencode({'grado': grado, 'letra': letra}), espera=60)

    # --- Biblioteca (validacion/biblioteca.py): vive en la base de la PC 4 ---

    def biblioteca(self):
        return self._pc4('/biblioteca')

    def biblioteca_identificar(self, archivos, quien):
        fotos = [{'nombre': nombre, 'contenido': base64.b64encode(contenido).decode()} for nombre, contenido in archivos[:3]]
        if not fotos:
            raise ErrorBandeja('Pon al menos una foto del libro.')
        return self._pc4('/biblioteca/identificar', {'fotos': fotos, 'actor': quien}, espera=330)

    def biblioteca_hacer(self, accion, datos, quien):
        return self._pc4(f'/biblioteca/{accion}', {**datos, 'actor': quien})

    def biblioteca_etiquetas(self, codigos, escuela):
        from urllib.parse import quote
        etiquetas = self._pc4('/biblioteca/etiquetas?codigos=' + quote(','.join(codigos[:300])))['etiquetas']
        pagina = codigo_barras.hoja_etiquetas(etiquetas, **({'escuela': escuela} if escuela else {}))
        return pagina.replace('Etiquetas de inventario', 'Etiquetas de la biblioteca').replace(
            'Pégalas en un lugar que no se raspe.', 'Pégalas en la contraportada, arriba a la derecha, sin tapar el código de barras.')

    def dato_agregar(self, datos):
        return self._pc4('/dato/agregar', datos)

    def por_confirmar(self):
        return self._pc4('/por_confirmar')

    def alumno_baja(self, datos, borrar=False):
        """Da de baja (o borra) al alumno en la PC 4 y lo quita de las listas de grupo de aquí."""
        curp = (datos.get('curp') or '').upper()
        motivo = (datos.get('motivo') or '').strip()
        if not motivo:
            raise ErrorBandeja('Escribe el motivo')
        if borrar and datos.get('confirmar') != 'BORRAR':
            raise ErrorBandeja('Para borrar, escribe BORRAR con mayúsculas')
        hecho = self._pc4('/alumno/borrar' if borrar else '/alumno/baja', {'curp': curp, 'motivo': motivo, 'persona': datos.get('persona')})
        if self.grupos and self.registro:
            fila = self.registro.db.execute('SELECT id FROM alumno WHERE curp = ?', (curp,)).fetchone()
            if fila:
                self._con_grupos(lambda: self.grupos.dar_baja(fila[0], ('Borrado: ' if borrar else '') + motivo))
        return hecho

    def campos_proponer(self, nombre, contenido):
        """El modelo que ve de la PC 4 lee una muestra y propone los campos de la plantilla (tarda unos minutos)."""
        return self._pc4('/plantilla/campos', {'nombre': nombre, 'contenido': base64.b64encode(contenido).decode()}, 900)

    def archivar_todo(self):
        """Pone en carpetas todo lo ya autorizado (al instalar en una PC que ya tenía expedientes)."""
        return [self.archivar(i) for i, d in self.decisiones().items() if (d or {}).get('decision') == 'autorizado']

    def detalle(self, identificador):
        carpeta = self._carpeta(identificador)
        try:
            captura = json.loads((carpeta / 'captura.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            captura = {}
        archivos = [a.name for a in sorted(carpeta.iterdir()) if a.is_file() and a.suffix != '.json' and not a.name.startswith('.')]
        textos = {a: (carpeta / a).read_text(encoding='utf-8', errors='replace') for a in archivos if a.endswith('.txt')} if self.editable else {}
        quien = self._quien(identificador)
        # Un alumno que llegó por la página de padres y no está en las listas: se proponen los parecidos para ubicarlo.
        parecidos = (self.grupos.parecidos(quien['alumno'], (captura.get('alumno') or {}).get('curp') or None)
                     if self.grupos and quien['alumno_id'] and not quien['grupo'] else [])
        return {'id': identificador, 'captura': captura, 'archivos': archivos, 'textos': textos,
                'resultado': self.resultados.get(identificador), 'decision': self.decisiones().get(identificador),
                **quien, 'parecidos': parecidos}

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
            resultado = self.registro.validar_constancia(contenido, guardar)
        except renapo.ErrorConstancia as error:
            raise ErrorBandeja(str(error)) from error
        if resultado.get('corregido'):
            self.enviar_padron()  # El nombre corregido va ya a la PC 4.
        return resultado

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
                          'trampa': marca and marca['trampa'], 'decision': decisiones.get(identificador), **self._quien(identificador)})
        autorizados_falsos = sum(1 for f in filas if f['etiqueta'] == 'falso' and f['decision']
                                 and f['decision']['decision'] == 'autorizado')
        return {'carpeta': str(self.carpeta), 'hoy': self.hoy.isoformat(), 'expedientes': filas,
                'medidas': {'revisados': len(revisados), 'listos': sum(r['estado'] == LISTO for r in revisados),
                            'revision': sum(r['estado'] not in (LISTO, EN_PAPEL) for r in revisados),
                            'en_papel': sum(r['estado'] == EN_PAPEL for r in revisados), 'etiquetados': medidas['etiquetados'],
                            'falsos': medidas['falsos'], 'falsos_detectados': medidas['falsos_detectados'],
                            'falsos_pasaron': medidas['falsos_pasaron'], 'verdaderos': medidas['verdaderos'],
                            'falsas_alarmas': medidas['falsas_alarmas'],
                            'autorizados': sum(1 for d in decisiones.values() if d['decision'] == 'autorizado'),
                            'rechazados': sum(1 for d in decisiones.values() if d['decision'] == 'rechazado'),
                            'falsos_autorizados': autorizados_falsos}}
