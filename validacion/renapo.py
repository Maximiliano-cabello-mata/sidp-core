"""La CURP del alumno validada ante RENAPO, con ayuda de una persona.

RENAPO no tiene un servicio abierto: su página oficial (gob.mx/curp) pide resolver un captcha, y el
servicio web es solo por convenio. Por eso lo hace una persona, sin bots:

1. En el panel copia la CURP que ya tenemos y abre la página oficial.
2. La pega, resuelve el captcha y descarga la constancia en PDF.
3. Arrastra el PDF al panel.

Aquí se lee esa constancia: qué CURP trae y si el nombre coincide con el del alumno. Con eso la
CURP pasa de "sin validar" a "validada en RENAPO" y la constancia se guarda como prueba.
"""
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


def faltan_del_nombre(texto, nombre):
    """Palabras del nombre del alumno que no aparecen en la constancia (vacío si coincide)."""
    palabras = set(texto.split())
    return [p for p in comparador.normalizar(nombre).split() if p not in palabras]
