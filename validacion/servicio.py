"""Bandeja del administrador: revisa los expedientes de una carpeta y guarda quién autorizó o rechazó.

La usan SIDP-Validador.exe (validacion/aplicacion.py) y la página de demostración, que corre
este mismo código en el navegador con expedientes inventados. Las decisiones van a una base
SQLite en la carpeta (`decisiones.db`): solo se agregan, nunca se cambian ni se borran, y la
última de cada expediente es la que cuenta.
"""
import datetime
import hashlib
import io
import json
import secrets
import shutil
import sqlite3
from pathlib import Path

from validacion import cerebro_red, comparador, expediente, extraer, hoja, lector, modelo, prueba, renapo
from validacion.grupos import ErrorGrupo, Grupos
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
        return problema

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
            pagina.update(texto=lectura['texto'], qr=lectura['qr'], problemas=lectura['problemas'])
        extraer.agrupar(paginas, self.plantillas.activas())
        propuesta = extraer.proponer(paginas, self.hoy)
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
                'paginas': [{k: p[k] for k in ('archivo', 'origen', 'tipo', 'reconocido')} for p in paginas]}

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
            return {'alumno': datos.get('nombre') or ' '.join(filter(None, (datos.get('nombres'), datos.get('primer_apellido')))) or None,
                    'grupo': None, 'alumno_id': None}
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
        """La lista de un grupo, escaneada o escrita: propone los renglones y el grado y grupo. No guarda nada."""
        sin_texto, procesado_en = [], None
        if archivos:
            lecturas, procesado_en = self._leer(self._muestras(archivos))
            sin_texto = [n for (n, _), l in zip(archivos, lecturas) if len(l['texto'].strip()) < lector.MINIMO_TEXTO]
            texto = '\n'.join(l['texto'] for l in lecturas) + '\n' + (texto or '')
        if not str(texto or '').strip():
            raise ErrorBandeja('Sube la lista escaneada o escribe los nombres, uno por renglón')
        grado, letra = extraer.grado_y_grupo(texto)
        return {'filas': extraer.lista_de_grupo(texto, apellidos_primero), 'grado': grado, 'letra': letra,
                'procesado_en': procesado_en, 'sin_texto': sin_texto}

    def lista_guardar(self, datos):
        def guardar():
            grupo = self.grupos.crear(datos.get('grado'), datos.get('letra'))
            return self.grupos.guardar_lista(grupo, datos.get('filas') or [])
        resultado = self._con_grupos(guardar)
        return {**resultado, **self.grupos.lista()}

    def grupo_crear(self, grado, letra):
        self._con_grupos(lambda: self.grupos.crear(grado, letra))
        return self.grupos.lista()

    def buscar_alumno(self, nombre, curp=None):
        return {'parecidos': self._con_grupos(lambda: self.grupos.parecidos(nombre, (curp or '').upper() or None))}

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

    def _tipos_escaneo(self):
        propias = {p['clave']: p['nombre'] for p in self.plantillas.activas() if not p.get('fabrica')}
        return {**{k: v for k, v in extraer.ESPACIOS.items() if k != 'otro'}, **propias, 'otro': extraer.ESPACIOS['otro']}

    # --- Plantillas de documentos (las agrega un administrativo desde el panel) ---

    def documentos_padres(self):
        """Lo que la página de padres pide, en orden: los de fábrica y luego los de la escuela."""
        return [{'clave': p['clave'], 'nombre': p['nombre'], 'de': p['de'], 'obligatorio': p['obligatorio']}
                for p in self.plantillas.activas() if p['para_padres']]

    def lista_plantillas(self):
        return {'plantillas': list(self.plantillas.todas().values()), 'reglas': plantillas_mod.REGLAS, 'de': plantillas_mod.DE_QUIEN}

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
        self.decidir(identificador, 'autorizado', 'Validado en papel por la escuela (escaneo)', quien)
        shutil.rmtree(carpeta_lote, ignore_errors=True)
        return {'expediente': identificador, 'alumno': alumno['nombre']}

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
