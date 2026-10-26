"""El taller de la PC 4: saca los datos de los expedientes escaneados, uno por uno y sin prisa.

El servidor guarda los PDF al momento y le encarga a la PC 4 sacar sus datos (POST /trabajo). La PC 4 los
trabaja en fila, en segundo plano, aunque tarde (el modelo que ve tarda de 30 segundos a 2 minutos por hoja):

1. Procesos fijos: texto del PDF u OCR, QR, CURP con dígito verificador, fechas, la franja de la INE.
2. Lectura completa: el modelo que ve transcribe cada hoja entera (frente y vuelta, cada una aparte) y purificar.py
   saca de ahí lo que sirve: teléfonos y correos con de quién son, el contacto de emergencia y la salud del alumno.
3. El modelo lee además la hoja dos veces con la lista de campos de su plantilla (en orden normal e inverso).
4. Las reglas de campos.py limpian cada valor; lo que coincide entre lecturas sube de confianza. Cada enfermedad,
   alergia o condición encontrada se revisa una vez más, sola; las graves siempre las confirma una persona.
5. Todo va a sidp.dato. Lo dudoso queda "por confirmar" y una persona lo ve en el panel con la hoja al lado.

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
from validacion import comparador, estandar, extraer, indicadores, lector, modelo, purificar, vision

MAXIMO_HOJAS = 3  # Por documento, al modelo que ve (las demás hojas casi nunca traen datos nuevos).
MAXIMO_HOJAS_COMPLETAS = 4  # Hojas de un documento que se transcriben completas (dos hojas con frente y vuelta).
SIN_CONTACTOS = campos_mod.SIN_CONTACTOS
INTENTOS = 3
# Con 2 lecturas compara orden normal e inverso: en la Tarea 021 (12 hojas inventadas, letra clara y fea) dio 86 % bien
# contra 80 % con una sola, y ningún dato mal marcado como seguro.
LECTURAS = int(os.environ.get('SIDP_LECTURAS_VISION') or 2)
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


# Documentos que traen uno por hoja: cada hoja de la boleta es de un año distinto y se lee aparte.
POR_HOJA = ('boleta',)
GRADOS = {'PRIMER': 1, 'PRIMERO': 1, 'SEGUNDO': 2, 'TERCER': 3, 'TERCERO': 3, 'CUARTO': 4, 'QUINTO': 5, 'SEXTO': 6}


def separar_hojas(carpeta, documentos):
    """Las boletas que llegan juntas en un PDF (una hoja por año) quedan como un documento por hoja."""
    salida = []
    for documento in documentos:
        archivo = Path(carpeta) / documento['archivo']
        if documento['tipo'] not in POR_HOJA or archivo.suffix.lower() != '.pdf' or not archivo.exists():
            salida.append(documento)
            continue
        try:
            import pypdf
            lector_pdf = pypdf.PdfReader(str(archivo))
            if len(lector_pdf.pages) < 2:
                salida.append(documento)
                continue
            for numero, pagina in enumerate(lector_pdf.pages, 1):
                escritor = pypdf.PdfWriter()
                escritor.add_page(pagina)
                nombre = f'{archivo.stem}_hoja{numero}.pdf'
                with open(Path(carpeta) / nombre, 'wb') as salida_pdf:
                    escritor.write(salida_pdf)
                salida.append({**documento, 'archivo': nombre, 'hoja': numero})
        except Exception as error:  # Un PDF que no se deja partir se lee entero, como antes.
            print(f'no se pudo separar {archivo.name}: {type(error).__name__}: {error}', flush=True)
            salida.append(documento)
    return salida


def grado_de(grado_escrito, ciclo_boleta, actual=None):
    """El grado (1 a 6) de una boleta: el que dice ("SEGUNDO GRADO", "2°") o, si no se leyó, el que sale de su ciclo
    contra el grado y ciclo que cursa ahora (una boleta de 2023-2024 de un alumno que en 2026-2027 va en 4.° es de 1.°)."""
    texto = campos_mod._mayus(grado_escrito)
    for palabra in re.findall(r'[A-Z]+|\d+', texto):
        if palabra in GRADOS:
            return GRADOS[palabra]
        if palabra.isdigit() and 1 <= int(palabra) <= 6:
            return int(palabra)
    hallado = re.search(r'(20\d\d)\s*[-–/]\s*(?:20)?\d\d', str(ciclo_boleta or ''))
    if hallado and actual and actual[0] and actual[1]:
        grado = int(actual[0]) - (int(str(actual[1])[:4]) - int(hallado[1]))
        return grado if 1 <= grado <= 6 else None
    return None


def por_grado(resultado, actual=None):
    """Los datos de una boleta con su grado al final del campo (promedio -> promedio_2), para que las boletas de cada
    año no se reemplacen entre sí. Sin grado, se dejan como están y por confirmar."""
    valores = {r['clave']: r.get('valor') for r in resultado}
    grado = grado_de(valores.get('grado_cursado'), valores.get('ciclo_boleta'), actual)
    salida = []
    for r in resultado:
        if r['clave'] == 'grado_cursado':
            continue  # Va en el nombre de cada campo.
        if r['campo'] in campos_mod.BOLETA:
            r = {**r, 'detalle': {**(r.get('detalle') or {}), 'grado': grado}, 'varios': r['campo'] in campos_mod.VARIOS}
            if grado:
                r['campo'] = f'{r["campo"]}_{grado}'
            else:
                r['confianza'] = 'baja'
        salida.append(r)
    return salida, grado


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
    if tipo == 'ine_tutor':  # La INE impresa: el domicilio va abajo de "DOMICILIO".
        renglones = [r.strip() for r in str(texto or '').upper().splitlines() if r.strip()]
        for i, renglon in enumerate(renglones):
            if renglon == 'DOMICILIO' and i + 1 < len(renglones):
                siguientes = [r for r in renglones[i + 1:i + 4] if not re.match(r'CLAVE|CURP|FECHA|SECCI|VIGENCIA|A[ÑN]O', r)]
                salida['domicilio_ine'] = (' '.join(siguientes[:2]), metodo)
    return {k: v for k, v in salida.items() if v[0]}


def coinciden(tipo, uno, otro, hoy=None, campo=None):
    if tipo == 'lista':
        return set(campos_mod.lista(uno)) == set(campos_mod.lista(otro))
    if campos_mod.vacio(uno) or campos_mod.vacio(otro):
        return campos_mod.vacio(uno) == campos_mod.vacio(otro)
    a, b = campos_mod.limpiar(tipo, uno, hoy, campo)[0] or uno, campos_mod.limpiar(tipo, otro, hoy, campo)[0] or otro
    return comparador.normalizar(str(a)) == comparador.normalizar(str(b)) or indicadores.misma_clase(campo, a, b)


def necesita_ver(lista, procesos):
    """False si los procesos fijos ya sacaron todos los campos de texto impreso o QR (sin OCR): ahí el modelo que ve
    solo gastaría minutos. Las hojas a mano, escaneadas o con campos que faltan sí pasan por él."""
    return any(procesos.get(c['clave'], (None, 'ocr'))[1] in ('ocr', 'lectura') for c in lista)


def _lectura(v):
    """La lectura cruda como texto, con "?" al final si el modelo dudó (así la cuenta cada lista y cada contacto)."""
    if isinstance(v, dict):
        valor = str(v.get('valor') or '').strip()
        return valor + ('?' if valor and v.get('seguro') is False and not valor.endswith('?') else '')
    return str(v or '').strip()


def ver(hojas, nombre_documento, lista, modelo_vision, url=modelo.URL, lecturas=None, hoy=None):
    """Lo que lee el modelo que ve: ({clave: {valor, seguro, lecturas}}, segundos). Con dos lecturas, lo que no coincide
    no es seguro. lecturas: lo que dijo cada una, tal cual (con "?" si dudó)."""
    cuantas = lecturas or LECTURAS
    cruda, segundos = vision.preguntar(hojas, campos_mod.pregunta(nombre_documento, lista), campos_mod.esquema(lista), modelo_vision, url)
    if not cruda:
        return cruda, segundos
    primera = {c['clave']: {**_visto(cruda.get(c['clave']), c['tipo'], cuantas), 'lecturas': [_lectura(cruda.get(c['clave']))]}
               for c in lista if c['clave'] in cruda}
    if cuantas < 2:
        return primera, segundos
    al_reves = list(reversed(lista))
    segunda, mas = vision.preguntar(hojas, campos_mod.pregunta(nombre_documento, al_reves), campos_mod.esquema(al_reves), modelo_vision, url)
    for c in lista:
        a, b = _visto(cruda.get(c['clave']), c['tipo'], 2), _visto((segunda or {}).get(c['clave']), c['tipo'], 2)
        crudas = [_lectura(cruda.get(c['clave'])), _lectura((segunda or {}).get(c['clave']))]
        uno, otro = str(a.get('valor') or '').strip(), str(b.get('valor') or '').strip()
        if not uno and not otro:
            continue
        if not coinciden(c['tipo'], uno, otro, hoy, c['campo']):
            primera[c['clave']] = {'valor': uno or otro, 'seguro': False, 'otra': otro if uno else '', 'lecturas': crudas}
        else:
            primera[c['clave']] = {'valor': uno, 'seguro': bool(a.get('seguro')) and bool(b.get('seguro')), 'lecturas': crudas}
    return primera, segundos + mas


def _de_acuerdo(c, metodo):
    """La confianza cuando el proceso y el modelo que ve dicen lo mismo. La lectura completa también es del modelo que ve:
    si se equivoca, se equivoca igual en las dos (Tarea 023: una CURP escrita a mano salió mal y marcada segura). Una CURP
    que solo leyó el modelo la confirma una persona, o la lista oficial, o RENAPO."""
    if metodo != 'lectura':
        return 'alta'
    return 'baja' if c['tipo'] == 'curp' else 'media'


def _dicen_lo_mismo(c, uno, otro):
    """Un dato de salud escrito con otras palabras en dos lecturas: "20/20 AMBOS OJOS" y "20/20" son vista normal; dos
    recomendaciones casi iguales son la misma."""
    if c['categoria'] != 'salud' or c['tipo'] != 'texto':
        return False
    return indicadores.misma_clase(c['campo'], uno, otro) or purificar.parecido(uno, otro)


def combinar(campos, procesos, vistos, identidad, hoy):
    """Un valor por campo con su confianza. vistos: lo que leyó el modelo {clave: {valor, seguro}}."""
    salida = []
    for c in campos:
        de_proceso, metodo = procesos.get(c['clave'], (None, None))
        visto = _visto((vistos or {}).get(c['clave']), c['tipo']) if vistos and c['clave'] in vistos else {}
        crudo_visto = str(visto.get('valor') or '').strip()
        limpio_p, detalle_p = campos_mod.limpiar(c['tipo'], de_proceso, hoy, c['campo']) if de_proceso else (None, {})
        limpio_v, detalle_v = (campos_mod.limpiar(c['tipo'], crudo_visto, hoy, c['campo']) if crudo_visto and not campos_mod.vacio(crudo_visto)
                               else (None, {}))
        if c['tipo'] == 'lista':
            salida += _lista(c, de_proceso, metodo, visto)
            continue
        if limpio_p and limpio_v:
            iguales = comparador.normalizar(str(limpio_p)) == comparador.normalizar(str(limpio_v)) or _dicen_lo_mismo(c, limpio_p, limpio_v)
            valor, detalle = (limpio_p, detalle_p)
            confianza, metodo = (_de_acuerdo(c, metodo), f'{metodo}+vision') if iguales else ('baja', metodo)
            if not iguales and metodo in ('ocr', 'lectura'):  # En una foto, el modelo que ve suele leer mejor que el OCR: se propone lo suyo.
                valor, detalle, metodo = limpio_v, {**detalle_v, 'otra_lectura': limpio_p}, 'vision'
            elif not iguales:
                detalle = {**detalle, 'otra_lectura': limpio_v}
        elif limpio_p:
            valor, detalle = limpio_p, detalle_p
            # El OCR de una foto confunde 5 con 3 o 7 con 1, y una sola lectura del modelo también se equivoca: solo, queda por
            # confirmar (la CURP se salva con su dígito).
            confianza = 'alta' if (c['tipo'] == 'curp' and metodo != 'lectura') or metodo == 'qr' else 'baja' if metodo in ('ocr', 'lectura') else 'media'
        elif limpio_v:
            valor, detalle, metodo = limpio_v, detalle_v, 'vision'
            confianza = 'media' if visto.get('seguro') and c['tipo'] != 'curp' else 'baja'
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
        if c['categoria'] == 'salud' and purificar.es_grave(valor):  # "Conclusión: asma" en un texto libre: la confirma una persona.
            confianza, detalle = 'baja', {**detalle, 'grave': True}
        valores = campos_mod.lista(valor) if c['tipo'] == 'lista' else [valor]
        salida.append({**c, 'valores': valores, 'valor': valor, 'detalle': {**detalle, **({'de': c['de']} if c.get('de') else {})},
                       'confianza': confianza, 'metodo': metodo})
    return de_la_curp(campos, salida)


def de_la_curp(campos, salida):
    """La fecha de nacimiento sale de la CURP de la misma persona: si no se leyó, se propone; si se leyó otra, se avisa."""
    for c in campos:
        if c['tipo'] != 'fecha' or c['campo'] != 'fecha_nacimiento':
            continue
        curp = next((r for r in salida if r['tipo'] == 'curp' and r['categoria'] == c['categoria'] and r.get('valor')), None)
        desglose = comparador.desglose_curp(str(curp['valor'])) if curp else None
        if not desglose:
            continue
        de_curp = desglose['fecha']
        leido = next((r for r in salida if r['clave'] == c['clave']), None)
        if leido is None:
            segura = curp['confianza'] in ('alta', 'confirmado') and desglose['digito_valido']
            salida.append({**c, 'valores': [de_curp], 'valor': de_curp, 'detalle': {'de_la_curp': curp['valor']},
                           'confianza': 'media' if segura else 'baja', 'metodo': 'curp'})
        elif leido.get('confirma_lista'):
            continue
        elif str(leido.get('valor')) != de_curp:
            leido.update(confianza='baja', detalle={**(leido.get('detalle') or {}), 'otra_lectura': de_curp, 'segun_curp': True})
        elif leido['confianza'] == 'baja':
            leido['confianza'] = 'media'
    return salida


def _lista(c, de_proceso, metodo, visto):
    """Una lista (alergias, padecimientos...): un resultado por valor, con cuántas lecturas lo vieron.

    Las lecturas son lo que sacó la lectura completa o el texto de la hoja (de_proceso) y cada lectura del modelo con
    la lista de campos. Un valor que vio una sola lectura, o que otra lectura dice que no hay, queda por confirmar; las
    enfermedades graves siempre. "Ninguna" también se guarda, para que se vea que el certificado sí se leyó.
    """
    fuentes = [(metodo, str(de_proceso))] if de_proceso is not None else []
    for crudo in (visto.get('lecturas') or [_lectura(visto)]) if visto else []:
        if str(crudo or '').strip():
            fuentes.append(('vision', str(crudo)))
    grupos, nada, nada_dudoso = [], 0, False
    for numero, (metodo_fuente, crudo) in enumerate(fuentes):
        dudoso = crudo.strip().endswith('?')  # El modelo dudó: lo propone, pero no cuenta como lectura que coincide.
        texto = crudo.strip().rstrip('?').strip()
        valores = [v for v in campos_mod.lista(texto) if not purificar.es_ninguno(v)]
        if not valores:
            if purificar.es_ninguno(texto) or campos_mod.vacio(texto):
                nada += not dudoso
                nada_dudoso = nada_dudoso or dudoso
            continue
        for valor in valores:
            grupo = next((g for g in grupos if purificar.parecido(g['valor'], valor)), None)
            if grupo is None:
                grupo = {'valor': valor, 'fuentes': set(), 'metodos': set(), 'de': metodo_fuente}
                grupos.append(grupo)
            elif grupo['de'] == 'ocr' and metodo_fuente != 'ocr' and not dudoso:
                grupo['valor'], grupo['de'] = valor, metodo_fuente  # "RI N ITIS" del OCR y "RINITIS" del modelo: se guarda lo del modelo.
            grupo['metodos'].add(metodo_fuente)
            if not dudoso:
                grupo['fuentes'].add(numero)
    de = {'de': c['de']} if c.get('de') else {}
    if not grupos:
        return [{**c, 'valores': [], 'valor': 'NINGUNA', 'confianza': 'media' if nada >= 2 else 'baja', 'nada': True,
                 'metodo': '+'.join(sorted({m for m, _ in fuentes})), 'detalle': {'nada': True, 'lecturas': nada, **de}}] if nada or nada_dudoso else []
    salida = []
    for grupo in grupos:
        vieron = len(grupo['fuentes'])
        detalle = {'lecturas': vieron, 'de_lecturas': len(fuentes), **de}
        confianza = 'media' if vieron >= 2 and not nada else 'baja'
        if nada:
            detalle['otra_lectura'] = 'NINGUNA'
        if c['categoria'] == 'salud' and purificar.es_grave(grupo['valor']):
            confianza, detalle['grave'] = 'baja', True  # Hipertensión, epilepsia, una enfermedad mental: la confirma una persona.
        salida.append({**c, 'valores': [grupo['valor']], 'valor': grupo['valor'], 'confianza': confianza, 'detalle': detalle,
                       'metodo': '+'.join(sorted(grupo['metodos'])), 'metodos': sorted(grupo['metodos'])})
    return salida


def revisar_salud(resultado, hojas, modelo_vision, url, cuenta):
    """Cada alergia, padecimiento, medicamento o condición encontrada se revisa una vez más, sola, con la hoja (el peso,
    la vista o las vacunas no: no son de lo que el modelo confunde con lo de un familiar).

    Si el modelo dice que sí lo tiene el alumno, se queda como estaba. Si dice que no (es de un familiar, es una opción
    impresa sin marcar, está negado), se queda por confirmar cuando una lectura con etiqueta o casilla lo vio, y si no,
    no se guarda: lo había "visto" solo el modelo y al revisarlo no lo sostiene.
    """
    salida = []
    for r in resultado:
        if r['categoria'] != 'salud' or r['tipo'] != 'lista' or r.get('nada') or not r.get('valor'):
            salida.append(r)
            continue
        try:
            visto, segundos = vision.preguntar(hojas, vision.pregunta_verificar(r['valor'], r['etiqueta']), vision.ESQUEMA_VERIFICAR,
                                               modelo_vision, url, largo=200)
            cuenta['segundos_vision'] += segundos
        except vision.ErrorVision as error:
            print(f'revisión de salud: {error}', flush=True)
            salida.append({**r, 'confianza': 'baja', 'detalle': {**r['detalle'], 'revision': 'sin_revisar'}})
            continue
        cuenta['revisados'] += 1
        respuesta = visto.get('respuesta') if visto.get('respuesta') in vision.RESPUESTAS_VERIFICAR else 'no_aparece'
        detalle = {**r['detalle'], 'revision': respuesta, **({'dice': str(visto['dice'])[:120]} if str(visto.get('dice') or '').strip() else {})}
        if respuesta == 'lo_tiene':
            salida.append({**r, 'detalle': detalle})
        elif set(r.get('metodos') or ()) & {'lectura', 'texto', 'ocr'}:
            salida.append({**r, 'confianza': 'baja', 'detalle': detalle})
        else:
            cuenta['descartados'] += 1
    return salida


NIVELES = ('baja', 'media', 'alta')


def _juntar(fuentes, clase, mismo, casi):
    """Los teléfonos o correos de todas las lecturas: cada uno con cuántas lo vieron (peso) y de quién es."""
    grupos = []
    for numero, (metodo, peso, datos) in enumerate(fuentes):
        for dato in datos[clase]:
            grupo = next((g for g in grupos if mismo(g['valor'], dato['valor'])), None)
            if grupo is None:
                grupo = {'valor': dato['valor'], 'peso': 0, 'fuentes': set(), 'metodos': set(), 'de': ''}
                grupos.append(grupo)
            if numero not in grupo['fuentes']:
                grupo['fuentes'].add(numero)
                grupo['metodos'].add(metodo)
                grupo['peso'] += peso
            grupo['de'] = grupo['de'] or dato.get('de', '')  # El de la lectura completa manda: va primero.
    grupos.sort(key=lambda g: -g['peso'])
    quedan = []
    for grupo in grupos:  # Una lectura que cambia un dígito no es otro teléfono: es el mismo leído distinto.
        fuerte = next((q for q in quedan if casi(q['valor'], grupo['valor']) and min(q['peso'], grupo['peso']) == 1), None)
        if fuerte:
            fuerte['otra'] = grupo['valor']
        else:
            quedan.append(grupo)
    return quedan


def _nivel(peso, dudoso=False):
    nivel = 2 if peso >= 3 else 1 if peso == 2 else 0
    return NIVELES[max(0, nivel - 1) if dudoso else nivel]


def contactos_de(transcrito, texto, metodo_texto, vistos):
    """Teléfonos, correos y contacto de emergencia de toda la hoja, aunque su plantilla no tenga esos campos.

    Fuentes: la lectura completa, el texto del PDF o el OCR (el del PDF es exacto: vale por tres) y cada lectura del
    modelo de "¿qué teléfonos hay?". Visto en tres lecturas: seguro; en dos: vigente; en una: por confirmar.
    """
    fuentes = []
    if transcrito.strip():
        fuentes.append(('lectura', 1, purificar.contactos(transcrito)))
    if str(texto or '').strip():
        fuentes.append((metodo_texto, 3 if metodo_texto == 'texto' else 1, purificar.contactos(texto)))
    vistos = vistos or {}
    claves = (('telefonos_en_la_hoja', 'TELEFONOS'), ('correos_en_la_hoja', 'CORREOS'), ('emergencia_en_la_hoja', 'EN CASO DE EMERGENCIA AVISAR A'))
    for numero in range(2):
        partes = []
        for clave, etiqueta in claves:
            visto = vistos.get(clave) or {}
            lecturas = visto.get('lecturas') or [visto.get('valor')]
            if numero < len(lecturas) and str(lecturas[numero] or '').strip() and not campos_mod.vacio(lecturas[numero]):
                partes.append(f'{etiqueta}: {lecturas[numero]}')
        if partes:
            fuentes.append(('vision', 1, purificar.contactos('\n'.join(partes), exigir_etiqueta=False)))
    salida = []
    telefonos = _juntar(fuentes, 'telefonos', lambda a, b: a == b, purificar.un_digito)
    correos = _juntar(fuentes, 'correos', lambda a, b: a == b, lambda a, b: purificar.parecido(a, b, 0.92))
    for clase, grupos, tipo in (('telefono', telefonos, 'telefono'), ('correo', correos, 'correo')):
        for n, g in enumerate(grupos, 1):
            detalle = {'lecturas': len(g['fuentes']), **({'de': g['de']} if g['de'] else {}), **({'otra_lectura': g['otra']} if g.get('otra') else {})}
            salida.append({**campos_mod.campo(f'{clase}_en_la_hoja_{n}', f'{clase.capitalize()} escrito en la hoja', tipo, 'contacto', clase, g['de']),
                           'valores': [g['valor']], 'valor': g['valor'], 'confianza': _nivel(g['peso'], bool(g.get('otra'))), 'detalle': detalle,
                           'metodo': '+'.join(sorted(g['metodos'])), 'varios': True, 'extra': True})
    personas = []
    for numero, (metodo, peso, datos) in enumerate(fuentes):
        for persona in datos['emergencia']:
            grupo = next((g for g in personas if purificar.parecido(g['valor'], persona['nombre'])), None)
            if grupo is None:
                grupo = {'valor': persona['nombre'], 'peso': 0, 'fuentes': set(), 'metodos': set(), 'parentesco': '', 'distintos': set()}
                personas.append(grupo)
            if numero not in grupo['fuentes']:
                grupo['fuentes'].add(numero)
                grupo['metodos'].add(metodo)
                grupo['peso'] += peso
            grupo['distintos'].add(comparador.normalizar(persona['nombre']))
            grupo['parentesco'] = grupo['parentesco'] or persona.get('parentesco', '')
    if personas:
        g = max(personas, key=lambda x: x['peso'])
        otras = sorted(g['distintos'] - {comparador.normalizar(g['valor'])})
        detalle = {'lecturas': len(g['fuentes']), 'de': 'emergencia', **({'parentesco': g['parentesco']} if g['parentesco'] else {}),
                   **({'otra_lectura': otras[0]} if otras else {})}
        salida.append({**campos_mod.campo('emergencia_en_la_hoja', 'Contacto de emergencia', 'nombre', 'contacto', 'nombre_emergencia', 'emergencia'),
                       'valores': [g['valor']], 'valor': g['valor'], 'confianza': _nivel(g['peso'], bool(otras)), 'detalle': detalle,
                       'metodo': '+'.join(sorted(g['metodos'])), 'extra': True})
    return salida


def leer_documento(archivo, documento, identidad, hoy, modelo_vision=None, url=modelo.URL, lecturas=None):
    """Todo lo que sale de un documento, ya purificado: (resultado, cuenta). Lo usan el taller y medir_lectura.

    documento: {tipo, nombre, campos}. La lectura completa va hoja por hoja (un certificado con frente y vuelta son dos
    hojas, uno de una sola cara es una): así se adapta a cuántas caras traiga.
    """
    cuenta = {'segundos_vision': 0.0, 'hojas_completas': 0, 'revisados': 0, 'descartados': 0}
    tipo, lista = documento['tipo'], documento['campos']
    lectura = lector.leer(archivo)
    metodo_texto = 'ocr' if any('ocr' in m for m in lectura['metodo']) else 'texto'
    procesos = de_procesos(tipo, lectura['texto'], lectura['qr'], hoy, metodo_texto)
    for clave, valor in campos_mod.de_texto(lectura['texto'], lista, hoy).items():
        procesos.setdefault(clave, (valor, metodo_texto))
    con_contactos = tipo not in SIN_CONTACTOS
    hojas, transcrito = [], ''
    if modelo_vision and (con_contactos or necesita_ver(lista, procesos)):
        hojas = vision.paginas(archivo.read_bytes(), archivo.name)
        partes = []
        for numero, hoja in enumerate(hojas[:MAXIMO_HOJAS_COMPLETAS], 1):
            try:
                texto, segundos = vision.transcribir(hoja, modelo_vision, url)
            except vision.ErrorVision as error:
                print(f'{archivo.name}: {error}', flush=True)
                break
            cuenta['segundos_vision'] += segundos
            cuenta['hojas_completas'] += 1
            partes.append(f'[Hoja {numero}]\n{texto}')
        transcrito = '\n'.join(partes)
    tipos = {c['clave']: c['tipo'] for c in lista}
    if transcrito:  # Lo transcrito por el modelo lee mejor la letra a mano que el OCR (la CURP del OCR se salva con su dígito).
        for clave, valor in purificar.de_campos(transcrito, lista, hoy).items():
            if clave not in procesos or (procesos[clave][1] == 'ocr' and tipos[clave] != 'curp'):
                procesos[clave] = (valor, 'lectura')
    for clave, valor in purificar.de_campos(lectura['texto'], lista, hoy).items():
        procesos.setdefault(clave, (valor, metodo_texto))
    preguntas = lista + (campos_mod.EN_LA_HOJA if con_contactos else [])
    vistos = None
    if hojas and preguntas and (con_contactos or necesita_ver(lista, procesos)):
        try:
            vistos, segundos = ver(hojas[:MAXIMO_HOJAS], documento['nombre'], preguntas, modelo_vision, url, lecturas, hoy)
            cuenta['segundos_vision'] += segundos
        except vision.ErrorVision as error:
            print(f'{archivo.name}: {error}', flush=True)
    resultado = combinar(lista, procesos, vistos, identidad, hoy)
    if hojas:
        resultado = revisar_salud(resultado, hojas[:MAXIMO_HOJAS], modelo_vision, url, cuenta)
    if con_contactos:
        resultado += contactos_de(transcrito, lectura['texto'], metodo_texto, vistos)
    return resultado, cuenta


def del_estandar(c):
    """Solo se leen los campos del estándar (y el grado de la boleta, que dice a qué año pertenece cada dato)."""
    return c['clave'] == 'grado_cursado' or (c['categoria'] == 'alumno' and c['campo'] in campos_mod.IDENTIDAD) \
        or estandar.permitido(c['categoria'], c['campo'])


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
            lista = campos_mod.revisar_campos(d['campos']) if d.get('campos') else campos_mod.FABRICA.get(d.get('tipo'), [])
            documentos.append({'archivo': Path(d['archivo']).name, 'tipo': d.get('tipo') or 'otro', 'nombre': d.get('nombre') or d.get('tipo'),
                               'campos': [c for c in lista if del_estandar(c)]})
        if not documentos:
            raise ValueError('El trabajo no trae documentos')
        expediente, relectura = str(pedido.get('expediente') or ''), bool(pedido.get('relectura'))
        en_fila = self.base._consulta("SELECT id FROM sidp.trabajo WHERE alumno_id = %s AND expediente = %s AND estado = 'pendiente' "
                                      "ORDER BY id DESC LIMIT 1", (alumno, expediente)) if expediente else []
        if en_fila:  # Ya esperaba en la fila (se pidió leer todo dos veces): se actualiza, no se lee dos veces.
            trabajo = en_fila[0][0]
            self.base._consulta('UPDATE sidp.trabajo SET documentos = CAST(%s AS jsonb), relectura = relectura OR %s WHERE id = %s',
                                (json.dumps(documentos, ensure_ascii=False), relectura, trabajo))
        else:
            trabajo = self.base._uno('INSERT INTO sidp.trabajo (alumno_id, expediente, documentos, relectura) VALUES (%s, %s, CAST(%s AS jsonb), %s) '
                                     'RETURNING id', (alumno, expediente, json.dumps(documentos, ensure_ascii=False), relectura))
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
            "ORDER BY relectura, id LIMIT 1) RETURNING id, alumno_id, documentos, expediente, relectura", (INTENTOS,))  # Lo recién escaneado, antes.
        return fila[0] if fila else None

    def hacer(self, trabajo_id, alumno_id, documentos, expediente=None, relectura=False):
        identidad = _identidad(self.base._consulta(
            'SELECT curp, nombres, primer_apellido, segundo_apellido, fecha_nacimiento, sexo FROM sidp.alumno WHERE id = %s', (alumno_id,))[0])
        hoy = self.hoy or datetime.date.today()
        modelo_vision = vision.elegir(self.url) if self.con_vision else None
        cuenta = {'esperados': 0, 'alta': 0, 'media': 0, 'baja': 0, 'vacios': 0, 'segundos_vision': 0, 'modelo': modelo_vision,
                  'hojas_completas': 0, 'revisados': 0, 'descartados': 0, 'contactos': 0}
        carpeta = self.carpeta / str(trabajo_id)
        documentos = separar_hojas(carpeta, documentos)
        actual = self.base._consulta('SELECT grado, ciclo FROM sidp.v_inscritos WHERE id = %s ORDER BY ciclo DESC LIMIT 1', (alumno_id,))
        actual = actual[0] if actual else None
        guardar = []  # Primero se lee todo; si algo falla a la mitad, no se toca lo que ya había.
        for documento in documentos:
            archivo = carpeta / documento['archivo']
            if not archivo.exists():
                continue
            resultado, parcial = leer_documento(archivo, documento, identidad, hoy, modelo_vision, self.url)
            for clave in ('segundos_vision', 'hojas_completas', 'revisados', 'descartados'):
                cuenta[clave] += parcial[clave]
            if documento['tipo'] in POR_HOJA:
                resultado, grado = por_grado(resultado, actual)
                cuenta.setdefault('boletas', []).append(grado)
            llenos = {r['clave'] for r in resultado}
            cuenta['esperados'] += len(documento['campos'])
            cuenta['vacios'] += len([c for c in documento['campos'] if c['clave'] not in llenos])
            for r in resultado:
                if r.get('extra'):
                    cuenta['contactos'] += 1
                else:
                    cuenta[r['confianza'] if r['confianza'] in cuenta else 'alta'] += 1
                if r.get('confirma_lista') or not del_estandar(r):
                    continue
                guardar += [(documento['nombre'], r, valor) for valor in (r['valores'] or (['NINGUNA'] if r.get('nada') else []))]
        if relectura:  # La auditoría: lo que la máquina leyó antes de este mismo expediente se reemplaza; lo de las personas no.
            cuenta['reemplazados'] = self.base._uno('SELECT sidp.relectura(%s, %s, %s)', (alumno_id, str(expediente or ''), trabajo_id))
        for nombre, r, valor in guardar:
            self.base._uno('SELECT sidp.guardar_dato(%s, %s, %s, %s, CAST(%s AS jsonb), %s, %s, %s, %s, %s, %s)',
                           (alumno_id, r['categoria'], r['campo'], str(valor), json.dumps(r.get('detalle') or {}, ensure_ascii=False),
                            r['confianza'], r['metodo'] or 'vision', nombre, trabajo_id, 'cerebro', r.get('varios', r['campo'] in campos_mod.VARIOS)))
        cuenta['duplicados'] = depurar(self.base, alumno_id)
        # De lo que sí venía en los documentos, cuánto salió seguro (el certificado trae muchos campos posibles; cada uno, solo algunos).
        encontrados = cuenta['alta'] + cuenta['media'] + cuenta['baja']
        cuenta['utiles'] = round(100 * (cuenta['alta'] + cuenta['media']) / encontrados) if encontrados else 0
        self.base._consulta("UPDATE sidp.trabajo SET estado = 'hecho', terminado = now(), resumen = CAST(%s AS jsonb), problema = NULL WHERE id = %s",
                            (json.dumps(cuenta), trabajo_id))
        shutil.rmtree(carpeta, ignore_errors=True)
        return cuenta

    def una_vez(self):
        """Hace el siguiente trabajo. None si no había."""
        siguiente = self.siguiente()
        if not siguiente:
            return None
        trabajo_id, alumno_id, documentos, expediente, relectura = siguiente
        self.ahora = trabajo_id
        try:
            return self.hacer(trabajo_id, alumno_id, documentos, expediente, relectura)
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
        encontrados = sum(sum((r[0] or {}).get(k, 0) for k in ('alta', 'media', 'baja')) for r in resumen)
        utiles = sum((r[0] or {}).get('alta', 0) + (r[0] or {}).get('media', 0) for r in resumen)
        return {'trabajos': {e: n for e, n in filas}, 'trabajando': self.ahora, 'modelo_vision': vision.elegir(self.url) if self.con_vision else None,
                'campos_esperados': esperados, 'campos_utiles': utiles, 'porcentaje_util': round(100 * utiles / encontrados) if encontrados else None,
                'por_confirmar': self.base._uno("SELECT count(*) FROM sidp.dato WHERE estado = 'por_confirmar'")}


def depurar(base, alumno_id=None):
    """Marca como reemplazadas las lecturas repetidas de la máquina (casi iguales a otra más segura). Nada se borra: la
    fila se queda con la marca y el id del dato que se quedó. Sin alumno_id, revisa a todos. Devuelve cuántas marcó."""
    filtro, parametros = ('AND alumno_id = %s', (alumno_id,)) if alumno_id else ('', ())
    filas = base._consulta('SELECT id, alumno_id, categoria, campo, valor, detalle, confianza, estado, quien FROM sidp.dato '
                           f"WHERE estado IN ('vigente', 'por_confirmar') {filtro} ORDER BY alumno_id, id", parametros)
    por_alumno = {}
    for f in filas:
        por_alumno.setdefault(f[1], []).append(dict(zip(('id', 'alumno_id', 'categoria', 'campo', 'valor', 'detalle', 'confianza', 'estado', 'quien'), f)))
    marcados = 0
    for datos in por_alumno.values():
        for sobra, queda in purificar.duplicados(datos):
            marcados += bool(base._uno('SELECT sidp.marcar_duplicado(%s, %s)', (sobra, queda)))
    return marcados


def arrancar(base, **opciones):
    taller = Taller(base, **opciones)
    threading.Thread(target=taller.trabajar, daemon=True).start()
    return taller


def esperar(taller, segundos=60):
    """Para las pruebas: trabaja hasta que no quede nada (o se acabe el tiempo)."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite and taller.una_vez() is not None:
        pass
