"""Fichas inventadas llenadas "a mano", para medir cuánto saca el escaneo de la letra a mano.

Dibuja fichas de inscripción y certificados médicos con las etiquetas impresas y los datos en letra
manuscrita (en Windows: Ink Free, Segoe Print, Comic Sans; y las "feas": Segoe Script, Bradley Hand,
Kristen), chueca, de distinto tamaño, en tinta azul o negra, y luego como foto de celular o escaneo.
Todo es inventado. Deja en la carpeta:
- respuestas.csv: lo que de verdad dice cada hoja (archivo, tipo, clave, valor, letra, variante);
- campos.json: los datos que se esperan de cada tipo de hoja (los mismos que tendría su plantilla).

    python -m validacion.ejemplo.manuscritos C:\\SIDP-datos\\manuscritos --cuantas 12
    python -m validacion.medir_lectura C:\\SIDP-datos\\manuscritos

La prueba de verdad es con letra de personas: imprime fichas en blanco (--en-blanco), que alguien las llene
a mano con datos inventados (letra fea incluida), tómales foto, ponlas en la carpeta y agrega a
respuestas.csv lo que escribió en cada una. La carpeta va fuera del repositorio.
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

from validacion import campos as campos_mod
from validacion.ejemplo import fotos, generar

C = campos_mod.campo
FICHA = [
    C('nombre_alumno', 'Nombre del alumno', 'nombre', 'alumno', 'nombre'),
    C('fecha_nacimiento', 'Fecha de nacimiento', 'fecha', 'alumno'),
    C('curp', 'CURP', 'curp', 'alumno'),
    C('domicilio', 'Domicilio (calle, número y colonia)', 'domicilio', 'domicilio'),
    C('cp', 'Código postal', 'cp', 'domicilio'),
    C('nombre_madre', 'Nombre de la madre', 'nombre', 'madre', 'nombre'),
    C('telefono_madre', 'Teléfono de la madre', 'telefono', 'contacto', 'telefono', 'madre'),
    C('nombre_padre', 'Nombre del padre', 'nombre', 'padre', 'nombre'),
    C('telefono_padre', 'Teléfono del padre', 'telefono', 'contacto', 'telefono', 'padre'),
    C('correo', 'Correo electrónico', 'correo', 'contacto', 'correo'),
    C('alergias', 'Alergias', 'lista', 'salud', 'alergia'),
    C('enfermedades', 'Enfermedades o padecimientos', 'lista', 'salud', 'padecimiento'),
    C('contacto_emergencia', 'En caso de emergencia avisar a', 'nombre', 'contacto', 'nombre_emergencia', 'emergencia'),
    C('telefono_emergencia', 'Teléfono de emergencia', 'telefono', 'contacto', 'telefono', 'emergencia'),
]
# Lo que dice impreso el certificado médico dibujado, y a qué campo de fábrica corresponde. Trae peso, talla y fecha como
# uno de verdad, pero solo se miden los cuatro datos que se sacan (Solo lo necesario, validacion/estandar.py).
MEDICO = [('Nombre del paciente', None), ('Peso (kg)', 'peso'), ('Talla (m)', 'talla'), ('Alergias', 'alergias'),
          ('Padecimientos', 'padecimientos'), ('Medicamentos', 'medicamentos'), ('Discapacidad o condición', 'discapacidad'),
          ('Observaciones', 'observaciones'), ('Fecha', 'fecha'), ('Nombre del médico', 'medico'), ('Cédula profesional', 'cedula')]
FUENTES = [('Inkfree.ttf', 'clara'), ('segoepr.ttf', 'clara'), ('comic.ttf', 'clara'),
           ('segoesc.ttf', 'fea'), ('BRADHITC.TTF', 'fea'), ('ITCKRIST.TTF', 'fea')]
NINOS = [('MARIA FERNANDA', 'M'), ('JOSE LUIS', 'H'), ('ANA SOFIA', 'M'), ('DIEGO', 'H'), ('XIMENA', 'M'), ('SANTIAGO', 'H'),
         ('VALERIA', 'M'), ('EMILIANO', 'H'), ('REGINA', 'M'), ('MATEO', 'H'), ('CAMILA', 'M'), ('LEONARDO', 'H')]
MAMAS = ['ROSA', 'MARIA ELENA', 'PATRICIA', 'GUADALUPE', 'JUANA', 'VERONICA', 'LETICIA', 'ADRIANA']
PAPAS = ['PEDRO', 'JUAN CARLOS', 'ROBERTO', 'MIGUEL ANGEL', 'FRANCISCO', 'ARTURO', 'JORGE', 'RAUL']
APELLIDOS = ['HERNANDEZ', 'GARCIA', 'MARTINEZ', 'LOPEZ', 'GONZALEZ', 'RODRIGUEZ', 'PEREZ', 'SANCHEZ', 'RAMIREZ', 'CRUZ',
             'FLORES', 'GOMEZ', 'MORALES', 'VAZQUEZ', 'JIMENEZ', 'REYES', 'DIAZ', 'TORRES', 'GUTIERREZ', 'RUIZ']
CALLES = ['C. PINO', 'AV. HIDALGO', 'C. MORELOS', 'C. JUAREZ', 'PRIV. LAS ROSAS', 'C. ALLENDE', 'AV. INDEPENDENCIA']
COLONIAS = ['CENTRO', 'LA MORA', 'SAN JUAN', 'EL CARMEN', 'LAS FLORES', 'SANTA ANA']
ALERGIAS = ['PENICILINA', 'POLVO', 'MARISCOS', 'POLEN', 'NUEZ']
ENFERMEDADES = ['ASMA', 'RINITIS', 'DERMATITIS']
MEDICAMENTOS = ['SALBUTAMOL', 'LORATADINA', 'METILFENIDATO']
CONDICIONES = ['TDAH', 'BAJA VISION', 'HIPOACUSIA']
MESES = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']


def _consonante(palabra):
    return next((c for c in palabra[1:] if c not in 'AEIOU'), 'X')


def curp_inventada(nombre, apellido1, apellido2, nacimiento, sexo):
    vocal = next((c for c in apellido1[1:] if c in 'AEIOU'), 'X')
    prefijo = (apellido1[0] + vocal + apellido2[0] + nombre.split()[0][0] + nacimiento.strftime('%y%m%d') + sexo + 'MC'
               + _consonante(apellido1) + _consonante(apellido2) + _consonante(nombre.split()[0]) + 'A')
    return generar.curp(prefijo)


def persona(azar):
    """Una familia inventada: lo que se escribe en la hoja (como lo escribiría alguien) y lo que es de verdad."""
    import datetime
    nombre, sexo = azar.choice(NINOS)
    ap1, ap2, ap_madre2, ap_padre2 = azar.sample(APELLIDOS, 4)
    nacimiento = datetime.date(azar.randint(2014, 2020), azar.randint(1, 12), azar.randint(1, 28))
    telefonos = [f'722{azar.randint(1000000, 9999999)}' for _ in range(3)]
    alergias = azar.sample(ALERGIAS, azar.choice((0, 0, 1, 2)))
    enfermedades = azar.sample(ENFERMEDADES, azar.choice((0, 0, 0, 1)))
    madre, padre = f'{azar.choice(MAMAS)} {ap2} {ap_madre2}', f'{azar.choice(PAPAS)} {ap1} {ap_padre2}'
    calle, numero, colonia, cp = azar.choice(CALLES), azar.randint(1, 250), azar.choice(COLONIAS), str(azar.randint(50000, 52999))
    correo = f'{madre.split()[0].lower()}.{ap2.lower()}{azar.randint(1, 99)}@{azar.choice(("gmail.com", "hotmail.com"))}'
    verdad = {
        'nombre_alumno': f'{nombre} {ap1} {ap2}', 'fecha_nacimiento': nacimiento.isoformat(),
        'curp': curp_inventada(nombre, ap1, ap2, nacimiento, sexo), 'domicilio': f'{calle} {numero} COL. {colonia}', 'cp': cp,
        'nombre_madre': madre, 'telefono_madre': telefonos[0], 'nombre_padre': padre, 'telefono_padre': telefonos[1], 'correo': correo,
        'alergias': ', '.join(alergias) or 'NINGUNA', 'enfermedades': ', '.join(enfermedades) or 'NINGUNA',
        'contacto_emergencia': f'{azar.choice(MAMAS)} {ap2} {azar.choice(APELLIDOS)}', 'telefono_emergencia': telefonos[2],
    }
    escrito = {k: v.title() if k.startswith(('nombre', 'contacto')) else v for k, v in verdad.items()}
    t = telefonos
    escrito.update(
        fecha_nacimiento=azar.choice([nacimiento.strftime('%d/%m/%Y'), f'{nacimiento.day}-{MESES[nacimiento.month - 1].lower()}-{nacimiento.year}']),
        telefono_madre=azar.choice([f'{t[0][:3]} {t[0][3:6]} {t[0][6:]}', f'{t[0][:3]}-{t[0][3:6]}-{t[0][6:]}', t[0]]),
        telefono_padre=f'{t[1][:3]} {t[1][3:]}', telefono_emergencia=t[2],
        domicilio=f'{calle.title()} #{numero}, Col. {colonia.title()}',
        alergias=(' y '.join(a.lower() for a in alergias) or azar.choice(['ninguna', 'no', 'negadas'])).capitalize(),
        enfermedades=(', '.join(e.lower() for e in enfermedades) or azar.choice(['ninguna', 'ninguno'])).capitalize(),
    )
    return verdad, escrito


def fuentes_a_mano(tamano):
    """Las letras manuscritas que hay en esta PC: [(fuente, 'clara' o 'fea')]. En Linux, las de siempre."""
    from PIL import ImageFont
    encontradas = []
    for nombre, letra in FUENTES:
        for carpeta in ('C:/Windows/Fonts/', ''):
            try:
                encontradas.append((nombre, letra, ImageFont.truetype(carpeta + nombre, tamano)))
                break
            except OSError:
                continue
    return encontradas or [('normal', 'clara', fotos.fuente(tamano))]


def escribir(imagen, x, y, texto, fuente, azar, fea):
    """Un dato escrito a mano: cada palabra un poco más arriba o abajo y todo el renglón chueco."""
    from PIL import Image, ImageDraw
    tinta = azar.choice([(20, 40, 140), (25, 25, 30), (30, 60, 160)])
    capa = Image.new('RGBA', (1500, 140), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    posicion = 6
    for palabra in texto.split():
        dibujo.text((posicion, 30 + azar.randint(-6, 6) * (2 if fea else 1)), palabra, fill=tinta + (255,), font=fuente)
        posicion += int(dibujo.textlength(palabra + ' ', font=fuente)) + azar.randint(-4, 10)
    capa = capa.rotate(azar.uniform(-5, 5) if fea else azar.uniform(-2.5, 2.5), resample=Image.BICUBIC, expand=False)
    imagen.paste(capa, (x, y - 40), capa)


def hoja_ficha(escrito, fuente, azar, fea):
    from PIL import Image, ImageDraw
    imagen = Image.new('RGB', (1700, 2200), 'white')
    dibujo = ImageDraw.Draw(imagen)
    dibujo.text((120, 90), 'FICHA DE INSCRIPCIÓN · CICLO ESCOLAR 2026-2027', fill=(20, 20, 20), font=fotos.fuente(46))
    dibujo.text((120, 160), 'Escuela primaria (formato inventado para pruebas de SIDP)', fill=(90, 90, 90), font=fotos.fuente(28))
    etiqueta = fotos.fuente(30)
    y = 270
    for c in FICHA:
        dibujo.text((120, y), c['etiqueta'] + ':', fill=(30, 30, 30), font=etiqueta)
        x = 120 + int(dibujo.textlength(c['etiqueta'] + ': ', font=etiqueta))
        if x > 900:  # Etiqueta larga: se escribe en el renglón de abajo.
            x, y = 160, y + 52
        dibujo.line((x, y + 40, 1600, y + 40), fill=(150, 150, 150), width=2)
        if escrito.get(c['clave']):
            escribir(imagen, x + 10, y, escrito[c['clave']], fuente, azar, fea)
        y += 118
    return imagen


def hoja_medico(verdad, escrito, fuente, azar, fea):
    from PIL import Image, ImageDraw
    imagen = Image.new('RGB', (1700, 2200), 'white')
    dibujo = ImageDraw.Draw(imagen)
    dibujo.text((120, 90), 'CERTIFICADO MÉDICO', fill=(20, 20, 20), font=fotos.fuente(52))
    dibujo.text((120, 165), 'Centro de salud (formato inventado para pruebas de SIDP)', fill=(90, 90, 90), font=fotos.fuente(28))
    etiqueta = fotos.fuente(30)
    y = 290
    for texto, clave in MEDICO:
        dibujo.text((120, y), texto + ':', fill=(30, 30, 30), font=etiqueta)
        x = 120 + int(dibujo.textlength(texto + ': ', font=etiqueta))
        dibujo.line((x, y + 40, 1600, y + 40), fill=(150, 150, 150), width=2)
        valor = escrito['nombre_alumno'] if clave is None else escrito.get(clave)
        if valor:
            escribir(imagen, x + 10, y, valor, fuente, azar, fea)
        y += 140
    return imagen


def datos_medico(azar):
    import datetime
    fecha = datetime.date(2026, azar.randint(7, 9), azar.randint(1, 28))
    peso, talla = round(azar.uniform(16, 42), 1), round(azar.uniform(1.0, 1.5), 2)
    medico = f'{azar.choice(["DR.", "DRA."])} {azar.choice(PAPAS + MAMAS)} {azar.choice(APELLIDOS)}'
    cedula = str(azar.randint(1000000, 12999999))
    medicamentos = azar.sample(MEDICAMENTOS, azar.choice((0, 0, 0, 1)))
    condiciones = azar.sample(CONDICIONES, azar.choice((0, 0, 0, 0, 1)))
    verdad = {'medicamentos': ', '.join(medicamentos) or 'NINGUNO', 'discapacidad': ', '.join(condiciones) or 'NINGUNA'}
    escrito = {'peso': f'{peso} kg'.replace('.', azar.choice(['.', ','])), 'talla': f'{talla} m', 'observaciones': 'Sano',
               'fecha': f'{fecha.day:02d}/{fecha.month:02d}/{fecha.year}', 'medico': medico.title(), 'cedula': cedula,
               'medicamentos': ', '.join(m.lower() for m in medicamentos).capitalize() or azar.choice(['Ninguno', 'No']),
               'discapacidad': ', '.join(condiciones) or azar.choice(['Ninguna', 'No'])}
    return verdad, escrito


def crear(destino, cuantas=12, semilla=7, en_blanco=False):
    try:
        import cv2
        import numpy
        from PIL import Image
    except ImportError:
        print('Hace falta opencv y Pillow: python -m pip install -r validacion/requisitos.txt', file=sys.stderr)
        raise SystemExit(2)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    azar = random.Random(semilla)
    (destino / 'campos.json').write_text(json.dumps({'ficha_inscripcion': FICHA, 'certificado_medico': campos_mod.FABRICA['certificado_medico']},
                                                    ensure_ascii=False, indent=1), encoding='utf-8')
    if en_blanco:  # Para imprimir y llenar a mano.
        hoja_ficha({}, None, azar, False).save(destino / 'ficha_en_blanco.pdf', resolution=200)
        return 0
    renglones = []
    for numero in range(cuantas):
        verdad, escrito = persona(azar)
        medico_verdad, medico_escrito = datos_medico(azar)
        medico_verdad.update(alergias=verdad['alergias'], padecimientos=verdad['enfermedades'])
        medico_escrito.update(alergias=escrito['alergias'], padecimientos=escrito['enfermedades'], nombre_alumno=escrito['nombre_alumno'])
        opciones = fuentes_a_mano(azar.randint(40, 54))
        nombre_fuente, letra, fuente = opciones[numero % len(opciones)]
        for tipo, imagen, respuestas in (('ficha_inscripcion', hoja_ficha(escrito, fuente, azar, letra == 'fea'), verdad),
                                          ('certificado_medico', hoja_medico(verdad, medico_escrito, fuente, azar, letra == 'fea'), medico_verdad)):
            variante = fotos.VARIANTES[(numero + (tipo == 'certificado_medico')) % len(fotos.VARIANTES)]
            foto = fotos.deformar(imagen, variante, cv2, numpy)
            archivo = f'{numero + 1:02d}_{tipo}.' + ('pdf' if variante == 'escaneo' else 'jpg')
            if variante == 'escaneo':
                Image.fromarray(cv2.cvtColor(foto, cv2.COLOR_BGR2RGB)).save(destino / archivo, resolution=200)
            else:
                cv2.imwrite(str(destino / archivo), foto, [cv2.IMWRITE_JPEG_QUALITY, 85])
            renglones += [{'archivo': archivo, 'tipo': tipo, 'clave': clave, 'valor': valor, 'letra': f'{letra} ({nombre_fuente})',
                           'variante': variante} for clave, valor in respuestas.items()]
    with open(destino / 'respuestas.csv', 'w', newline='', encoding='utf-8') as salida:
        escritor = csv.DictWriter(salida, ['archivo', 'tipo', 'clave', 'valor', 'letra', 'variante'])
        escritor.writeheader()
        escritor.writerows(renglones)
    return cuantas * 2


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='python -m validacion.ejemplo.manuscritos')
    parser.add_argument('destino', type=Path, help='Carpeta fuera del repositorio')
    parser.add_argument('--cuantas', type=int, default=12, help='Cuántas familias inventadas (cada una: ficha y certificado)')
    parser.add_argument('--semilla', type=int, default=7)
    parser.add_argument('--en-blanco', action='store_true', help='Solo la ficha en blanco, para imprimirla y llenarla a mano')
    args = parser.parse_args(argumentos)
    hojas = crear(args.destino, args.cuantas, args.semilla, args.en_blanco)
    print(f'Ficha en blanco en {args.destino}' if args.en_blanco else f'{hojas} hojas "a mano" en {args.destino}, con respuestas.csv y campos.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
