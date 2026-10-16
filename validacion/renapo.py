"""La CURP del alumno validada ante RENAPO, con ayuda de una persona.

RENAPO no tiene un servicio abierto: su página oficial (gob.mx/curp) pide resolver un captcha, y el
servicio web es solo por convenio. Por eso lo hace una persona, sin bots:

1. En el panel copia la CURP que ya tenemos y abre la página oficial.
2. La pega, resuelve el captcha y descarga la constancia en PDF.
3. Arrastra el PDF al panel.

Aquí se lee esa constancia: qué CURP trae y si el nombre coincide con el del alumno. Con eso la
CURP pasa de "sin validar" a "validada en RENAPO" y la constancia se guarda como prueba.
"""
import functools
import io
import re

from validacion import comparador

PAGINA_OFICIAL = 'https://www.gob.mx/curp/'
MAXIMO = 5 * 1024 * 1024
CURP_EN_TEXTO = re.compile(r'(?<![A-Z0-9])([A-Z][AEIOUX][A-Z]{2}\d{6}[HMX][A-Z]{5}[0-9A-Z]\d)(?![A-Z0-9])')
# Lo que dice toda constancia de la CURP; basta con una de estas frases.
MARCAS = ('REGISTRO DE POBLACION', 'RENAPO', 'CONSTANCIA DE LA CLAVE')
ESTADOS = {'sin_validar': 'Sin validar', 'validada': 'Validada en RENAPO', 'no_coincide': 'Revisar: no coincide',
           'no_encontrada': 'RENAPO no la encontró', 'sin_curp': 'Falta la CURP'}


class ErrorConstancia(Exception):
    """El archivo no se pudo usar como constancia; el mensaje es para la persona del panel."""


def texto_pdf(contenido):
    if not contenido.startswith(b'%PDF'):
        raise ErrorConstancia('Ese archivo no es un PDF. Arrastra el PDF que descargaste de la página de RENAPO.')
    if len(contenido) > MAXIMO:
        raise ErrorConstancia('El PDF es demasiado grande para ser una constancia de la CURP.')
    try:
        import pypdf
    except ImportError as error:
        raise ErrorConstancia('Falta pypdf en esta PC para leer la constancia.') from error
    try:
        lector = pypdf.PdfReader(io.BytesIO(contenido))
        return '\n'.join(pagina.extract_text() or '' for pagina in lector.pages[:5])
    except Exception as error:  # Un PDF dañado no tumba el panel.
        raise ErrorConstancia(f'No se pudo abrir el PDF ({type(error).__name__}). Descárgalo otra vez de la página de RENAPO.') from error


def leer_constancia(contenido):
    """{'texto': texto normalizado, 'curps': CURP con dígito verificador correcto} o ErrorConstancia."""
    texto = comparador.normalizar(texto_pdf(contenido))
    if not texto:
        raise ErrorConstancia('No se pudo leer el texto del PDF. Descarga la constancia otra vez desde la página de RENAPO '
                              '(no una foto ni un escaneo).')
    if not any(marca in texto for marca in MARCAS):
        raise ErrorConstancia('Ese PDF no parece la constancia de la CURP. Es el que se descarga en la página de RENAPO '
                              'después de buscar la CURP.')
    curps = []
    for curp in CURP_EN_TEXTO.findall(texto):
        desglose = comparador.desglose_curp(curp)
        if desglose and desglose['digito_valido'] and curp not in curps:
            curps.append(curp)
    if not curps:
        raise ErrorConstancia('No se encontró ninguna CURP en la constancia.')
    return {'texto': texto, 'curps': curps}


def partir(pegado, palabras):
    """Las palabras de la constancia que, juntas y en orden, forman `pegado` ("GARCIALOPEZ" -> GARCIA, LOPEZ), o None.

    Pasa con las listas oficiales en PDF: a veces el texto sale sin el espacio entre dos apellidos o dos nombres.
    """
    candidatas = sorted({p for p in palabras if len(p) >= 2 and p.isalpha()}, key=len, reverse=True)

    @functools.lru_cache(maxsize=None)
    def desde(inicio):
        if inicio == len(pegado):
            return ()
        for palabra in candidatas:
            if pegado.startswith(palabra, inicio):
                resto = desde(inicio + len(palabra))
                if resto is not None:
                    return (palabra,) + resto
        return None
    return desde(0) if pegado else None


def faltan_del_nombre(texto, nombre):
    """Palabras del nombre del alumno que no aparecen en la constancia (vacío si coincide).

    Una palabra pegada ("GARCIALOPEZ") cuenta como que sí aparece si la constancia trae sus partes.
    """
    palabras = set(texto.split())
    return [p for p in comparador.normalizar(nombre).split() if p not in palabras and not partir(p, palabras)]


COMUNES = {'JOSE', 'J', 'MARIA', 'MA', 'M'}  # La CURP se salta estos primeros nombres y usa la inicial del segundo.


def nombre_de_renapo(texto, curp, primer_apellido, segundo_apellido, nombres):
    """El nombre bien separado cuando en la lista venía pegado, con las palabras de la constancia; o None.

    Las partes se acomodan en el orden de la lista (primer apellido, segundo, nombres) y se aceptan solo si cuadran
    con las letras de la CURP: inicial del primer apellido (1), del segundo (3) y del nombre (4).
    """
    antes = [comparador.normalizar(x) for x in (primer_apellido, segundo_apellido, nombres)]
    partes = partir(''.join(antes).replace(' ', ''), set(texto.split()))
    if not partes or not curp or len(curp) < 4:
        return None
    from validacion.extraer import PARTICULAS
    posicion = 0

    def apellido():
        nonlocal posicion
        inicio = posicion
        while posicion < len(partes) - 1 and partes[posicion] in PARTICULAS:
            posicion += 1
        posicion += 1
        return partes[inicio:posicion]

    def cuadra(letra, palabra):
        return letra == 'X' or palabra[:1] == letra

    primero = apellido()
    segundo = [] if curp[2] == 'X' and len(partes) - posicion < 2 else apellido()
    resto = list(partes[posicion:])
    if not resto or not cuadra(curp[0], primero[-1]) or (segundo and not cuadra(curp[2], segundo[-1])):
        return None
    inicial = resto[1] if resto[0] in COMUNES and len(resto) > 1 else resto[0]
    if not cuadra(curp[3], inicial):
        return None
    despues = {'primer_apellido': ' '.join(primero), 'segundo_apellido': ' '.join(segundo) or None, 'nombres': ' '.join(resto)}
    if [despues['primer_apellido'], despues['segundo_apellido'] or '', despues['nombres']] == antes:
        return None  # Ya estaba bien.
    return despues
