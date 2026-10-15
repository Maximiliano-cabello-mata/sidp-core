"""Plantillas de documentos: lo que la escuela espera de cada documento, sin programar.

Un administrativo sube una muestra del documento (por ejemplo, la carta compromiso de la escuela).
El sistema la lee y propone sus "textos fijos": las frases que trae siempre, sin datos de nadie.
La persona los revisa, elige qué más se debe cumplir de una lista fija y guarda. Desde ese momento:

- la página de padres pide ese documento (si se marcó así);
- al escanear, las hojas que dicen esos textos se reconocen como ese documento;
- al revisar un expediente, el documento se valida contra su plantilla.

Las reglas que se pueden elegir son procesos fijos (ver REGLAS). La plantilla nunca ejecuta nada:
solo dice qué textos buscar y cuáles de esas reglas aplicar.

Las plantillas no se sobrescriben: cada cambio es una versión nueva (plantillas/<clave>/v001.json).
Los documentos que ya vienen con el sistema (acta, INE...) también aparecen como plantillas "de
fábrica": se les pueden agregar textos fijos (otra compañía de luz, por ejemplo) o cambiar si son
obligatorios, y conservan sus revisiones propias (CURP del acta, franja de la INE, vigencia).
"""
import datetime
import json
import re
import unicodedata
from pathlib import Path

from validacion import comparador
from validacion.expediente import TIPOS, fechas, mayusculas, parece

REGLAS = {
    'nombre_alumno': 'Dice el nombre del alumno',
    'nombre_tutor': 'Dice el nombre de la madre, padre o tutor',
    'curp_alumno': 'Trae la CURP del alumno',
    'domicilio': 'Dice el domicilio que escribió el tutor',
    'fecha_reciente': 'Tiene una fecha de los últimos meses (vigencia)',
}
DE_QUIEN = {'alumno': 'Del alumno', 'tutor': 'De la madre, padre o tutor'}
FABRICA_DE = {'acta_alumno': 'alumno', 'certificado_medico': 'alumno', 'boleta': 'alumno',
              'ine_tutor': 'tutor', 'acta_tutor': 'tutor', 'comprobante': 'tutor'}
# Para que el administrativo vea qué revisa ya el sistema en los documentos de fábrica.
FABRICA_REVISA = {'acta_alumno': ['nombre_alumno', 'curp_alumno'], 'certificado_medico': ['nombre_alumno'],
                  'boleta': ['nombre_alumno'], 'ine_tutor': ['nombre_tutor'], 'acta_tutor': ['nombre_tutor'],
                  'comprobante': ['domicilio', 'fecha_reciente']}
MAXIMO_TEXTOS = 30
MAXIMO_MUESTRA = 15 * 1024 * 1024


class ErrorPlantilla(Exception):
    """Algo que la persona debe corregir en la plantilla; el mensaje es para ella."""


def _clave(nombre):
    texto = unicodedata.normalize('NFD', nombre.lower())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return 'p_' + '_'.join(re.findall(r'[a-z0-9]+', texto))[:40]


def fabrica():
    """Los documentos que trae el sistema, como plantillas versión 0."""
    return {clave: {'clave': clave, 'nombre': nombre, 'de': FABRICA_DE[clave], 'obligatorio': obligatorio, 'para_padres': True,
                    'textos': list(marcas), 'minimo': 1, 'reglas': FABRICA_REVISA[clave], 'meses': 3 if clave == 'comprobante' else None,
                    'fabrica': True, 'activa': True, 'version': 0}
            for clave, (nombre, obligatorio, marcas) in TIPOS.items()}


def proponer_textos(textos):
    """Frases que podrían ser fijas, a partir del texto de una o varias muestras.

    Con varias muestras, solo las frases que están en todas (lo que cambia son datos de cada quien).
    Con una sola, los renglones de 2 a 8 palabras sin números, sin CURP ni fechas: casi siempre
    son títulos y etiquetas del formato. La persona quita los que no sirvan.
    """
    por_muestra = []
    for texto in textos:
        renglones = []
        for renglon in mayusculas(texto).splitlines():
            renglon = renglon.split(':')[0]  # "Nombre del alumno: LUIS..." -> solo la etiqueta, sin el dato.
            limpio = ' '.join(re.sub(r'[^A-Z0-9 ]+', ' ', renglon).split())
            palabras = limpio.split()
            if not 2 <= len(palabras) <= 8 or re.search(r'\d', limpio) or len(limpio) < 6:
                continue
            if sum(len(p) > 2 for p in palabras) < 2 or limpio in renglones:
                continue
            renglones.append(limpio)
        por_muestra.append(renglones)
    if not por_muestra:
        return []
    comunes = [r for r in por_muestra[0] if all(parece('\n'.join(otra), [r]) for otra in por_muestra[1:])]
    return comunes[:MAXIMO_TEXTOS]


def normalizar(datos, existentes):
    """La plantilla que mandó el panel, revisada y en su forma guardable. existentes: {clave: plantilla}."""
    nombre = ' '.join(str(datos.get('nombre') or '').split())
    clave = str(datos.get('clave') or '') or _clave(nombre)
    anterior = existentes.get(clave)
    if anterior and anterior.get('fabrica'):
        nombre = anterior['nombre']  # Los de fábrica conservan su nombre: así los reconoce el resto del sistema.
    if not 3 <= len(nombre) <= 80:
        raise ErrorPlantilla('Escribe el nombre del documento (de 3 a 80 letras).')
    if not anterior and any(p['nombre'].lower() == nombre.lower() for p in existentes.values()):
        raise ErrorPlantilla(f'Ya hay una plantilla que se llama "{nombre}". Ábrela para cambiarla.')
    de = anterior['de'] if anterior and anterior.get('fabrica') else datos.get('de')
    if de not in DE_QUIEN:
        raise ErrorPlantilla('Elige si el documento es del alumno o del tutor.')
    textos = []
    for texto in datos.get('textos') or []:
        limpio = ' '.join(re.sub(r'[^A-Z0-9 ]+', ' ', mayusculas(str(texto))).split())
        if limpio and limpio not in textos:
            if not 3 <= len(limpio) <= 80:
                raise ErrorPlantilla(f'El texto fijo "{texto}" debe tener de 3 a 80 letras.')
            textos.append(limpio)
    if not textos:
        raise ErrorPlantilla('Escribe al menos un texto fijo: una frase que siempre trae el documento (por ejemplo, su título).')
    if len(textos) > MAXIMO_TEXTOS:
        raise ErrorPlantilla(f'Son demasiados textos fijos: deja {MAXIMO_TEXTOS} o menos.')
    try:
        minimo = int(datos.get('minimo') or 1)
    except (TypeError, ValueError):
        raise ErrorPlantilla('"Cuántos textos debe tener" debe ser un número.')
    if not 1 <= minimo <= len(textos):
        raise ErrorPlantilla(f'"Cuántos textos debe tener" va de 1 a {len(textos)}.')
    reglas = [r for r in REGLAS if r in (datos.get('reglas') or [])]
    meses = None
    if 'fecha_reciente' in reglas:
        try:
            meses = int(datos.get('meses') or 0)
        except (TypeError, ValueError):
            meses = 0
        if not 1 <= meses <= 24:
            raise ErrorPlantilla('Para la vigencia, escribe de cuántos meses (de 1 a 24).')
    if anterior and anterior.get('fabrica'):
        reglas = anterior['reglas']  # Las revisiones de fábrica son código y no cambian desde aquí.
        meses = anterior['meses']
    return {'clave': clave, 'nombre': nombre, 'de': de, 'obligatorio': bool(datos.get('obligatorio')),
            'para_padres': bool(datos.get('para_padres')), 'textos': textos, 'minimo': minimo, 'reglas': reglas, 'meses': meses,
            'fabrica': bool(anterior and anterior.get('fabrica')), 'activa': datos.get('activa', True) is not False}


def cuantos_dice(texto, plantilla):
    """Cuántos textos fijos de la plantilla aparecen en el texto (con la misma tolerancia al OCR del resto)."""
    return sum(parece(texto, [marca]) for marca in plantilla['textos'])


def coincide(texto, plantilla):
    return cuantos_dice(texto, plantilla) >= plantilla['minimo']


def aplicar(plantilla, texto, alumno, tutor, hoy, revision):
    """Las reglas elegidas para un documento de plantilla. revision: expediente.Revision."""
    nombre = plantilla['nombre']
    encontrados = cuantos_dice(texto, plantilla)
    if encontrados < plantilla['minimo']:
        revision.hallazgo('plantilla_no_coincide', nombre, f'no parece un(a) {nombre.lower()}: tiene {encontrados} de los '
                          f'{plantilla["minimo"]} textos fijos que pide su plantilla', 'media')
    reglas = set(plantilla['reglas'])
    clave = plantilla['clave']
    if 'nombre_alumno' in reglas and alumno.get('nombre'):
        revision.cotejar(f'{clave}_nombre_alumno', nombre, alumno['nombre'], texto, 'nombre', 'El nombre del alumno', orden_libre=True)
    if 'nombre_tutor' in reglas and tutor.get('nombre'):
        revision.cotejar(f'{clave}_nombre_tutor', nombre, tutor['nombre'], texto, 'nombre', 'El nombre del tutor', orden_libre=True)
    if 'curp_alumno' in reglas and alumno.get('curp'):
        if alumno['curp'].upper() not in re.sub(r'[^A-Z0-9]', '', mayusculas(texto)):
            revision.hallazgo(f'{clave}_curp', nombre, 'no trae la CURP del alumno')
    if 'domicilio' in reglas and tutor.get('domicilio'):
        revision.cotejar(f'{clave}_domicilio', nombre, tutor['domicilio'], texto, 'domicilio', 'El domicilio')
    if 'fecha_reciente' in reglas:
        pasadas = [f for f in fechas(texto) if f <= hoy]
        if not pasadas:
            revision.no_leido(f'{clave}_fecha', nombre, 'no se encontró su fecha')
        elif comparador.sumar_meses(max(pasadas), plantilla['meses']) < hoy:
            revision.hallazgo(f'{clave}_vigencia', nombre, f'la fecha más reciente es {max(pasadas)}: tiene más de '
                              f'{plantilla["meses"]} meses', 'media')
        else:
            revision.resultado['extraidos'][f'{clave}_fecha'] = max(pasadas).isoformat()


class Plantillas:
    """Las plantillas de una carpeta. Nunca se sobrescribe ni se borra un archivo: cada cambio es otra versión."""

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)

    def _versiones(self, clave):
        carpeta = self.carpeta / clave
        return sorted(carpeta.glob('v*.json')) if carpeta.is_dir() else []

    def todas(self):
        """{clave: plantilla vigente}, las de fábrica primero; incluye las dadas de baja (activa False)."""
        salida = fabrica()
        if self.carpeta.is_dir():
            for carpeta in sorted(self.carpeta.iterdir()):
                versiones = self._versiones(carpeta.name)
                if versiones:
                    salida[carpeta.name] = json.loads(versiones[-1].read_text(encoding='utf-8'))
        return salida

    def activas(self):
        return [p for p in self.todas().values() if p['activa']]

    def guardar(self, datos, quien, muestras=()):
        """Versión nueva de una plantilla. muestras: [(nombre, contenido)] que se guardan junto a ella como referencia."""
        plantilla = normalizar(datos, self.todas())
        versiones = self._versiones(plantilla['clave'])
        numero = int(versiones[-1].stem[1:]) + 1 if versiones else 1
        carpeta = self.carpeta / plantilla['clave']
        carpeta.mkdir(parents=True, exist_ok=True)
        anteriores = json.loads(versiones[-1].read_text(encoding='utf-8')).get('muestras', []) if versiones else []
        guardadas = list(anteriores)
        for indice, (nombre, contenido) in enumerate(muestras, 1):
            archivo = carpeta / f'muestra_v{numero:03d}_{indice}{Path(nombre).suffix.lower()}'
            with open(archivo, 'xb') as salida:
                salida.write(contenido)
            guardadas.append(archivo.name)
        plantilla.update(version=numero, muestras=guardadas, guardo=quien,
                         fecha=datetime.datetime.now().isoformat(timespec='seconds'))
        with open(carpeta / f'v{numero:03d}.json', 'x', encoding='utf-8') as salida:
            json.dump(plantilla, salida, ensure_ascii=False, indent=1)
        return plantilla
