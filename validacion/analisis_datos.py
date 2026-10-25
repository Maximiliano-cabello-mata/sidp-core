"""Estudio de los alumnos con pandas, en la PC 4, sobre su base PostgreSQL: salud, dónde viven, boletas y el 911.

Se calcula cada vez que se abre la pestaña (y se refresca solo mientras está abierta), así que crece conforme se
escanea. Lo que cuenta (todo en números, sin nombres ni CURP; cada alumno se cuenta con validacion/indicadores.py):
- Matrícula por grupo y sexo, edades al 1 de septiembre (911) y extraedad.
- Las tablas del 911.3: alumnos por grado, sexo y edad; discapacidad y condiciones por tipo; nacidos en otra entidad
  o en otro país (sale de la CURP).
- Salud mínima (el estándar, validacion/estandar.py): alergias, padecimientos, medicamentos y discapacidad para el 911.
  Peso, talla, vista, dientes, sangre y vacunas ya no se estudian: los resultados de "Vive saludable" son del sector salud.
- Lo que el 911 pide y pone la escuela: repetidores, de dónde vienen, becas, lengua indígena y afromexicanos.
- Dónde viven: municipios, colonias y códigos postales.
- Boletas de años anteriores: promedio por grado cursado, por campo formativo y alumnos con promedio bajo.
- Cuántos alumnos tienen ya cada tipo de dato, para saber si los porcentajes ya valen para toda la escuela.
No cuenta documentos: subirlos es trabajo de todos los días, no algo que estudiar.

La IA (Ollama, en la misma PC 4) escribe el estudio para el director y el subdirector con esos números: sola, cuando
hay datos nuevos y la PC 4 no está leyendo escaneos (Estudio.vigilar), o cuando se le pide en el panel. Nunca recibe
nombres ni CURP, nunca cambia un dato y su texto se muestra marcado como de la IA.
"""
import datetime
import json
import os
import threading
import time
import urllib.request
from pathlib import Path

from validacion import indicadores, modelo

MODELO_REDACTOR = 'llama3.1:latest'  # El modelo base: sidp-revisor-2 está entrenado para contestar si, no o duda.
MAYORIA = 50  # Con datos de más de la mitad de los alumnos, los porcentajes ya hablan de la escuela.


def _cruce(df, filas, columnas, nombre_total='Total', orden=None):
    """Tabla de conteos con totales, lista para el panel: {columnas, filas: [[etiqueta, n, n, ..., total]]}."""
    import pandas as pd
    df = df.dropna(subset=[filas, columnas]) if len(df) else df
    if df.empty:
        return {'columnas': [], 'filas': []}
    tabla = pd.crosstab(df[filas], df[columnas], margins=True, margins_name=nombre_total)
    if orden:
        tabla = tabla[[c for c in orden if c in tabla.columns] + [nombre_total]]
    return {'columnas': [str(c) for c in tabla.columns],
            'filas': [[str(i)] + [int(v) for v in fila] for i, fila in zip(tabla.index, tabla.to_numpy())]}


def _conteo(serie, cuantos=None):
    """[[valor, alumnos], ...] de mayor a menor (una serie de listas se cuenta por elemento)."""
    if serie.empty:
        return []
    serie = serie.explode().dropna()
    conteo = serie.value_counts()
    if cuantos:
        conteo = conteo.head(cuantos)
    return [[str(k), int(v)] for k, v in conteo.items()]


def _por_ciento(parte, todo):
    return round(100 * parte / todo, 1) if todo else 0.0


def alumnos_de(base, ciclo, hoy):
    """Un renglón por alumno inscrito con lo que se cuenta de él (sin nombre ni CURP)."""
    import pandas as pd
    filas = base._consulta('SELECT id, grado, letra, sexo, fecha_nacimiento, curp, grado_esperado FROM sidp.v_inscritos WHERE ciclo = %s',
                           (ciclo,))
    datos = {}
    for alumno_id, categoria, campo, valor, detalle, estado in base._consulta(
            "SELECT d.alumno_id, d.categoria, d.campo, d.valor, d.detalle, d.estado FROM sidp.dato d "
            "JOIN sidp.v_inscritos i ON i.id = d.alumno_id AND i.ciclo = %s WHERE d.estado IN ('vigente', 'por_confirmar') ORDER BY d.id",
            (ciclo,)):
        datos.setdefault(alumno_id, {}).setdefault(categoria, []).append({'campo': campo, 'valor': valor, 'detalle': detalle, 'estado': estado})
    renglones = []
    for alumno_id, grado, letra, sexo, nacimiento, curp, esperado in filas:
        r = indicadores.de_alumno(datos.get(alumno_id), grado, sexo, nacimiento, curp, ciclo, hoy)
        r['grupo'] = f'{int(grado)}° {letra}' if grado else 'Sin grupo'
        r['grado_texto'] = f'{int(grado)}°' if grado else 'Sin grupo'
        r['sexo_texto'] = {'H': 'Hombres', 'M': 'Mujeres'}.get(r['sexo'], 'Sin dato')
        r['situacion'] = ('Sin fecha' if esperado is None or grado is None else 'Extraedad' if esperado - grado >= 2
                          else 'Menor edad' if esperado < grado else 'En su edad')
        renglones.append(r)
    return pd.DataFrame(renglones)


def tabla_911(df):
    """Alumnos por grado, sexo y edad al 1 de septiembre, como el cuestionario 911.3 (con subtotal por grado y total)."""
    columnas = list(indicadores.EDADES_911) + ['Sin fecha', 'Total']
    filas = []
    for grado in range(1, 7):
        del_grado = df[df['grado'] == grado] if len(df) else df
        for sexo, nombre in (('H', 'Hombres'), ('M', 'Mujeres'), (None, 'Subtotal')):
            parte = del_grado if sexo is None else del_grado[del_grado['sexo'] == sexo] if len(del_grado) else del_grado
            cuenta = parte['columna_911'].fillna('Sin fecha').value_counts() if len(parte) else {}
            filas.append([f'{grado}°', nombre] + [int(cuenta.get(c, 0)) for c in columnas[:-1]] + [len(parte)])
    total = [sum(f[i] for f in filas if f[1] == 'Subtotal') for i in range(2, len(columnas) + 2)]
    filas.append(['Total', ''] + total)
    return {'columnas': columnas, 'filas': filas}


def analizar(base, hoy=None):
    """El estudio de los alumnos como un diccionario de números y textos cortos."""
    import pandas as pd
    hoy = hoy or datetime.date.today()
    ciclo = base._uno('SELECT max(ciclo) FROM sidp.v_inscritos')
    df = alumnos_de(base, ciclo, hoy) if ciclo else pd.DataFrame()
    resultado = {'ciclo': ciclo, 'fecha': hoy.isoformat(), 'motor': 'pandas ' + pd.__version__}
    total = len(df)
    vacio = pd.DataFrame(columns=['grado', 'grado_texto', 'grupo', 'sexo', 'sexo_texto'])
    if not total:
        df = vacio
    salud, domicilio, boletas = (df[df[c]] if total else df for c in ('con_salud', 'con_domicilio', 'con_boletas'))
    con_boleta_posible = df[df['grado'] > 1] if total else df  # En 1.° no traen boleta de primaria.
    cobertura = [
        {'area': 'Salud (certificado médico)', 'con': len(salud), 'de': total},
        {'area': 'Domicilio (colonia, municipio o CP)', 'con': len(domicilio), 'de': total},
        {'area': 'Boletas de años anteriores (de 2.° a 6.°)', 'con': len(boletas), 'de': len(con_boleta_posible)},
    ]
    for c in cobertura:
        c['porcentaje'] = _por_ciento(c['con'], c['de'])
        c['suficiente'] = c['porcentaje'] > MAYORIA
    resultado['cobertura'] = cobertura
    resultado['suficiente'] = any(c['suficiente'] for c in cobertura)

    lista = lambda d, c: int(d[c].map(bool).sum()) if len(d) else 0  # noqa: E731 - alumnos con al menos un valor en la lista
    municipios = _conteo(domicilio['municipio'].dropna().map(indicadores.titulo)) if len(domicilio) else []
    con_municipio = sum(n for _, n in municipios)
    ultimos = boletas['ultimo_promedio'].dropna() if len(boletas) else pd.Series(dtype=float)
    resultado['kpis'] = {
        'alumnos': total, 'hombres': int((df['sexo'] == 'H').sum()) if total else 0, 'mujeres': int((df['sexo'] == 'M').sum()) if total else 0,
        'grupos': int(df['grupo'].nunique()) if total else 0,
        'con_salud': len(salud),
        'con_alergias': lista(salud, 'alergias'), 'con_padecimientos': lista(salud, 'padecimientos'),
        'con_medicamento': lista(salud, 'medicamentos'), 'con_discapacidad': lista(df, 'discapacidades'),
        'promedio_general': round(float(ultimos.mean()), 1) if len(ultimos) else None,
        'municipio_principal': municipios[0][0] if municipios else None,
        'por_ciento_municipio': _por_ciento(municipios[0][1], con_municipio) if municipios else 0.0,
    }

    # Matrícula y edades.
    resultado['matricula'] = _cruce(df, 'grupo', 'sexo_texto')
    edades = df.assign(edad=df['columna_911'].fillna('Sin fecha')) if total else df.assign(edad=None)
    resultado['edades'] = _cruce(edades, 'grupo', 'edad', orden=list(indicadores.EDADES_911) + ['Sin fecha'])
    resultado['situacion_edad'] = _cruce(df.assign(situacion=df.get('situacion')), 'grupo', 'situacion',
                                         orden=['En su edad', 'Extraedad', 'Menor edad', 'Sin fecha'])

    # Lo que pide el 911.3.
    resultado['f911'] = tabla_911(df)
    resultado['grupos_por_grado'] = [[f'{g}°', int(n)] for g, n in df.groupby('grado')['grupo'].nunique().items()] if total else []
    tipos = df[['grado_texto', 'sexo_texto', 'discapacidades']].explode('discapacidades').dropna() if total else df
    resultado['discapacidad_911'] = _cruce(tipos.rename(columns={'discapacidades': 'tipo'}), 'tipo', 'grado_texto') if len(tipos) else \
        {'columnas': [], 'filas': []}
    resultado['discapacidad_sexo'] = _cruce(tipos.rename(columns={'discapacidades': 'tipo'}), 'tipo', 'sexo_texto') if len(tipos) else \
        {'columnas': [], 'filas': []}
    resultado['nacidos'] = _cruce(df, 'grado_texto', 'nacido', orden=['Estado de México', 'Otra entidad', 'Otro país'])
    resultado['nacidos_sexo'] = _cruce(df[df['nacido'].isin(['Otra entidad', 'Otro país'])] if total else df, 'nacido', 'sexo_texto')
    resultado['entidades'] = _conteo(df[df['nacido'] == 'Otra entidad']['entidad']) if total else []

    # Salud.
    resultado['salud'] = {
        'alergias': _conteo(salud['alergias'], 10) if len(salud) else [],
        'padecimientos': _conteo(salud['padecimientos'], 10) if len(salud) else [],
        'medicamentos': _conteo(salud['medicamentos'], 10) if len(salud) else [],
    }
    # Lo del 911 que pone la escuela: cuántos ya tienen el dato y cuántos dicen que sí.
    resultado['para_911'] = [{'dato': nombre, 'con': int(df[clave].notna().sum()) if total else 0,
                              'si': int((df[clave] == 'sí').sum()) if total else 0, 'de': total}
                             for clave, nombre in (('repite', 'Repiten el grado'), ('lengua_indigena', 'Hablan una lengua indígena'),
                                                   ('afro', 'Afromexicanos o afrodescendientes'))]
    resultado['becas'] = _conteo(df['beca'].dropna()) if total else []
    resultado['procedencia'] = _conteo(df['procedencia'].dropna()) if total else []

    # Dónde viven.
    resultado['domicilio'] = {
        'municipios': municipios,
        'colonias': _conteo(domicilio['colonia'].dropna().map(indicadores.titulo), 15) if len(domicilio) else [],
        'cps': _conteo(domicilio['cp'], 10) if len(domicilio) else [],
    }

    # Boletas de años anteriores.
    escolar = {'por_grado_cursado': [], 'formativos': [], 'por_grupo': [], 'bajos': 0, 'no_acreditan': 0}
    if len(boletas):
        cursados = boletas['promedios'].map(lambda p: list(p.items())).explode().dropna()
        cursados = pd.DataFrame(cursados.tolist(), columns=['grado', 'promedio'])
        escolar['por_grado_cursado'] = [[f'{int(g)}°', round(float(p), 1), int(n)] for g, p, n in
                                        cursados.groupby('grado')['promedio'].agg(['mean', 'size']).reset_index().itertuples(index=False)]
        formativos = pd.DataFrame(boletas['formativos'].tolist())
        escolar['formativos'] = [[nombre, round(float(formativos[clave].mean()), 1)] for clave, nombre in indicadores.FORMATIVOS
                                 if clave in formativos and formativos[clave].notna().any()]
        con_ultimo = boletas[boletas['ultimo_promedio'].notna()]
        escolar['por_grupo'] = [[g, round(float(p), 1), int(b)] for g, p, b in con_ultimo.groupby('grupo').agg(
            p=('ultimo_promedio', 'mean'), b=('ultimo_promedio', lambda s: int((s < indicadores.PROMEDIO_BAJO).sum()))).itertuples()]
        escolar['bajos'] = int((con_ultimo['ultimo_promedio'] < indicadores.PROMEDIO_BAJO).sum())
        escolar['no_acreditan'] = int((con_ultimo['ultimo_promedio'] < 6).sum())
    resultado['escolar'] = escolar
    resultado['hallazgos'] = hallazgos(resultado)
    return resultado


def _lista_corta(pares, cuantos=3):
    return ', '.join(f'{nombre} ({n})' for nombre, n, *_ in pares[:cuantos])


def hallazgos(r):
    """Frases cortas con reglas fijas: lo que el director y el subdirector querrían ver primero."""
    k = r['kpis']
    if not k['alumnos']:
        return ['Todavía no hay alumnos en la base de la PC 4.']
    frases = [f'Hay {k["alumnos"]} alumnos en {k["grupos"]} grupos: {k["hombres"]} hombres y {k["mujeres"]} mujeres.']
    cobertura = {c['area'].split(' ')[0]: c for c in r['cobertura']}
    frases.append(f'Ya hay datos de salud de {cobertura["Salud"]["con"]} alumnos ({cobertura["Salud"]["porcentaje"]}%), de domicilio de '
                  f'{cobertura["Domicilio"]["con"]} ({cobertura["Domicilio"]["porcentaje"]}%) y boletas de {cobertura["Boletas"]["con"]} '
                  f'({cobertura["Boletas"]["porcentaje"]}% de los de 2.° a 6.°).'
                  + ('' if r['suficiente'] else ' Todavía son pocos: los números de abajo hablan solo de los ya escaneados.'))
    s = r['salud']
    if k['con_alergias']:
        frases.append(f'{k["con_alergias"]} alumno(s) con alguna alergia; las más comunes: {_lista_corta(s["alergias"])}.')
    if k['con_padecimientos'] or k['con_medicamento']:
        frases.append(f'{k["con_padecimientos"]} con alguna enfermedad o padecimiento ({_lista_corta(s["padecimientos"]) or "sin detalle"}) y '
                      f'{k["con_medicamento"]} toman medicamento: que lo sepan sus maestras.')
    if r['discapacidad_911']['filas']:
        tipos = [(f[0], f[-1]) for f in r['discapacidad_911']['filas'] if f[0] != 'Total']
        frases.append(f'{k["con_discapacidad"]} alumno(s) con discapacidad o condición para el 911: {_lista_corta(tipos, 6)}.')
    faltan_911 = [f'{x["de"] - x["con"]} sin el dato de «{x["dato"].lower()}»' for x in r.get('para_911', []) if x['de'] - x['con']]
    if faltan_911:
        frases.append('Para el 911 faltan datos que pone la escuela: ' + ', '.join(faltan_911) + ' (se completan en «Formatos oficiales»).')
    d = r['domicilio']
    if d['municipios']:
        primero, n = d['municipios'][0]
        con_dato = sum(x for _, x in d['municipios'])
        frases.append(f'{"La mayoría vive" if n * 2 > con_dato else "Viven sobre todo"} en {primero} ({n} de {con_dato}, '
                      f'{k["por_ciento_municipio"]}%)' + (f'; siguen {_lista_corta(d["municipios"][1:], 2)}.' if len(d['municipios']) > 1 else '.'))
    if d['colonias']:
        frases.append(f'Colonias con más alumnos: {_lista_corta(d["colonias"])}.')
    nacidos = {f[0]: dict(zip(r['nacidos']['columnas'], f[1:])) for f in r['nacidos']['filas']}.get('Total', {})
    if nacidos.get('Otra entidad') or nacidos.get('Otro país'):
        frases.append(f'{nacidos.get("Otra entidad", 0)} nacieron en otra entidad'
                      + (f' (sobre todo {_lista_corta(r["entidades"], 2)})' if r['entidades'] else '')
                      + f' y {nacidos.get("Otro país", 0)} en otro país (el 911 lo pide).')
    e = r['escolar']
    if k['promedio_general'] is not None:
        frase = f'Promedio de la última boleta: {k["promedio_general"]}; {e["bajos"]} alumno(s) con menos de 7'
        grupos = sorted([g for g in e['por_grupo'] if g[2]], key=lambda g: -g[2])
        frases.append(frase + (f' (más en {grupos[0][0]}: {grupos[0][2]}).' if grupos else '.'))
        if len(e['formativos']) > 1:
            bajo = min(e['formativos'], key=lambda f: f[1])
            frases.append(f'Por campo formativo, el más bajo es {bajo[0]} ({bajo[1]}).')
    situacion = {f[0]: dict(zip(r['situacion_edad']['columnas'], f[1:])) for f in r['situacion_edad']['filas']}
    extra = situacion.get('Total', {}).get('Extraedad', 0)
    if extra:
        grupos = [g for g, c in situacion.items() if g != 'Total' and c.get('Extraedad')]
        frases.append(f'{extra} alumno(s) con extraedad (2 años o más arriba de la edad del grado), en {", ".join(grupos)}.')
    return frases


def _numeros_para_ia(r):
    """Solo los números que la IA necesita (sin nombres): resúmenes cortos, no tablas enteras."""
    s, d, e = r['salud'], r['domicilio'], r['escolar']
    return {
        'ciclo': r['ciclo'], 'alumnos': r['kpis'], 'cuantos_alumnos_tienen_cada_dato': r['cobertura'],
        'alergias_mas_comunes': s['alergias'], 'padecimientos_mas_comunes': s['padecimientos'], 'medicamentos': s['medicamentos'],
        'datos_del_911_que_pone_la_escuela': r.get('para_911'), 'becas': r.get('becas'), 'de_donde_vienen': r.get('procedencia'),
        'discapacidad_911_por_grado': r['discapacidad_911'], 'municipios': d['municipios'][:8], 'colonias': d['colonias'][:10],
        'codigos_postales': d['cps'][:5], 'nacidos_por_grado': r['nacidos'], 'otras_entidades': r['entidades'][:5],
        'promedio_por_grado_cursado': e['por_grado_cursado'], 'promedio_por_campo_formativo': e['formativos'],
        'promedio_por_grupo_y_alumnos_con_menos_de_7': e['por_grupo'], 'alumnos_con_menos_de_7': e['bajos'],
        'alumnos_con_menos_de_6': e['no_acreditan'], 'situacion_de_edad': r['situacion_edad'], 'hallazgos': r['hallazgos'],
    }


PEDIDO = ('Eres asistente de la dirección de una escuela primaria pública del Estado de México. Con estos datos (solo números, '
          'sin nombres) escribe en español un estudio breve para el director y el subdirector, con estos apartados en este orden: '
          '"Salud" (alergias, padecimientos y medicamentos, para que lo sepan las maestras), "Dónde viven" (municipios y '
          'colonias), "Aprovechamiento" (boletas de años anteriores), "Para el 911" (discapacidad, nacidos en otra entidad o país, '
          'extraedad, repetidores, becas, lengua indígena) y "Qué hacer primero" (3 acciones concretas). Cada apartado de 2 a 4 frases. '
          'No hables de peso, talla, vista, dientes, sangre ni vacunas. Di siempre de cuántos alumnos sale '
          'cada número y, si son pocos, dilo. No hables de documentos ni de expedientes. No inventes datos que no estén aquí.\n')


def redactar(resultado, url=modelo.URL, nombre_modelo=MODELO_REDACTOR, espera=600):
    """El estudio de la IA con los números (sin nombres). Si Ollama no responde, un problema: el análisis sirve igual."""
    pedido = PEDIDO + json.dumps(_numeros_para_ia(resultado), ensure_ascii=False)
    cuerpo = json.dumps({'model': nombre_modelo, 'stream': False, 'options': {'temperature': 0.2, 'num_ctx': 8192},
                         'messages': [{'role': 'user', 'content': pedido}]}).encode()
    inicio = time.monotonic()
    try:
        solicitud = urllib.request.Request(url, cuerpo, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
            texto = json.load(respuesta)['message']['content'].strip()
    except Exception as error:
        return {'texto': None, 'problema': f'la IA no respondió ({type(error).__name__})'}
    return {'texto': texto, 'modelo': nombre_modelo, 'segundos': round(time.monotonic() - inicio, 1)}


def archivo_por_omision():
    if os.environ.get('SIDP_ESTUDIO'):
        return Path(os.environ['SIDP_ESTUDIO'])
    return Path('C:/SIDP-datos/estudio_ia.json') if os.name == 'nt' else Path.home() / 'SIDP-datos' / 'estudio_ia.json'


class Estudio:
    """El estudio de la IA que se rehace solo conforme se escanea.

    Cada `cada` segundos ve cuántos datos de alumnos hay. Si llegaron al menos `minimo` nuevos desde el último estudio,
    ya hay datos de la mayoría en alguna área y la PC 4 no está leyendo escaneos (la IA y el modelo que ve no caben
    juntos en el procesador), le pide a la IA un estudio nuevo y lo guarda. El panel muestra el último.
    """

    def __init__(self, base, url=modelo.URL, archivo=None, ocupado=None, cada=600, minimo=20, nombre_modelo=MODELO_REDACTOR):
        self.base, self.url, self.archivo = base, url, Path(archivo or archivo_por_omision())
        self.ocupado, self.cada, self.minimo, self.nombre_modelo = ocupado or (lambda: False), cada, minimo, nombre_modelo
        self.candado = threading.Lock()

    def huella(self):
        return int(self.base._uno('SELECT count(*) FROM sidp.dato') or 0)

    def guardado(self):
        try:
            estudio = json.loads(self.archivo.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        estudio['al_dia'] = self.huella() - estudio.get('huella', 0) < self.minimo
        return estudio

    def toca(self, resultado):
        anterior = self.guardado()
        return resultado['suficiente'] and (anterior is None or not anterior['al_dia'])

    def hacer(self, resultado=None):
        """Pide el estudio a la IA y lo guarda si contestó. Devuelve lo que contestó."""
        with self.candado:
            huella = self.huella()
            resultado = resultado or analizar(self.base)
            ia = redactar(resultado, self.url, self.nombre_modelo)
            if ia.get('texto'):
                guardar = {**ia, 'fecha': datetime.datetime.now().isoformat(timespec='minutes'), 'huella': huella,
                           'alumnos': resultado['kpis']['alumnos'], 'cobertura': resultado['cobertura']}
                self.archivo.parent.mkdir(parents=True, exist_ok=True)
                temporal = self.archivo.with_suffix('.tmp')
                temporal.write_text(json.dumps(guardar, ensure_ascii=False, indent=1), encoding='utf-8')
                os.replace(temporal, self.archivo)
            return ia

    def una_vez(self):
        if self.ocupado():
            return None
        resultado = analizar(self.base)
        return self.hacer(resultado) if self.toca(resultado) else None

    def vigilar(self):
        while True:
            time.sleep(self.cada)
            try:
                self.una_vez()
            except Exception as error:  # Nunca detiene al cerebro.
                print(f'estudio de la IA: {type(error).__name__}: {error}', flush=True)
