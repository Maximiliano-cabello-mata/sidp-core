"""Análisis de datos de la escuela con pandas, en la PC 4, sobre su base PostgreSQL.

Qué calcula (todo en números, sin nombres ni CURP, para que se pueda mostrar en el panel y copiar a un informe):
- Matrícula por grado y sexo, y por grado y edad al 31 de diciembre (base del 911).
- Extraedad y menor edad por grado.
- Avance del expediente por grupo: qué parte de los documentos obligatorios ya validó una persona.
- Documentos por tipo y estado, y lo recibido en los últimos 14 días.
- Calidad de lectura del cerebro: cuántas páginas se leyeron, por qué método, y cuántas no.
- Alertas por tipo e inventario por categoría y estado.
- Hallazgos: frases cortas que salen de reglas fijas (el grupo más atrasado, el documento que más falta...).

La IA (Ollama, en la misma PC 4) solo redacta un párrafo con esos números y hallazgos cuando se le pide. Nunca recibe
nombres ni CURP, nunca cambia un dato y su texto se muestra marcado como de la IA.

Librerías: pandas (tablas, cruces y agrupaciones) y numpy (que pandas ya trae). Nada más.
"""
import datetime
import json
import time
import urllib.request

from validacion import modelo

MODELO_REDACTOR = 'llama3.1:latest'  # El modelo base: sidp-revisor-2 está entrenado para contestar si, no o duda.


def _tabla(base, sql, columnas, parametros=()):
    import pandas as pd
    return pd.DataFrame(base._consulta(sql, parametros), columns=columnas)


def _cruce(df, filas, columnas, nombre_total='Total'):
    """Tabla de conteos con totales, lista para el panel: {columnas, filas: [[etiqueta, n, n, ..., total]]}."""
    import pandas as pd
    if df.empty:
        return {'columnas': [], 'filas': []}
    tabla = pd.crosstab(df[filas], df[columnas], margins=True, margins_name=nombre_total)
    return {'columnas': [str(c) for c in tabla.columns],
            'filas': [[str(i)] + [int(v) for v in fila] for i, fila in zip(tabla.index, tabla.to_numpy())]}


def analizar(base, hoy=None):
    """Todo el análisis de la base del cerebro como un diccionario de números y textos cortos."""
    import pandas as pd
    hoy = hoy or datetime.date.today()
    ciclo = base._uno('SELECT max(ciclo) FROM sidp.v_inscritos')
    alumnos = _tabla(base, 'SELECT id, grado, letra, sexo, edad_31_dic, grado_esperado, curp IS NOT NULL, curp_digito_ok, curp_renapo '
                           'FROM sidp.v_inscritos WHERE ciclo = %s',
                     ['id', 'grado', 'letra', 'sexo', 'edad', 'grado_esperado', 'tiene_curp', 'curp_ok', 'renapo'], (ciclo,))
    obligatorios = _tabla(base, 'SELECT clave, nombre, desde_grado FROM sidp.tipo_documento WHERE obligatorio', ['tipo', 'nombre', 'desde_grado'])
    documentos = _tabla(base, "SELECT d.alumno_id, d.tipo, d.estado, d.origen, d.recibido::date FROM sidp.documento d "
                              "WHERE d.estado <> 'reemplazado'", ['alumno_id', 'tipo', 'estado', 'origen', 'recibido'])
    lecturas = _tabla(base, 'SELECT metodo, caracteres, distancia, parecido, alumno_id IS NOT NULL FROM sidp.lectura',
                      ['metodo', 'caracteres', 'distancia', 'parecido', 'reconocida'])
    alertas = _tabla(base, 'SELECT tipo, gravedad FROM sidp.v_alertas', ['tipo', 'gravedad'])
    inventario = _tabla(base, 'SELECT categoria_nombre, estado FROM sidp.v_inventario', ['categoria', 'estado'])

    resultado = {'ciclo': ciclo, 'fecha': hoy.isoformat(), 'motor': 'pandas ' + pd.__version__}
    if not alumnos.empty:
        alumnos['grupo'] = alumnos['grado'].astype(int).astype(str) + '° ' + alumnos['letra']
        alumnos['sexo'] = alumnos['sexo'].fillna('?').map({'H': 'Hombres', 'M': 'Mujeres'}).fillna('Sin dato')
        alumnos['situacion'] = 'En su edad'
        alumnos.loc[alumnos['grado_esperado'] - alumnos['grado'] >= 2, 'situacion'] = 'Extraedad'
        alumnos.loc[alumnos['grado_esperado'] < alumnos['grado'], 'situacion'] = 'Menor edad'

    # Avance del expediente: documentos obligatorios validados entre los que le tocan a cada alumno.
    validados = documentos[documentos['estado'] == 'validado'][['alumno_id', 'tipo']].drop_duplicates()
    avance = pd.DataFrame(columns=['grupo', 'pedidos', 'validados'])
    faltan_por_tipo = pd.Series(dtype=int)
    if not alumnos.empty and not obligatorios.empty:
        pedidos = alumnos[['id', 'grupo', 'grado']].merge(obligatorios, how='cross')
        pedidos = pedidos[pedidos['desde_grado'] <= pedidos['grado']]
        pedidos = pedidos.merge(validados.rename(columns={'alumno_id': 'id'}).assign(validado=True), on=['id', 'tipo'], how='left')
        pedidos['validado'] = pedidos['validado'].fillna(False).astype(bool)
        avance = pedidos.groupby('grupo').agg(pedidos=('validado', 'size'), validados=('validado', 'sum')).reset_index()
        faltan_por_tipo = pedidos[~pedidos['validado']].groupby('nombre').size().sort_values(ascending=False)
        completos = pedidos.groupby('id')['validado'].all()
    else:
        completos = pd.Series(dtype=bool)

    total = len(alumnos)
    resultado['kpis'] = {
        'alumnos': total,
        'hombres': int((alumnos['sexo'] == 'Hombres').sum()) if total else 0,
        'mujeres': int((alumnos['sexo'] == 'Mujeres').sum()) if total else 0,
        'grupos': int(alumnos['grupo'].nunique()) if total else 0,
        'expedientes_completos': int(completos.sum()),
        'avance_expedientes': round(100 * float(avance['validados'].sum()) / float(avance['pedidos'].sum()), 1) if len(avance) else 0.0,
        'documentos': len(documentos),
        'documentos_validados': int((documentos['estado'] == 'validado').sum()),
        'alertas_altas': int((alertas['gravedad'] == 'alta').sum()),
        'curp_validadas_renapo': int((alumnos['renapo'] == 'validada').sum()) if total else 0,
        'piezas_inventario': len(inventario),
    }
    resultado['matricula'] = _cruce(alumnos, 'grupo', 'sexo')
    resultado['edades'] = _cruce(alumnos, 'grupo', 'edad')
    resultado['situacion_edad'] = _cruce(alumnos, 'grupo', 'situacion')
    resultado['avance_por_grupo'] = [{'grupo': g, 'pedidos': int(p), 'validados': int(v), 'porcentaje': round(100 * v / p, 1) if p else 0.0}
                                     for g, p, v in avance[['grupo', 'pedidos', 'validados']].itertuples(index=False)]
    resultado['faltan_por_documento'] = [{'documento': d, 'faltan': int(n)} for d, n in faltan_por_tipo.items()]
    resultado['documentos_por_estado'] = _cruce(documentos.merge(obligatorios[['tipo', 'nombre']], on='tipo', how='left')
                                                .assign(nombre=lambda d: d['nombre'].fillna(d['tipo'])), 'nombre', 'estado')
    hace_14 = pd.Timestamp(hoy - datetime.timedelta(days=13))
    dias = pd.date_range(hace_14, pd.Timestamp(hoy), freq='D')
    recibidos = pd.to_datetime(documentos['recibido']).value_counts() if len(documentos) else pd.Series(dtype=int)
    resultado['recibidos_14_dias'] = [{'dia': d.date().isoformat(), 'documentos': int(recibidos.get(d, 0))} for d in dias]
    resultado['lecturas'] = {
        'paginas': len(lecturas),
        'sin_texto': int((lecturas['caracteres'].fillna(0) == 0).sum()),
        'reconocidas': int(lecturas['reconocida'].sum()) if len(lecturas) else 0,
        'por_metodo': {str(k): int(v) for k, v in lecturas['metodo'].fillna('sin dato').value_counts().items()},
        'curp_con_errores': int((lecturas['distancia'].fillna(0) > 0).sum()),
    }
    resultado['alertas'] = {str(k): int(v) for k, v in alertas['tipo'].value_counts().items()}
    resultado['inventario'] = _cruce(inventario, 'categoria', 'estado')
    resultado['hallazgos'] = hallazgos(resultado)
    return resultado


def hallazgos(r):
    """Frases cortas con reglas fijas: lo que una directora querría ver primero."""
    frases = []
    k = r['kpis']
    if not k['alumnos']:
        return ['Todavía no hay alumnos en la base de la PC 4.']
    frases.append(f'Hay {k["alumnos"]} alumnos en {k["grupos"]} grupos: {k["hombres"]} hombres y {k["mujeres"]} mujeres.')
    frases.append(f'Expedientes: {k["avance_expedientes"]}% de los documentos obligatorios ya están validados; '
                  f'{k["expedientes_completos"]} expedientes completos.')
    avance = sorted(r['avance_por_grupo'], key=lambda g: g['porcentaje'])
    if len(avance) > 1 and avance[0]['porcentaje'] < avance[-1]['porcentaje']:
        frases.append(f'El grupo más atrasado es {avance[0]["grupo"]} ({avance[0]["porcentaje"]}%) y el más avanzado '
                      f'{avance[-1]["grupo"]} ({avance[-1]["porcentaje"]}%).')
    if r['faltan_por_documento']:
        primero = r['faltan_por_documento'][0]
        frases.append(f'El documento que más falta es: {primero["documento"]} ({primero["faltan"]} alumnos).')
    situacion = {f[0]: dict(zip(r['situacion_edad']['columnas'], f[1:])) for f in r['situacion_edad']['filas']}
    extra = situacion.get('Total', {}).get('Extraedad', 0)
    if extra:
        grupos = [g for g, c in situacion.items() if g != 'Total' and c.get('Extraedad')]
        frases.append(f'{extra} alumno(s) con extraedad (2 años o más arriba de la edad del grado), en {", ".join(grupos)}.')
    if r['alertas'].get('curp_digito'):
        frases.append(f'{r["alertas"]["curp_digito"]} CURP no cuadra(n) su dígito verificador: hay que confirmarla(s) con el acta.')
    pendientes = r['alertas'].get('renapo_pendiente', 0)
    if pendientes:
        frases.append(f'{pendientes} CURP faltan por validar en RENAPO.')
    if r['lecturas']['paginas']:
        frases.append(f'El cerebro ha leído {r["lecturas"]["paginas"]} páginas; {r["lecturas"]["sin_texto"]} no se pudieron leer.')
    if k['piezas_inventario']:
        frases.append(f'El inventario tiene {k["piezas_inventario"]} piezas registradas.')
    return frases


def redactar(resultado, url=modelo.URL, nombre_modelo=MODELO_REDACTOR, espera=180):
    """Un párrafo de la IA con los números (sin nombres). Si Ollama no responde, None: el análisis sirve igual."""
    numeros = {k: resultado[k] for k in ('ciclo', 'kpis', 'avance_por_grupo', 'faltan_por_documento', 'alertas', 'hallazgos')}
    pedido = ('Eres asistente de la dirección de una escuela primaria en México. Con estos datos (solo números, sin nombres), '
              'escribe en español un resumen de 4 a 6 frases para la directora: qué va bien, qué urge y qué hacer primero. '
              'No inventes datos que no estén aquí.\n' + json.dumps(numeros, ensure_ascii=False))
    cuerpo = json.dumps({'model': nombre_modelo, 'stream': False, 'options': {'temperature': 0.2},
                         'messages': [{'role': 'user', 'content': pedido}]}).encode()
    inicio = time.monotonic()
    try:
        solicitud = urllib.request.Request(url, cuerpo, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(solicitud, timeout=espera) as respuesta:
            texto = json.load(respuesta)['message']['content'].strip()
    except Exception as error:
        return {'texto': None, 'problema': f'la IA no respondió ({type(error).__name__})'}
    return {'texto': texto, 'modelo': nombre_modelo, 'segundos': round(time.monotonic() - inicio, 1)}
