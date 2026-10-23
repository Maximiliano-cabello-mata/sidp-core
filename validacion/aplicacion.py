"""SIDP-Validador.exe: la PC del administrador en el entorno de pruebas.

Guarda los expedientes (archivos sin sobrescribir y datos en SQLite con las 39 tablas),
manda cada uno al cerebro de la PC 4 para que lo valide por IP y muestra el panel donde una
persona autoriza o rechaza. También sirve la página de padres a la red local.

- Panel del administrador: http://127.0.0.1:8770/ en esta PC, sin contraseña.
- Desde las otras computadoras de la escuela: http://IP-de-esta-PC:8770/ con el usuario y la contraseña que
  Dirección crea en Ajustes > Cuentas. Así lo que se escanea en cualquier PC se guarda aquí, en el servidor.
- Página de padres: http://IP-de-esta-PC:8770/padres (cualquier equipo de la red).
- El cerebro lee lo guardado para el análisis: GET /api/cerebro/datos con su clave.

Uso: SIDP-Validador.exe [carpeta] [--puerto 8770] [--cerebro http://IP:8771 --clave X]
     SIDP-Validador.exe validacion/ejemplo --hoy 2026-10-14 --revisar   (sin ventana: imprime y sale)
"""
import argparse
import datetime
import json
import mimetypes
import secrets
import sys
import threading
import time
import webbrowser
from email.parser import BytesParser
from email.policy import default as politica_correo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from validacion import cerebro_red, codigo_barras, prueba
from validacion.cuentas import Cuentas, ErrorCuenta, PERMISOS
from validacion.registro import Registro
from validacion.servicio import Bandeja, ErrorBandeja

RAIZ = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
INTERFAZ = RAIZ / 'validacion' / 'interfaz'
PUERTO = 8770
MAXIMO_ENVIO = 100 * 1024 * 1024
ESTATICOS = {'/estilo.css': 'estilo.css', '/motor.js': 'motor.js'}
LOCALES = ('127.0.0.1', '::1')
# Desde otra PC, cada ruta pide un permiso del rol (validacion/cuentas.py). Gana el primer prefijo que coincide;
# None es cualquier cuenta; lo que no está aquí es solo de Dirección, y SOLO_ESTA_PC solo se usa en el servidor mismo.
PERMISO_RUTA = (
    ('/api/yo', None),
    ('/api/renapo', 'renapo'), ('/api/curps', 'renapo'), ('/api/estado', 'expedientes'), ('/api/buscar_alumno', 'expedientes'),
    ('/api/trabajos', 'expedientes'), ('/api/escaneo', 'documentos'), ('/api/expediente', 'documentos'), ('/api/archivo', 'documentos'),
    ('/api/pdf', 'documentos'), ('/api/dato', 'documentos'), ('/api/por_confirmar', 'documentos'), ('/api/plantillas', 'documentos'),
    ('/api/alumno/', 'decidir'), ('/api/alumno', 'documentos'), ('/api/decidir', 'decidir'), ('/api/revisar_todo', 'decidir'),
    ('/api/grupo', 'grupos'), ('/api/listas', 'grupos'), ('/api/inventario', 'grupos'), ('/api/etiquetas', 'grupos'),
    ('/api/analisis', 'ver_grupos'), ('/api/exportar', 'ver_grupos'), ('/api/cuentas', 'personal'),
)
SOLO_ESTA_PC = ('/api/configuracion', '/api/cerebro/buscar', '/api/base', '/api/respaldo')
LOCAL = {'id': None, 'usuario': 'servidor', 'rol': 'direccion', 'rol_texto': 'Dirección', 'nombre': 'Esta PC (servidor)', 'local': True}


def permiso_de(ruta):
    for prefijo, permiso in PERMISO_RUTA:
        if ruta.startswith(prefijo):
            return permiso
    return 'ajustes'


def carpeta_por_omision():
    return Path.home() / 'SIDP-prueba'


class Aplicacion:
    def __init__(self, carpeta, hoy=None, puerto=PUERTO, usar_modelo=True, expedientes=None, conectar_al_abrir=True):
        self.carpeta = Path(carpeta).resolve()
        self.vigia = None  # En el .exe instalado (escritorio.Vigia) cuida la conexión con la PC 4.
        self.actualizador = None  # En el .exe instalado (actualizar.Actualizador) toma de la PC 4 la versión nueva.
        self.servidor = None
        self.ultimo_cambio = time.time()  # La versión nueva se pone cuando nadie ha cambiado nada en un rato.
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(16)  # Sin él, otra página del navegador no puede usar el panel.
        self.puerto = puerto
        self.candado = threading.Lock()
        self.bandeja = Bandeja(self.carpeta, hoy, usar_modelo=usar_modelo, registro=Registro(self.carpeta / 'plataforma_prueba.db'),
                               expedientes=expedientes)
        self.cuentas = Cuentas(self.bandeja.registro.db)  # Quién entra desde las otras PC de la escuela.
        self.archivo_configuracion = self.carpeta / 'configuracion.json'
        self.configuracion = {}
        if self.archivo_configuracion.exists():
            self.configuracion = json.loads(self.archivo_configuracion.read_text(encoding='utf-8'))
        if self.configuracion and conectar_al_abrir:
            self.bandeja.conectar_cerebro(self.configuracion.get('cerebro_url'), self.configuracion.get('cerebro_clave', ''))

    def configurar(self, url, clave):
        problema = self.bandeja.conectar_cerebro((url or '').strip(), (clave or '').strip())
        self.configuracion = {'cerebro_url': (url or '').strip(), 'cerebro_clave': (clave or '').strip()}
        self.archivo_configuracion.write_text(json.dumps(self.configuracion), encoding='utf-8')
        return problema

    def estado_configuracion(self, problema=None):
        estado = {**self.configuracion, 'cerebro_conectado': bool(self.bandeja.cerebro), 'padron': self.bandeja.padron_aviso,
                  'traidos': self.bandeja.traidos_aviso, 'respaldo': self.bandeja.respaldo_aviso, 'direccion_padres': self.direccion_padres(),
                  'expedientes': str(self.bandeja.expedientes_alumno) if self.bandeja.expedientes_alumno else None}
        if self.vigia:
            estado['vigia'] = self.vigia.estado
        if self.actualizador:
            estado['actualizacion'] = self.actualizador.estado
        if problema is not None:
            estado['problema'] = problema
        return estado

    def datos_para_cerebro(self):
        """Lo extraído y decidido, sin archivos: lo que el cerebro necesita para el análisis."""
        decisiones = self.bandeja.decisiones()
        return [{'id': i, 'estado': r['estado'], 'reglas': sorted({h['regla'] for h in r['hallazgos']} | {g['regla'] for g in r['grises']}
                                                                    | {n['regla'] for n in r['no_leidos']}),
                 'extraidos': r.get('extraidos', {}), 'documentos': r.get('documentos', {}), 'decision': decisiones.get(i)}
                for i, r in self.bandeja.resultados.items()]

    def pagina(self, nombre, local=True):
        if nombre == 'panel.html' and not local:  # Otra PC: el panel pide usuario y contraseña.
            config = {'modo': 'red', 'token': ''}
        else:
            config = {'modo': 'local', 'token': self.token if nombre == 'panel.html' else ''}
        texto = (INTERFAZ / nombre).read_text(encoding='utf-8')
        return texto.replace('/*SIDP_CONFIG*/', f'window.SIDP = {json.dumps(config)};').encode()

    def direccion_padres(self):
        return f'http://{cerebro_red.ip_local()}:{self.puerto}/padres'

    def direccion_red(self):
        return f'http://{cerebro_red.ip_local()}:{self.puerto}/'

    def cuentas_estado(self):
        return {'cuentas': self.cuentas.lista(), 'direccion': self.direccion_red()}


def respaldar_seguido(app, cada=3600, primera=120):
    """Cada hora (la primera vez, 2 minutos después de abrir) copia a la PC 4 lo nuevo; si no está, lo intenta después."""
    import time
    time.sleep(primera)
    while True:
        if app.bandeja.cerebro:
            try:
                app.bandeja.respaldar()
            except ErrorBandeja as error:
                print(error, flush=True)
        time.sleep(cada)


def crear_servidor(aplicacion, anfitrion='0.0.0.0', clave_apagar=None):
    app = aplicacion

    class Manejador(BaseHTTPRequestHandler):
        def _enviar(self, codigo, cuerpo, tipo='application/json; charset=utf-8'):
            if not isinstance(cuerpo, bytes):
                cuerpo = json.dumps(cuerpo, ensure_ascii=False, default=str).encode()
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(cuerpo)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(cuerpo)

        def _descargar(self, nombre, cuerpo, tipo):
            self.send_response(200)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(cuerpo)))
            self.send_header('Content-Disposition', f'attachment; filename="{nombre}"')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(cuerpo)

        def _local(self):
            return self.client_address[0] in LOCALES

        def _admin(self, consulta=None):
            """En esta PC, el token que se le dio al panel al abrirlo; desde otra PC, una sesión con el permiso de la ruta."""
            token = self.headers.get('X-SIDP-Token') or (consulta or {}).get('t', [''])[0]
            ruta = urlparse(self.path).path
            if self._local() and secrets.compare_digest(token, app.token):
                self.usuario = LOCAL
                return True
            with app.candado:
                usuario = app.cuentas.sesion(token)
            if not usuario and self._local():
                self._enviar(403, {'error': 'El panel de esta PC necesita el token que se le dio al abrirlo'})
                return False
            if not usuario:
                self._enviar(401, {'error': 'Tu sesión terminó. Vuelve a entrar con tu usuario y contraseña.', 'entrar': True})
                return False
            permiso = permiso_de(ruta)
            if ruta in SOLO_ESTA_PC or (permiso and permiso not in PERMISOS.get(usuario['rol'], set())):
                self._enviar(403, {'error': 'Tu cuenta no puede hacer esto. Pídeselo a Dirección.'})
                return False
            self.usuario = usuario
            return True

        def _cerebro(self):
            clave = app.configuracion.get('cerebro_clave', '')
            if clave and secrets.compare_digest(self.headers.get('X-SIDP-Clave', ''), clave):
                return True
            self._enviar(401, {'error': 'clave incorrecta'})
            return False

        def _cuerpo(self):
            largo = int(self.headers.get('Content-Length') or 0)
            if largo < 0:
                raise ErrorBandeja('Envío no válido')
            if largo > MAXIMO_ENVIO:
                raise ErrorBandeja('El envío es demasiado grande (máximo 100 MB)')
            return self.rfile.read(largo)

        def do_GET(self):
            url = urlparse(self.path)
            consulta = parse_qs(url.query)
            try:
                if url.path in ('/', '/index.html', '/panel.html'):
                    return self._enviar(200, app.pagina('panel.html', self._local()), 'text/html; charset=utf-8')
                if url.path in ('/padres', '/padres.html'):
                    return self._enviar(200, app.pagina('padres.html'), 'text/html; charset=utf-8')
                if url.path == '/api/hola':  # Para saber si SIDP ya está abierto en esta PC; no dice nada más.
                    from validacion import escritorio
                    return self._enviar(200, {'sidp': 'servidor', 'version': escritorio.version()})
                if url.path in ESTATICOS:
                    nombre = ESTATICOS[url.path]
                    return self._enviar(200, (INTERFAZ / nombre).read_bytes(), mimetypes.guess_type(nombre)[0] + '; charset=utf-8')
                if url.path == '/api/padres/documentos':  # Qué documentos pide la página de padres.
                    with app.candado:
                        return self._enviar(200, {'documentos': app.bandeja.documentos_padres()})
                if url.path == '/api/cerebro/datos':
                    if self._cerebro():
                        with app.candado:
                            self._enviar(200, {'expedientes': app.datos_para_cerebro()})
                    return
                if not url.path.startswith('/api/') or not self._admin(consulta):
                    return self._enviar(404, {'error': 'no existe'}) if not url.path.startswith('/api/') else None
                # Lo que vive en la PC 4 no detiene el panel mientras responde (el análisis con IA tarda).
                if url.path == '/api/yo':
                    return self._enviar(200, self.usuario)
                if url.path == '/api/cuentas':
                    with app.candado:
                        return self._enviar(200, app.cuentas_estado())
                if url.path == '/api/inventario':
                    return self._enviar(200, app.bandeja.inventario())
                if url.path == '/api/analisis_pc4':
                    return self._enviar(200, app.bandeja.analisis_pc4(consulta.get('ia', [''])[0] == '1'))
                if url.path == '/api/respaldo':
                    return self._enviar(200, {'aviso': app.bandeja.respaldo_aviso, 'conectado': bool(app.bandeja.cerebro)})
                if url.path == '/api/trabajos':
                    return self._enviar(200, app.bandeja.trabajos_pc4())
                if url.path == '/api/por_confirmar':
                    return self._enviar(200, app.bandeja.por_confirmar())
                if url.path == '/api/alumno':
                    return self._enviar(200, app.bandeja.alumno_pc4(consulta.get('curp', [''])[0]))
                if url.path == '/api/pdf':  # Un PDF de C:\SIDP\Expedientes, para verlo en la ventana.
                    return self._enviar(200, app.bandeja.pdf(consulta.get('ruta', [''])[0]), 'application/pdf')
                if url.path == '/api/etiquetas':  # Página para imprimir las etiquetas con código de barras.
                    pedidos = [c for c in consulta.get('codigos', [''])[0].upper().split(',') if c]
                    piezas = {p['codigo']: p for p in app.bandeja.inventario()['piezas']}
                    return self._enviar(200, codigo_barras.hoja_etiquetas([piezas[c] for c in pedidos if c in piezas]).encode(),
                                        'text/html; charset=utf-8')
                with app.candado:
                    if url.path == '/api/estado':
                        return self._enviar(200, app.bandeja.estado())
                    if url.path == '/api/expediente':
                        return self._enviar(200, app.bandeja.detalle(consulta.get('id', [''])[0]))
                    if url.path == '/api/base':
                        return self._enviar(200, app.bandeja.base())
                    if url.path == '/api/curps':
                        return self._enviar(200, app.bandeja.curps())
                    if url.path == '/api/configuracion':
                        return self._enviar(200, app.estado_configuracion())
                    if url.path == '/api/plantillas':
                        return self._enviar(200, app.bandeja.lista_plantillas())
                    if url.path == '/api/grupos':
                        return self._enviar(200, app.bandeja.grupos_lista())
                    if url.path == '/api/grupo':
                        return self._enviar(200, app.bandeja.grupo_alumnos(consulta.get('id', [''])[0]))
                    if url.path == '/api/buscar_alumno':
                        return self._enviar(200, app.bandeja.buscar_alumno(consulta.get('nombre', [''])[0], consulta.get('curp', [''])[0]))
                    if url.path == '/api/analisis':
                        return self._enviar(200, app.bandeja.analisis())
                    if url.path == '/api/exportar':
                        return self._descargar(*app.bandeja.exportar(consulta.get('que', [''])[0], consulta.get('formato', ['xlsx'])[0]))
                    if url.path == '/api/plantillas/muestra':
                        ruta = app.bandeja.plantilla_muestra(consulta.get('clave', [''])[0], consulta.get('archivo', [''])[0])
                        return self._enviar(200, ruta.read_bytes(), mimetypes.guess_type(ruta.name)[0] or 'application/octet-stream')
                    if url.path == '/api/escaneo/pagina':
                        ruta = app.bandeja.escaneo_pagina(consulta.get('lote', [''])[0], consulta.get('archivo', [''])[0])
                        return self._enviar(200, ruta.read_bytes(), mimetypes.guess_type(ruta.name)[0] or 'application/octet-stream')
                    if url.path == '/api/archivo':
                        carpeta = app.bandeja._carpeta(consulta.get('id', [''])[0])
                        nombre = Path(consulta.get('nombre', [''])[0]).name
                        archivo = carpeta / nombre
                        if not nombre or not archivo.is_file() or archivo.suffix == '.json':
                            return self._enviar(404, {'error': 'no existe'})
                        return self._enviar(200, archivo.read_bytes(), mimetypes.guess_type(nombre)[0] or 'application/octet-stream')
                self._enviar(404, {'error': 'no existe'})
            except ErrorBandeja as error:
                self._enviar(400, {'error': str(error)})

        def do_POST(self):
            url = urlparse(self.path)
            app.ultimo_cambio = time.time()
            try:
                if url.path == '/api/padres/enviar':
                    captura, archivos = leer_formulario(self.headers.get('Content-Type', ''), self._cuerpo())
                    with app.candado:
                        return self._enviar(200, app.bandeja.recibir(captura, archivos))
                if url.path == '/api/cerebro/analisis':
                    if self._cerebro():
                        destino = app.carpeta / 'analisis'
                        destino.mkdir(exist_ok=True)
                        archivo = destino / f'{datetime.datetime.now():%Y-%m-%d_%H%M%S}.md'
                        archivo.write_bytes(self._cuerpo()[:1024 * 1024])
                        self._enviar(200, {'guardado': archivo.name})
                    return
                if url.path == '/api/apagar':  # SIDP.exe --apagar, desde esta misma PC.
                    if clave_apagar and self._local() and secrets.compare_digest(self.headers.get('X-SIDP-Apagar', ''), clave_apagar):
                        self._enviar(200, {'apagado': True})
                        threading.Thread(target=servidor.shutdown, daemon=True).start()
                    else:
                        self._enviar(403, {'error': 'no permitido'})
                    return
                if url.path == '/api/entrar':  # Desde otra PC: usuario y contraseña de Ajustes > Cuentas.
                    datos = json.loads(self._cuerpo() or b'{}')
                    with app.candado:
                        token = app.cuentas.entrar(datos.get('usuario', ''), datos.get('contrasena', ''))
                        return self._enviar(200, {'token': token, 'usuario': app.cuentas.sesion(token)})
                if url.path == '/api/salir':
                    with app.candado:
                        app.cuentas.salir(self.headers.get('X-SIDP-Token', ''))
                    return self._enviar(200, {'ok': True})
                if not self._admin():
                    return
                if url.path == '/api/cerebro/buscar':  # Plan de emergencia: encontrar a la PC 4 aunque haya cambiado de IP.
                    from validacion import escritorio
                    guardada = app.configuracion.get('cerebro_url')
                    encontrados = escritorio.buscar_cerebro(guardada)
                    return self._enviar(200, {'encontrados': encontrados, 'diagnostico': escritorio.diagnostico(guardada)})
                if url.path == '/api/escaneo/leer':  # Escaneos de un alumno ya revisado en papel.
                    archivos = leer_archivos(self.headers.get('Content-Type', ''), self._cuerpo())
                    with app.candado:
                        return self._enviar(200, app.bandeja.escaneo_leer(archivos))
                if url.path == '/api/listas/leer':  # La lista de un grupo: escaneada (archivos) o escrita (campo "captura").
                    datos, archivos = leer_formulario(self.headers.get('Content-Type', ''), self._cuerpo())
                    with app.candado:
                        return self._enviar(200, app.bandeja.lista_leer([(n, c) for _, n, c in archivos], datos.get('texto', ''),
                                                                        datos.get('apellidos_primero', True) is not False))
                if url.path == '/api/plantillas/leer':  # Muestras de un documento: se proponen sus textos fijos.
                    archivos = leer_archivos(self.headers.get('Content-Type', ''), self._cuerpo())
                    with app.candado:
                        return self._enviar(200, app.bandeja.plantilla_leer(archivos))
                if url.path == '/api/plantillas/campos':  # Una muestra: el modelo que ve de la PC 4 propone sus campos.
                    archivos = leer_archivos(self.headers.get('Content-Type', ''), self._cuerpo())
                    if not archivos:
                        raise ErrorBandeja('Sube una muestra del documento')
                    return self._enviar(200, app.bandeja.campos_proponer(*archivos[0]))
                if url.path == '/api/plantillas/guardar':  # Los datos de la plantilla (campo "captura") y sus muestras.
                    datos, archivos = leer_formulario(self.headers.get('Content-Type', ''), self._cuerpo())
                    with app.candado:
                        return self._enviar(200, app.bandeja.plantilla_guardar(datos, [(n, c) for _, n, c in archivos]))
                if url.path == '/api/renapo/constancia':  # El PDF tal cual, arrastrado al panel.
                    contenido = self._cuerpo()
                    with app.candado:
                        return self._enviar(200, app.bandeja.constancia_renapo(self.headers.get('X-SIDP-Nombre', ''), contenido))
                datos = json.loads(self._cuerpo() or b'{}')
                if url.path == '/api/inventario/alta':
                    return self._enviar(200, app.bandeja.inventario_alta(datos))
                if url.path == '/api/dato/confirmar':
                    return self._enviar(200, app.bandeja.dato_confirmar(datos))
                if url.path == '/api/dato/agregar':
                    return self._enviar(200, app.bandeja.dato_agregar(datos))
                if url.path in ('/api/alumno/baja', '/api/alumno/borrar'):
                    with app.candado:
                        return self._enviar(200, app.bandeja.alumno_baja(datos, borrar=url.path.endswith('borrar')))
                if url.path == '/api/inventario/cambiar':
                    return self._enviar(200, app.bandeja.inventario_cambiar(datos))
                if url.path == '/api/respaldo':
                    return self._enviar(200, app.bandeja.respaldar())
                quien = 'administrador' if self.usuario.get('local') else self.usuario['nombre']
                with app.candado:
                    if url.path == '/api/cuentas/crear':
                        app.cuentas.crear(datos, actor=self.usuario['id'] or 'servidor')
                        return self._enviar(200, app.cuentas_estado())
                    if url.path == '/api/cuentas/estado':
                        app.cuentas.cambiar_estado(datos.get('id', ''), bool(datos.get('activo')), self.usuario['id'] or 'servidor')
                        return self._enviar(200, app.cuentas_estado())
                    if url.path == '/api/revisar_todo':
                        return self._enviar(200, app.bandeja.revisar_todo())
                    if url.path == '/api/decidir':
                        return self._enviar(200, app.bandeja.decidir(datos.get('id', ''), datos.get('decision', ''), datos.get('motivo', ''), quien))
                    if url.path == '/api/escaneo/guardar':
                        return self._enviar(200, app.bandeja.escaneo_guardar(datos.get('lote', ''), datos, quien))
                    if url.path == '/api/escaneo/descartar':
                        return self._enviar(200, app.bandeja.escaneo_descartar(datos.get('lote', '')))
                    if url.path == '/api/listas/guardar':
                        return self._enviar(200, app.bandeja.lista_guardar(datos))
                    if url.path == '/api/listas/traer':
                        return self._enviar(200, app.bandeja.lista_traer())
                    if url.path == '/api/grupos/ubicar':
                        return self._enviar(200, app.bandeja.ubicar_alumno(datos.get('alumno_id'), datos.get('grupo_id'), datos.get('mismo_que')))
                    if url.path == '/api/grupos/crear':
                        return self._enviar(200, app.bandeja.grupo_crear(datos.get('grado'), datos.get('letra')))
                    if url.path == '/api/plantillas/activa':
                        return self._enviar(200, app.bandeja.plantilla_activa(datos.get('clave', ''), datos.get('activa')))
                    if url.path == '/api/renapo/no_encontrada':
                        return self._enviar(200, app.bandeja.renapo_no_encontrada(datos.get('alumno', '')))
                    if url.path == '/api/configuracion':
                        problema = app.configurar(datos.get('cerebro_url'), datos.get('cerebro_clave'))
                        return self._enviar(200, app.estado_configuracion(problema))
                self._enviar(404, {'error': 'no existe'})
            except ErrorCuenta as error:
                self._enviar(400, {'error': str(error)})
            except (ErrorBandeja, ValueError) as error:
                self._enviar(400, {'error': str(error)})

        def log_message(self, formato, *args):  # Sin datos de los padres en la ventana.
            print(f'{self.client_address[0]} {formato % args}', flush=True)

    servidor = ThreadingHTTPServer((anfitrion, app.puerto), Manejador)
    return servidor


def leer_formulario(tipo, cuerpo):
    """Formulario multipart de la página de padres: (captura, [(espacio, nombre, contenido)])."""
    if not tipo.startswith('multipart/form-data'):
        raise ErrorBandeja('Se esperaba un formulario con archivos')
    mensaje = BytesParser(policy=politica_correo).parsebytes(f'Content-Type: {tipo}\r\n\r\n'.encode() + cuerpo)
    captura, archivos = None, []
    for parte in mensaje.iter_parts():
        campo = parte.get_param('name', header='content-disposition')
        if campo == 'captura':
            captura = json.loads(parte.get_content())
        elif parte.get_filename():
            archivos.append((campo, parte.get_filename(), parte.get_payload(decode=True) or b''))
    if captura is None:
        raise ErrorBandeja('Faltan los datos del formulario')
    return captura, archivos


def leer_archivos(tipo, cuerpo):
    """Solo los archivos de un formulario multipart: [(nombre, contenido)]."""
    if not tipo.startswith('multipart/form-data'):
        raise ErrorBandeja('Se esperaba un formulario con archivos')
    mensaje = BytesParser(policy=politica_correo).parsebytes(f'Content-Type: {tipo}\r\n\r\n'.encode() + cuerpo)
    return [(parte.get_filename(), parte.get_payload(decode=True) or b'') for parte in mensaje.iter_parts() if parte.get_filename()]


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='SIDP-Validador')
    parser.add_argument('carpeta', nargs='?', type=Path, default=carpeta_por_omision(), help='Dónde se guardan los expedientes')
    parser.add_argument('--puerto', type=int, default=PUERTO)
    parser.add_argument('--cerebro', help='Dirección del cerebro de la PC 4, por ejemplo http://192.168.1.40:8771')
    parser.add_argument('--clave', default='', help='Clave que muestra el cerebro al arrancar')
    parser.add_argument('--hoy', type=datetime.date.fromisoformat, default=None)
    parser.add_argument('--sin-modelo', action='store_true', help='Sin cerebro ni modelo: solo procesos en esta PC')
    parser.add_argument('--revisar', action='store_true', help='Revisa la carpeta, imprime el resumen y sale (sin ventana)')
    parser.add_argument('--no-abrir', action='store_true', help='No abrir el navegador')
    args = parser.parse_args(argumentos)

    carpeta = args.carpeta.resolve()
    if prueba.dentro_de_repositorio(carpeta) and any(
            a.suffix.lower() in prueba.DOCUMENTOS_REALES for a in (carpeta / 'expedientes').glob('*/*')):
        print('La carpeta tiene PDF o fotos y está dentro de un repositorio de Git. Usa una carpeta fuera del repositorio.')
        return 2
    app = Aplicacion(carpeta, args.hoy, args.puerto, not args.sin_modelo)
    if args.cerebro:
        problema = app.configurar(args.cerebro, args.clave)
        print(f'Cerebro {args.cerebro}: {"conectado" if not problema else "no respondió: " + problema}')
    if args.revisar:
        estado = app.bandeja.revisar_todo()
        print(json.dumps(estado['medidas'], ensure_ascii=False, indent=1))
        return 0 if estado['medidas']['falsos_pasaron'] == 0 else 1
    servidor = crear_servidor(app)
    panel = f'http://127.0.0.1:{args.puerto}/'
    print(f'SIDP-Validador · carpeta {carpeta}')
    print(f'Panel del administrador: {panel}')
    print(f'Página de padres (misma red): {app.direccion_padres()}')
    print('Cierra esta ventana para apagarlo.', flush=True)
    if not args.no_abrir:
        threading.Timer(1.0, webbrowser.open, (panel,)).start()
    threading.Thread(target=respaldar_seguido, args=(app,), daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
