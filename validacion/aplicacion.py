"""SIDP-Validador.exe: la PC del administrador en el entorno de pruebas.

Guarda los expedientes (archivos sin sobrescribir y datos en SQLite con las 39 tablas),
manda cada uno al cerebro de la PC 4 para que lo valide por IP y muestra el panel donde una
persona autoriza o rechaza. También sirve la página de padres a la red local.

- Panel del administrador: http://127.0.0.1:8770/ (solo desde esta PC).
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
import webbrowser
from email.parser import BytesParser
from email.policy import default as politica_correo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from validacion import cerebro_red, prueba
from validacion.registro import Registro
from validacion.servicio import Bandeja, ErrorBandeja

RAIZ = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
INTERFAZ = RAIZ / 'validacion' / 'interfaz'
PUERTO = 8770
MAXIMO_ENVIO = 100 * 1024 * 1024
ESTATICOS = {'/estilo.css': 'estilo.css', '/motor.js': 'motor.js'}
LOCALES = ('127.0.0.1', '::1')


def carpeta_por_omision():
    return Path.home() / 'SIDP-prueba'


class Aplicacion:
    def __init__(self, carpeta, hoy=None, puerto=PUERTO, usar_modelo=True):
        self.carpeta = Path(carpeta).resolve()
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(16)  # Sin él, otra página del navegador no puede usar el panel.
        self.puerto = puerto
        self.candado = threading.Lock()
        self.bandeja = Bandeja(self.carpeta, hoy, usar_modelo=usar_modelo, registro=Registro(self.carpeta / 'plataforma_prueba.db'))
        self.archivo_configuracion = self.carpeta / 'configuracion.json'
        self.configuracion = {}
        if self.archivo_configuracion.exists():
            self.configuracion = json.loads(self.archivo_configuracion.read_text(encoding='utf-8'))
            self.bandeja.conectar_cerebro(self.configuracion.get('cerebro_url'), self.configuracion.get('cerebro_clave', ''))

    def configurar(self, url, clave):
        problema = self.bandeja.conectar_cerebro((url or '').strip(), (clave or '').strip())
        self.configuracion = {'cerebro_url': (url or '').strip(), 'cerebro_clave': (clave or '').strip()}
        self.archivo_configuracion.write_text(json.dumps(self.configuracion), encoding='utf-8')
        return problema

    def datos_para_cerebro(self):
        """Lo extraído y decidido, sin archivos: lo que el cerebro necesita para el análisis."""
        decisiones = self.bandeja.decisiones()
        return [{'id': i, 'estado': r['estado'], 'reglas': sorted({h['regla'] for h in r['hallazgos']} | {g['regla'] for g in r['grises']}
                                                                    | {n['regla'] for n in r['no_leidos']}),
                 'extraidos': r.get('extraidos', {}), 'documentos': r.get('documentos', {}), 'decision': decisiones.get(i)}
                for i, r in self.bandeja.resultados.items()]

    def pagina(self, nombre):
        config = {'modo': 'local', 'token': self.token if nombre == 'panel.html' else ''}
        texto = (INTERFAZ / nombre).read_text(encoding='utf-8')
        return texto.replace('/*SIDP_CONFIG*/', f'window.SIDP = {json.dumps(config)};').encode()

    def direccion_padres(self):
        return f'http://{cerebro_red.ip_local()}:{self.puerto}/padres'


def crear_servidor(aplicacion, anfitrion='0.0.0.0'):
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

        def _local(self):
            return self.client_address[0] in LOCALES

        def _admin(self, consulta=None):
            """El panel solo se usa desde esta PC y con el token que se le dio al abrirlo."""
            token = self.headers.get('X-SIDP-Token') or (consulta or {}).get('t', [''])[0]
            if self._local() and secrets.compare_digest(token, app.token):
                return True
            self._enviar(403, {'error': 'El panel solo se abre en la PC del administrador'})
            return False

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
                    if not self._local():
                        return self._enviar(403, b'El panel solo se abre en la PC del administrador. Padres: /padres', 'text/plain; charset=utf-8')
                    return self._enviar(200, app.pagina('panel.html'), 'text/html; charset=utf-8')
                if url.path in ('/padres', '/padres.html'):
                    return self._enviar(200, app.pagina('padres.html'), 'text/html; charset=utf-8')
                if url.path in ESTATICOS:
                    nombre = ESTATICOS[url.path]
                    return self._enviar(200, (INTERFAZ / nombre).read_bytes(), mimetypes.guess_type(nombre)[0] + '; charset=utf-8')
                if url.path == '/api/cerebro/datos':
                    if self._cerebro():
                        with app.candado:
                            self._enviar(200, {'expedientes': app.datos_para_cerebro()})
                    return
                if not url.path.startswith('/api/') or not self._admin(consulta):
                    return self._enviar(404, {'error': 'no existe'}) if not url.path.startswith('/api/') else None
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
                        return self._enviar(200, {**app.configuracion, 'cerebro_conectado': bool(app.bandeja.cerebro),
                                                  'direccion_padres': app.direccion_padres()})
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
                if not self._admin():
                    return
                if url.path == '/api/escaneo/leer':  # Escaneos de un alumno ya revisado en papel.
                    archivos = leer_archivos(self.headers.get('Content-Type', ''), self._cuerpo())
                    with app.candado:
                        return self._enviar(200, app.bandeja.escaneo_leer(archivos))
                if url.path == '/api/renapo/constancia':  # El PDF tal cual, arrastrado al panel.
                    contenido = self._cuerpo()
                    with app.candado:
                        return self._enviar(200, app.bandeja.constancia_renapo(self.headers.get('X-SIDP-Nombre', ''), contenido))
                datos = json.loads(self._cuerpo() or b'{}')
                with app.candado:
                    if url.path == '/api/revisar_todo':
                        return self._enviar(200, app.bandeja.revisar_todo())
                    if url.path == '/api/decidir':
                        return self._enviar(200, app.bandeja.decidir(datos.get('id', ''), datos.get('decision', ''), datos.get('motivo', '')))
                    if url.path == '/api/escaneo/guardar':
                        return self._enviar(200, app.bandeja.escaneo_guardar(datos.get('lote', ''), datos))
                    if url.path == '/api/escaneo/descartar':
                        return self._enviar(200, app.bandeja.escaneo_descartar(datos.get('lote', '')))
                    if url.path == '/api/renapo/no_encontrada':
                        return self._enviar(200, app.bandeja.renapo_no_encontrada(datos.get('alumno', '')))
                    if url.path == '/api/configuracion':
                        problema = app.configurar(datos.get('cerebro_url'), datos.get('cerebro_clave'))
                        return self._enviar(200, {**app.configuracion, 'cerebro_conectado': bool(app.bandeja.cerebro), 'problema': problema,
                                                  'direccion_padres': app.direccion_padres()})
                self._enviar(404, {'error': 'no existe'})
            except (ErrorBandeja, ValueError) as error:
                self._enviar(400, {'error': str(error)})

        def log_message(self, formato, *args):  # Sin datos de los padres en la ventana.
            print(f'{self.client_address[0]} {formato % args}', flush=True)

    return ThreadingHTTPServer((anfitrion, app.puerto), Manejador)


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
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
