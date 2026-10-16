"""El taller de la PC 4: saca los datos de los expedientes escaneados, uno por uno y sin prisa.

El servidor guarda los PDF al momento y le encarga a la PC 4 sacar sus datos (POST /trabajo). La PC 4 los
trabaja en fila, en segundo plano, aunque tarde (el modelo que ve tarda de 30 segundos a 2 minutos por hoja):

1. Procesos fijos: texto del PDF u OCR, QR, CURP con dígito verificador, fechas, la franja de la INE.
2. El modelo que ve (si está instalado) lee la hoja con la lista de campos de su plantilla, incluida la letra a mano.
3. Las reglas de campos.py limpian cada valor y le ponen confianza; lo que coincide entre los dos sube a "alta".
4. Todo va a sidp.dato. Lo dudoso queda "por confirmar" y una persona lo ve en el panel con la hoja al lado.

Los archivos del trabajo se guardan en C:\\SIDP-datos\\trabajos\\<id> y se borran al terminar (el servidor tiene
los originales y la PC 4 ya tiene su copia en el respaldo).
"""
import base64
import datetime
import json
import os
import re
import shutil
import threading
import time
from pathlib import Path

from validacion import campos as campos_mod
from validacion import comparador, extraer, lector, modelo, vision

MAXIMO_HOJAS = 3  # Por documento, al modelo que ve (las demás hojas casi nunca traen datos nuevos).
INTENTOS = 3
# Con 1 lectura y esquema plano tarda ~33 s por hoja en la PC 4; con 2 lecturas (~45 s) compara orden normal e inverso.
LECTURAS = int(os.environ.get('SIDP_LECTURAS_VISION') or 1)
TIPOS_SEGUROS_1 = ('fecha', 'sangre', 'si_no', 'numero')
TIPOS_SEGUROS_2 = TIPOS_SEGUROS_1 + ('telefono', 'cp')


def _visto(v, tipo=None, lecturas=1):
    if isinstance(v, dict):
        return v
    s = str(v or '').strip()
    dudoso = s.endswith('?')
    valor = s[:-1].strip() if dudoso else s
    seguros = TIPOS_SEGUROS_1 if lecturas < 2 else TIPOS_SEGUROS_2
    return {'valor': valor, 'seguro': (not dudoso) and (tipo is None or tipo in seguros)}


def carpeta_por_omision():
    return Path(os.environ.get('SIDP_TRABAJOS') or (Path('C:/SIDP-datos/trabajos') if os.name == 'nt' else Path.home() / 'SIDP-datos' / 'trabajos'))


def _identidad(fila):
    """Lo que ya se sabe del alumno (lista oficial): con esto se comparan las lecturas."""
    curp, nombres, primero, segundo, nacimiento, sexo = fila
    return {'curp': curp or '', 'nombre': ' '.join(filter(None, (nombres, primero, segundo))), 'nombres': nombres,
            'primer_apellido': primero, 'segundo_apellido': segundo or '',
            'fecha_nacimiento': nacimiento.isoformat() if nacimiento else '', 'sexo': sexo or ''}


def de_procesos(tipo, texto, qr, hoy, metodo_texto='texto'):
    """Lo que dan los procesos fijos: {clave del campo: (valor, metodo)}. metodo_texto: 'ocr' si el texto salió de
    una foto o un escaneo (puede traer letras confundidas), 'texto' si venía escrito en el PDF."""
    pagina = {'archivo': 'hoja', 'texto': texto, 'qr': qr, 'tipo': tipo}
    propuesta = extraer.proponer([pagina], hoy)
    salida = {}
    metodo = 'qr' if qr else metodo_texto
    alumno, tutor = propuesta.get('alumno') or {}, propuesta.get('tutor') or {}
    if tipo in ('acta_alumno', 'constancia_curp'):
        for clave in ('curp', 'nombres', 'primer_apellido', 'segundo_apellido', 'fecha_nacimiento'):
            if alumno.get(clave):
                salida[clave] = (alumno[clave], metodo)
        for quien, papa in ((propuesta.get('extraidos') or {}).get('padres_en_acta') or {}).items():
            if isinstance(papa, str):  # "PEDRO GARCIA RUIZ"
                papa = {'nombre': papa}
            nombre = papa.get('nombre') or ' '.join(filter(None, (papa.get('nombres'), papa.get('primer_apellido'), papa.get('segundo_apellido'))))
            if nombre:
                salida[f'nombre_{quien}'] = (nombre, metodo)
            if papa.get('curp'):
                salida[f'curp_{quien}'] = (papa['curp'], metodo)
    if tipo in ('ine_tutor', 'acta_tutor'):
        nombre = ' '.join(filter(None, (tutor.get('nombres'), tutor.get('primer_apellido'), tutor.get('segundo_apellido'))))
        if nombre:
            salida['nombre_tutor'] = (nombre, metodo)
        if tutor.get('curp'):
            salida['curp_tutor'] = (tutor['curp'], metodo)
    if tipo == 'ine_tutor':  # La INE impresa: el domicilio va abajo de "DOMICILIO" y la vigencia junto a "VIGENCIA".
        renglones = [r.strip() for r in str(texto or '').upper().splitlines() if r.strip()]
        for i, renglon in enumerate(renglones):
            if renglon == 'DOMICILIO' and i + 1 < len(renglones):
                siguientes = [r for r in renglones[i + 1:i + 4] if not re.match(r'CLAVE|CURP|FECHA|SECCI|VIGENCIA|A[ÑN]O', r)]
                salida['domicilio_ine'] = (' '.join(siguientes[:2]), metodo)
            if m := re.search(r'VIGENCIA\s*:?\s*(\d{4}\s*-\s*\d{4}|\d{4})', renglon):
                salida['vigencia_ine'] = (re.sub(r'\s+', '', m[1]), metodo)
    if tipo == 'comprobante':
        if fecha := (propuesta.get('extraidos') or {}).get('comprobante_fecha'):
            salida['fecha_comprobante'] = (fecha, metodo)
    if tipo == 'certificado_medico':  # "se encuentra sano y apto ... a 02 de septiembre de 2026"
        mayusculas = str(texto or '').upper()
        if re.search(r'\bNO\s+(?:ES\s+|SE\s+ENCUENTRA\s+)?APT[OA]\b', mayusculas):
            salida['apto'] = ('no', metodo)
        elif re.search(r'\b(?:SAN[OA]|APT[OA])\b', mayusculas):
            salida['apto'] = ('sí', metodo)
        for renglon in reversed(mayusculas.splitlines()):
            if fecha := campos_mod.fecha(renglon, hoy):
                salida['fecha_certificado'] = (fecha, metodo)
                break
    return {k: v for k, v in salida.items() if v[0]}


def coinciden(tipo, uno, otro, hoy=None):
    if tipo == 'lista':
        return set(campos_mod.lista(uno)) == set(campos_mod.lista(otro))
    if campos_mod.vacio(uno) or campos_mod.vacio(otro):
        return campos_mod.vacio(uno) == campos_mod.vacio(otro)
    a, b = campos_mod.limpiar(tipo, uno, hoy)[0] or uno, campos_mod.limpiar(tipo, otro, hoy)[0] or otro
    return comparador.normalizar(str(a)) == comparador.normalizar(str(b))


def necesita_ver(lista, procesos):
    """False si los procesos fijos ya sacaron todos los campos de texto impreso o QR (sin OCR): ahí el modelo que ve
    solo gastaría minutos. Las hojas a mano, escaneadas o con campos que faltan sí pasan por él."""
    return any(procesos.get(c['clave'], (None, 'ocr'))[1] == 'ocr' for c in lista)


def ver(hojas, nombre_documento, lista, modelo_vision, url=modelo.URL, lecturas=None, hoy=None):
    """Lo que lee el modelo que ve: ({clave: {valor, seguro}}, segundos). Con dos lecturas, lo que no coincide no es seguro."""
    cuantas = lecturas or LECTURAS
    primera, segundos = vision.preguntar(hojas, campos_mod.pregunta(nombre_documento, lista), campos_mod.esquema(lista), modelo_vision, url)
    if not primera:
        return primera, segundos
    primera = {c['clave']: _visto(primera.get(c['clave']), c['tipo'], cuantas) for c in lista if c['clave'] in primera}
    if cuantas < 2:
        return primera, segundos
    al_reves = list(reversed(lista))
    segunda, mas = vision.preguntar(hojas, campos_mod.pregunta(nombre_documento, al_reves), campos_mod.esquema(al_reves), modelo_vision, url)
    for c in lista:
        a, b = _visto(primera.get(c['clave']), c['tipo'], 2), _visto((segunda or {}).get(c['clave']), c['tipo'], 2)
        uno, otro = str(a.get('valor') or '').strip(), str(b.get('valor') or '').strip()
        if not uno and not otro:
            continue
        if not coinciden(c['tipo'], uno, otro, hoy):
            primera[c['clave']] = {'valor': uno or otro, 'seguro': False, 'otra': otro if uno else ''}
        else:
            primera[c['clave']] = {'valor': uno, 'seguro': bool(a.get('seguro')) and bool(b.get('seguro'))}
    return primera, segundos + mas


def combinar(campos, procesos, vistos, identidad, hoy):
    """Un valor por campo con su confianza. vistos: lo que leyó el modelo {clave: {valor, seguro}}."""
    salida = []
    for c in campos:
        de_proceso, metodo = procesos.get(c['clave'], (None, None))
        visto = _visto((vistos or {}).get(c['clave']), c['tipo']) if vistos and c['clave'] in vistos else {}
        crudo_visto = str(visto.get('valor') or '').strip()
        limpio_p, detalle_p = campos_mod.limpiar(c['tipo'], de_proceso, hoy) if de_proceso else (None, {})
        limpio_v, detalle_v = campos_mod.limpiar(c['tipo'], crudo_visto, hoy) if crudo_visto and not campos_mod.vacio(crudo_visto) else (None, {})
        if c['tipo'] == 'lista' and crudo_visto and campos_mod.vacio(crudo_visto):
            salida.append({**c, 'valores': [], 'confianza': 'media', 'metodo': 'vision', 'nada': True})
            continue
        if limpio_p and limpio_v:
            iguales = comparador.normalizar(str(limpio_p)) == comparador.normalizar(str(limpio_v))
            valor, detalle = (limpio_p, detalle_p)
            confianza, metodo = ('alta', f'{metodo}+vision') if iguales else ('baja', metodo)
            if not iguales and metodo == 'ocr':  # En una foto, el modelo que ve suele leer mejor que el OCR: se propone lo suyo.
                valor, detalle, metodo = limpio_v, {**detalle_v, 'otra_lectura': limpio_p}, 'vision'
            elif not iguales:
                detalle = {**detalle, 'otra_lectura': limpio_v}
        elif limpio_p:
            valor, detalle = limpio_p, detalle_p
            # El OCR de una foto confunde 5 con 3 o 7 con 1: solo, queda por confirmar (la CURP se salva con su dígito).
            confianza = 'alta' if c['tipo'] == 'curp' or metodo == 'qr' else 'baja' if metodo == 'ocr' else 'media'
        elif limpio_v:
            valor, detalle, metodo = limpio_v, detalle_v, 'vision'
            confianza = 'media' if visto.get('seguro') else 'baja'
            if visto.get('otra'):
                detalle = {**detalle, 'otra_lectura': visto['otra']}
        elif crudo_visto and not campos_mod.vacio(crudo_visto):
            valor, detalle, metodo, confianza = crudo_visto.upper(), {'no_paso_reglas': True}, 'vision', 'baja'
        else:
            continue
        if c['categoria'] == 'alumno' and c['campo'] in campos_mod.IDENTIDAD and identidad.get(c['campo']):
            # Ya está en la lista oficial: si coincide, el documento lo confirma; si no, se avisa.
            if comparador.normalizar(str(valor)) == comparador.normalizar(identidad[c['campo']]):
                salida.append({**c, 'valor': valor, 'confianza': 'alta', 'metodo': metodo, 'confirma_lista': True})
                continue
            confianza, detalle = 'baja', {**detalle, 'en_lista': identidad[c['campo']]}
        valores = campos_mod.lista(valor) if c['tipo'] == 'lista' else [valor]
        salida.append({**c, 'valores': valores, 'valor': valor, 'detalle': {**detalle, **({'de': c['de']} if c.get('de') else {})},
                       'confianza': confianza, 'metodo': metodo})
    return salida


class Taller:
    def __init__(self, base, carpeta=None, url=modelo.URL, hoy=None, con_vision=True):
        self.base = base
        self.carpeta = Path(carpeta or carpeta_por_omision())
        self.url = url
        self.hoy = hoy
        self.con_vision = con_vision
        self.despierta = threading.Event()
        self.ahora = None  # Qué trabajo se está haciendo (para el panel).

    # ------------------------------------------------------------ Encargar

    def encargar(self, pedido):
        """Recibe un expediente para sacarle los datos. pedido: {curp, expediente, documentos:[{archivo, tipo, nombre,
        campos, contenido}]}. Devuelve el id del trabajo."""
        curp = (pedido.get('curp') or '').upper()
        filas = self.base._consulta('SELECT id FROM sidp.alumno WHERE curp = %s', (curp,)) if curp else []
        alumno = filas[0][0] if filas else None
        if not alumno:
            raise LookupError('El alumno no está en la base de la PC 4 (falta mandar la lista de alumnos).')
        documentos = []
        for d in pedido.get('documentos') or []:
            documentos.append({'archivo': Path(d['archivo']).name, 'tipo': d.get('tipo') or 'otro', 'nombre': d.get('nombre') or d.get('tipo'),
                               'campos': campos_mod.revisar_campos(d['campos']) if d.get('campos') else campos_mod.FABRICA.get(d.get('tipo'), [])})
        if not documentos:
            raise ValueError('El trabajo no trae documentos')
        trabajo = self.base._uno('INSERT INTO sidp.trabajo (alumno_id, expediente, documentos) VALUES (%s, %s, CAST(%s AS jsonb)) RETURNING id',
                                 (alumno, str(pedido.get('expediente') or ''), json.dumps(documentos, ensure_ascii=False)))
        destino = self.carpeta / str(trabajo)
        destino.mkdir(parents=True, exist_ok=True)
        for d in pedido['documentos']:
            (destino / Path(d['archivo']).name).write_bytes(base64.b64decode(d['contenido']))
        self.despierta.set()
        return trabajo

    # ------------------------------------------------------------ Trabajar

    def siguiente(self):
        fila = self.base._consulta(
            "UPDATE sidp.trabajo SET estado = 'trabajando', intentos = intentos + 1 WHERE id = ("
            "SELECT id FROM sidp.trabajo WHERE estado = 'pendiente' OR (estado = 'trabajando' AND intentos < %s) "
            "ORDER BY id LIMIT 1) RETURNING id, alumno_id, documentos", (INTENTOS,))
        return fila[0] if fila else None

    def hacer(self, trabajo_id, alumno_id, documentos):
        identidad = _identidad(self.base._consulta(
            'SELECT curp, nombres, primer_apellido, segundo_apellido, fecha_nacimiento, sexo FROM sidp.alumno WHERE id = %s', (alumno_id,))[0])
        hoy = self.hoy or datetime.date.today()
        modelo_vision = vision.elegir(self.url) if self.con_vision else None
        cuenta = {'esperados': 0, 'alta': 0, 'media': 0, 'baja': 0, 'vacios': 0, 'segundos_vision': 0, 'modelo': modelo_vision}
        carpeta = self.carpeta / str(trabajo_id)
        for documento in documentos:
            archivo = carpeta / documento['archivo']
            if not archivo.exists():
                continue
            lectura = lector.leer(archivo)
            metodo_texto = 'ocr' if any('ocr' in m for m in lectura['metodo']) else 'texto'
            procesos = de_procesos(documento['tipo'], lectura['texto'], lectura['qr'], hoy, metodo_texto)
            for clave, valor in campos_mod.de_texto(lectura['texto'], documento['campos'], hoy).items():
                procesos.setdefault(clave, (valor, metodo_texto))
            vistos = None
            if modelo_vision and documento['campos'] and necesita_ver(documento['campos'], procesos):
                hojas = vision.paginas(archivo.read_bytes(), archivo.name)[:MAXIMO_HOJAS]
                try:
                    vistos, segundos = ver(hojas, documento['nombre'], documento['campos'], modelo_vision, self.url, hoy=hoy)
                    cuenta['segundos_vision'] += segundos
                except vision.ErrorVision as error:
                    print(f'trabajo {trabajo_id}: {error}', flush=True)
            resultado = combinar(documento['campos'], procesos, vistos, identidad, hoy)
            llenos = {r['clave'] for r in resultado}
            cuenta['esperados'] += len(documento['campos'])
            cuenta['vacios'] += len([c for c in documento['campos'] if c['clave'] not in llenos])
            for r in resultado:
                cuenta[r['confianza'] if r['confianza'] in cuenta else 'alta'] += 1
                if r.get('confirma_lista') or r.get('nada'):
                    continue
                for valor in r['valores']:
                    self.base._uno('SELECT sidp.guardar_dato(%s, %s, %s, %s, CAST(%s AS jsonb), %s, %s, %s, %s, %s, %s)',
                                   (alumno_id, r['categoria'], r['campo'], str(valor), json.dumps(r.get('detalle') or {}, ensure_ascii=False),
                                    r['confianza'], r['metodo'], documento['nombre'], trabajo_id, 'cerebro', r['campo'] in campos_mod.VARIOS))
        cuenta['utiles'] = round(100 * (cuenta['alta'] + cuenta['media']) / cuenta['esperados']) if cuenta['esperados'] else 0
        self.base._consulta("UPDATE sidp.trabajo SET estado = 'hecho', terminado = now(), resumen = CAST(%s AS jsonb), problema = NULL WHERE id = %s",
                            (json.dumps(cuenta), trabajo_id))
        shutil.rmtree(carpeta, ignore_errors=True)
        return cuenta

    def una_vez(self):
        """Hace el siguiente trabajo. None si no había."""
        siguiente = self.siguiente()
        if not siguiente:
            return None
        trabajo_id, alumno_id, documentos = siguiente
        self.ahora = trabajo_id
        try:
            return self.hacer(trabajo_id, alumno_id, documentos)
        except Exception as error:
            intentos = self.base._uno('SELECT intentos FROM sidp.trabajo WHERE id = %s', (trabajo_id,))
            estado = 'error' if intentos >= INTENTOS else 'pendiente'
            self.base._consulta('UPDATE sidp.trabajo SET estado = %s, problema = %s WHERE id = %s',
                                (estado, f'{type(error).__name__}: {error}'[:500], trabajo_id))
            print(f'trabajo {trabajo_id}: {type(error).__name__}: {error}', flush=True)
            return {'error': str(error)}
        finally:
            self.ahora = None

    def trabajar(self):
        while True:
            try:
                hecho = self.una_vez()
            except Exception as error:  # La base se cayó: se espera y se sigue.
                print(f'taller: {type(error).__name__}: {error}', flush=True)
                hecho = None
            if hecho is None:
                self.despierta.wait(30)
                self.despierta.clear()

    # ------------------------------------------------------------ Lo que ve el panel

    def estado(self):
        filas = self.base._consulta('SELECT estado, count(*) FROM sidp.trabajo GROUP BY estado')
        resumen = self.base._consulta("SELECT resumen FROM sidp.trabajo WHERE estado = 'hecho' AND resumen IS NOT NULL")
        esperados = sum((r[0] or {}).get('esperados', 0) for r in resumen)
        utiles = sum((r[0] or {}).get('alta', 0) + (r[0] or {}).get('media', 0) for r in resumen)
        return {'trabajos': {e: n for e, n in filas}, 'trabajando': self.ahora, 'modelo_vision': vision.elegir(self.url) if self.con_vision else None,
                'campos_esperados': esperados, 'campos_utiles': utiles, 'porcentaje_util': round(100 * utiles / esperados) if esperados else None,
                'por_confirmar': self.base._uno("SELECT count(*) FROM sidp.dato WHERE estado = 'por_confirmar'")}


def arrancar(base, **opciones):
    taller = Taller(base, **opciones)
    threading.Thread(target=taller.trabajar, daemon=True).start()
    return taller


def esperar(taller, segundos=60):
    """Para las pruebas: trabaja hasta que no quede nada (o se acabe el tiempo)."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite and taller.una_vez() is not None:
        pass
