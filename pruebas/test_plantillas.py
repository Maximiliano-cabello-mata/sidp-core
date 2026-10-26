"""Plantillas de documentos: textos fijos propuestos desde muestras y reglas elegidas de una lista."""
import datetime

from validacion import plantillas
from validacion.expediente import Revision


def test_de_una_muestra_llena_solo_quedan_las_etiquetas():
    texto = 'CARTA COMPROMISO DE DOCUMENTOS\nNombre del alumno: LUIS HERNANDEZ RAMOS\nFecha: 01/10/2026\nMe comprometo a entregar'
    assert plantillas.proponer_textos([texto]) == ['CARTA COMPROMISO DE DOCUMENTOS', 'NOMBRE DEL ALUMNO', 'ME COMPROMETO A ENTREGAR']


def test_con_dos_muestras_lo_que_cambia_no_es_fijo():
    uno = 'FICHA DE INSCRIPCION\nLUIS HERNANDEZ RAMOS\nGRADO Y GRUPO'
    dos = 'FICHA DE INSCRIPCION\nANA SOFIA BRAVO LEON\nGRADO Y GRUPO'
    assert plantillas.proponer_textos([uno, dos]) == ['FICHA DE INSCRIPCION', 'GRADO Y GRUPO']


def test_las_reglas_elegidas_se_aplican():
    plantilla = plantillas.normalizar({'nombre': 'Carta compromiso', 'de': 'alumno', 'textos': ['CARTA COMPROMISO', 'ME COMPROMETO'],
                                       'minimo': 2, 'reglas': ['nombre_alumno', 'curp_alumno', 'fecha_reciente'], 'meses': 1}, {})
    alumno = {'nombre': 'LUIS HERNANDEZ RAMOS', 'curp': 'HERL180314HMCRMSA9'}
    revision = Revision('x')
    plantillas.aplicar(plantilla, 'CARTA COMPROMISO\nLUIS HERNANDEZ RAMOS\n01/08/2026', alumno, {}, datetime.date(2026, 10, 15), revision)
    reglas = {h['regla'] for h in revision.resultado['hallazgos']}
    assert reglas == {'plantilla_no_coincide', 'p_carta_compromiso_curp', 'p_carta_compromiso_vigencia'}
    revision = Revision('y')
    plantillas.aplicar(plantilla, 'CARTA COMPROMISO ME COMPROMETO LUIS HERNANDEZ RAMOS HERL180314HMCRMSA9 01/10/2026', alumno, {},
                       datetime.date(2026, 10, 15), revision)
    assert not revision.resultado['hallazgos'] and not revision.resultado['grises']
