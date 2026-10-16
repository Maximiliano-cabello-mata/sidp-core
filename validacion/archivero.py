"""El archivero del servidor: cada expediente como lo abre la escuela, en carpetas y solo en PDF.

    C:\\SIDP\\Expedientes\\3° A\\HERNÁNDEZ LÓPEZ MARÍA JOSÉ\\Acta de nacimiento.pdf
                                                       \\INE del tutor.pdf
                                                       \\anteriores\\Acta de nacimiento 2026-10-16 0930.pdf

- Un PDF por documento: las fotos y las hojas sueltas de un mismo documento se juntan en un solo PDF.
- Nada se sobrescribe: si llega otra versión de un documento, la anterior pasa a "anteriores" con la fecha.
- Si el alumno cambia de grupo, su carpeta se mueve al grupo nuevo (se reconoce por la CURP, no por el nombre).
- Dos alumnos con el mismo nombre no se mezclan: al segundo se le agrega el inicio de su CURP.

Los datos que se extraen de estos documentos no viven aquí: van a la base de la PC 4.
"""
import datetime
import io
import json
import re
import shutil
from pathlib import Path

INDICE = '.sidp_indice.json'  # CURP o identificador -> carpeta del alumno (relativa a la raíz).
IMAGENES = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.heic')


def nombre_valido(texto):
    """Un nombre que Windows acepta como carpeta o archivo."""
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', str(texto or '')).strip(' .')
    return re.sub(r'\s+', ' ', limpio)[:80] or 'Sin nombre'


def a_pdf(partes):
    """Un solo PDF con todas las partes, en orden: PDF tal cual y cada imagen como una hoja."""
    import pypdf
    escritor = pypdf.PdfWriter()
    for extension, contenido in partes:
        if extension.lower() == '.pdf':
            for pagina in pypdf.PdfReader(io.BytesIO(contenido)).pages:
                escritor.add_page(pagina)
            continue
        if extension.lower() not in IMAGENES:
            continue
        from PIL import Image, ImageOps  # Solo hace falta con fotos; un PDF se copia tal cual.
        imagen = ImageOps.exif_transpose(Image.open(io.BytesIO(contenido))).convert('RGB')
        hoja = io.BytesIO()
        imagen.save(hoja, 'PDF', resolution=150)
        for pagina in pypdf.PdfReader(io.BytesIO(hoja.getvalue())).pages:
            escritor.add_page(pagina)
    if not escritor.pages:
        return None
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


class Archivero:
    def __init__(self, raiz):
        self.raiz = Path(raiz)

    def _indice(self):
        archivo = self.raiz / INDICE
        return json.loads(archivo.read_text(encoding='utf-8')) if archivo.exists() else {}

    def _guardar_indice(self, indice):
        self.raiz.mkdir(parents=True, exist_ok=True)
        temporal = self.raiz / (INDICE + '.nuevo')
        temporal.write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding='utf-8')
        temporal.replace(self.raiz / INDICE)

    def carpeta(self, clave, nombre, grupo):
        """La carpeta del alumno (la crea o la mueve a su grupo actual)."""
        indice = self._indice()
        grupo = nombre_valido(grupo or 'Sin grupo')
        nombre = nombre_valido(nombre)
        actual = self.raiz / indice[clave] if clave in indice else None
        if actual and actual.exists():
            if actual.parent.name == grupo:
                return actual
            destino = self._libre(self.raiz / grupo, actual.name, clave, indice)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(actual), str(destino))
        else:
            destino = self._libre(self.raiz / grupo, nombre, clave, indice)
            destino.mkdir(parents=True, exist_ok=True)
        indice[clave] = destino.relative_to(self.raiz).as_posix()
        self._guardar_indice(indice)
        return destino

    def _libre(self, grupo, nombre, clave, indice):
        ocupadas = {ruta for otra, ruta in indice.items() if otra != clave}
        candidato = grupo / nombre
        if candidato.relative_to(self.raiz).as_posix() in ocupadas or (candidato.exists() and clave not in indice):
            candidato = grupo / f'{nombre} ({clave[:10]})'
        return candidato

    def guardar(self, carpeta, documento, partes):
        """'igual', 'nuevo' o 'cambiado'. La versión anterior se queda en anteriores/ con la fecha."""
        contenido = a_pdf(partes)
        if contenido is None:
            return None
        destino = Path(carpeta) / f'{nombre_valido(documento)}.pdf'
        if destino.exists():
            if destino.read_bytes() == contenido:
                return 'igual'
            anteriores = destino.parent / 'anteriores'
            anteriores.mkdir(exist_ok=True)
            destino.replace(anteriores / f'{destino.stem} {datetime.datetime.now():%Y-%m-%d %H%M%S}.pdf')
            estado = 'cambiado'
        else:
            estado = 'nuevo'
        temporal = destino.with_name(destino.name + '.nuevo')
        temporal.write_bytes(contenido)
        temporal.replace(destino)
        return estado

    def archivar(self, clave, nombre, grupo, documentos):
        """documentos: {nombre del documento: [(extension, contenido)]}. Devuelve la carpeta y qué pasó con cada uno."""
        carpeta = self.carpeta(clave, nombre, grupo)
        return carpeta, {documento: self.guardar(carpeta, documento, partes) for documento, partes in documentos.items() if partes}
