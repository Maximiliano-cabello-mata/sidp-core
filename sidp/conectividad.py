"""Prueba de conectividad entre equipos: red, TLS, reloj, credenciales e ida y vuelta.

Se ejecuta en cualquier equipo. En el servidor (credencial admin) además envía una tarea
dirigida a cada agente remoto y espera su resultado: prueba de punta a punta de que el
otro equipo recibe trabajo de la plataforma y devuelve resultados confirmados.
"""
import email.utils
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import uuid
from datetime import datetime
import httpx
from comun import configuracion, descubrimiento, red, rutas
from comun.configuracion import Credencial, Nodo

EN_LINEA_S = 120
MARCAS = {'ok': '[ OK  ]', 'aviso': '[AVISO]', 'falla': '[FALLA]'}


class Informe:
    def __init__(self, aviso=None):
        self.pruebas = []
        self.aviso = aviso or (lambda texto: print(texto, flush=True))

    def agregar(self, nombre, estado, detalle):
        self.pruebas.append({'prueba': nombre, 'estado': estado, 'detalle': detalle})
        self.aviso(f'{MARCAS[estado]} {nombre:<30} {detalle}')

    @property
    def pasa(self):
        return all(p['estado'] != 'falla' for p in self.pruebas)

    def cerrar(self):
        avisos = sum(p['estado'] == 'aviso' for p in self.pruebas)
        self.aviso(f'\nRESULTADO: {"PASA" if self.pasa else "FALLA"} '
                   f'({len(self.pruebas)} pruebas, {avisos} avisos)')
        ruta = rutas.carpeta('registros') / f'conectividad-{datetime.now():%Y%m%d-%H%M%S}.json'
        configuracion.escribir_json(ruta, {'fecha': time.time(), 'pasa': self.pasa, 'pruebas': self.pruebas})
        self.aviso(f'Informe guardado en {ruta}')
        return 0 if self.pasa else 1


def _ms(inicio):
    return round((time.perf_counter() - inicio) * 1000)


def _estado_credencial(cliente, token):
    respuesta = cliente.get('/api/v1/enrolamiento/estado', headers={'Authorization': f'Bearer {token}'})
    return respuesta.json().get('estado', 'desconocida') if respuesta.status_code == 200 else 'desconocida'


def ida_y_vuelta(cliente, destino, espera):
    """Tarea dirigida a un agente concreto; devuelve segundos hasta confirmarse o un error."""
    mensaje = f'conectividad {destino} {uuid.uuid4()}'
    tarea = {'clave': f'conectividad-{destino}-{uuid.uuid4().hex[:12]}', 'mensaje': mensaje, 'destino': destino}
    inicio = time.monotonic()
    respuesta = cliente.post('/api/v1/tareas', json=tarea)
    respuesta.raise_for_status()
    identificador = respuesta.json()['id']
    while time.monotonic() - inicio < espera:
        estado = cliente.get(f'/api/v1/tareas/{identificador}').json()
        if estado['estado'] == 'completada':
            if estado['resultado'] != mensaje:
                return None, 'el resultado no coincide con lo enviado'
            return time.monotonic() - inicio, None
        if estado['estado'] == 'fallida':
            return None, 'la tarea agotó sus intentos'
        time.sleep(1)
    return None, f'sin respuesta en {espera} s (¿agente encendido y aprobado?)'


def ejecutar(url=None, equipos=None, espera=90, aviso=None):
    informe = Informe(aviso)
    paquete = configuracion.cargar_paquete()
    nodo = Nodo.cargar()
    if not paquete:
        informe.agregar('Paquete de instalacion', 'falla', f'no hay instalacion.json en {rutas.hogar()} ni junto al .exe')
        return informe
    informe.agregar('Paquete de instalacion', 'ok', f'"{paquete.nombre}" ({paquete.instalacion[:8]})')
    if nodo:
        informe.agregar('Este equipo', 'ok', f'{nodo.equipo}, roles: {", ".join(nodo.roles)}')

    inicio = time.perf_counter()
    encontrada = descubrimiento.buscar(paquete, espera=3)
    if encontrada:
        informe.agregar('Descubrimiento UDP', 'ok', f'{encontrada} ({_ms(inicio)} ms)')
    else:
        informe.agregar('Descubrimiento UDP', 'aviso', f'sin respuesta en UDP {paquete.puerto_descubrimiento}; '
                        'se usa la URL guardada (revise cortafuegos o use --url)')
    url = url or (nodo.url if nodo else None) or encontrada or paquete.url
    if not url:
        informe.agregar('Direccion de la plataforma', 'falla', 'desconocida: use --url https://IP:PUERTO')
        return informe
    destino = httpx.URL(url)

    inicio = time.perf_counter()
    try:
        socket.create_connection((destino.host, destino.port or 443), timeout=3).close()
        informe.agregar('Puerto TCP', 'ok', f'{destino.host}:{destino.port} abierto ({_ms(inicio)} ms)')
    except OSError as error:
        informe.agregar('Puerto TCP', 'falla', f'{destino.host}:{destino.port} inaccesible: {error}. '
                        'Servidor apagado o cortafuegos (sidp cortafuegos en el servidor)')
        return informe

    try:
        cliente = red.cliente(url, paquete=paquete, timeout=5)
    except ValueError as error:
        informe.agregar('Direccion de la plataforma', 'falla', f'{url}: {error}')
        return informe
    with cliente:
        tiempos, respuesta = [], None
        try:
            for _ in range(5):
                inicio = time.perf_counter()
                respuesta = cliente.get('/api/v1/sistema/latido')
                respuesta.raise_for_status()
                tiempos.append(_ms(inicio))
        except (ssl.SSLError, httpx.ConnectError) as error:
            causa = 'el certificado no es el de esta instalación' if 'CERTIFICATE' in str(error) else str(error)
            informe.agregar('HTTPS con certificado fijado', 'falla', causa)
            return informe
        except httpx.HTTPError as error:
            informe.agregar('HTTPS con certificado fijado', 'falla', f'{url} no responde como plataforma SIDP: {error}')
            return informe
        lento = max(tiempos) > 500
        informe.agregar('HTTPS con certificado fijado', 'aviso' if lento else 'ok',
                        f'latencia min/prom/max {min(tiempos)}/{sum(tiempos) // len(tiempos)}/{max(tiempos)} ms')

        fecha = respuesta.headers.get('date')
        if fecha:
            desfase = abs(email.utils.parsedate_to_datetime(fecha).timestamp() - time.time())
            estado = 'falla' if desfase > 600 else 'aviso' if desfase > 60 else 'ok'
            informe.agregar('Reloj', estado, f'desfase con el servidor {desfase:.0f} s'
                            + (' (el alta de equipos exige < 600 s)' if estado != 'ok' else ''))

        credenciales = {rol: Credencial.cargar(rol) for rol in ('admin', 'agente', 'cerebro')}
        for rol, credencial in credenciales.items():
            if credencial:
                estado = _estado_credencial(cliente, credencial.token)
                nivel = {'aprobada': 'ok', 'pendiente': 'aviso'}.get(estado, 'falla')
                informe.agregar(f'Credencial {rol}', nivel, f'{credencial.identidad}: {estado}')
        if not any(credenciales.values()):
            informe.agregar('Credenciales', 'aviso', 'este equipo aún no se ha unido (sidp unirse)')

        admin = credenciales['admin']
        if admin:
            cliente.headers['Authorization'] = f'Bearer {admin.token}'
            _probar_equipos(informe, cliente, credenciales['agente'], equipos, espera)
        elif credenciales['agente']:
            cliente.headers['Authorization'] = f'Bearer {credenciales["agente"].token}'
            if cliente.get('/api/v1/dispositivos/politica').status_code == 200:
                informe.agregar('Agente autorizado', 'ok', 'la plataforma acepta trabajo de este equipo; '
                                'la ida y vuelta se prueba desde el servidor')
    return informe


def _probar_equipos(informe, cliente, agente_local, equipos, espera):
    ahora = time.time()
    dispositivos = {d['id']: d for d in cliente.get('/api/v1/dispositivos').json()}
    for identificador, datos in sorted(dispositivos.items()):
        edad = ahora - datos['ultimo']
        informe.agregar(f'Equipo {identificador}', 'ok' if edad < EN_LINEA_S else 'aviso',
                        f'último contacto hace {edad:.0f} s')
    local = agente_local.identidad if agente_local else None
    objetivos = equipos or [i for i, d in dispositivos.items() if i != local and ahora - d['ultimo'] < EN_LINEA_S]
    if not objetivos:
        informe.agregar('Ida y vuelta', 'aviso', 'no hay otro equipo con agente en línea; enciéndalo y repita')
        return
    for objetivo in objetivos:
        segundos, error = ida_y_vuelta(cliente, objetivo, espera)
        if error:
            informe.agregar(f'Ida y vuelta {objetivo}', 'falla', error)
        else:
            informe.agregar(f'Ida y vuelta {objetivo}', 'ok', f'tarea creada aquí, ejecutada allá y confirmada en {segundos:.1f} s')


def abrir_cortafuegos(paquete, aviso=print):
    """Reglas de entrada solo para redes privadas/dominio. Necesita consola de administrador."""
    reglas = [('SIDP plataforma', 'TCP', paquete.puerto), ('SIDP descubrimiento', 'UDP', paquete.puerto_descubrimiento)]
    if os.name != 'nt':
        for nombre, protocolo, puerto in reglas:
            aviso(f'Linux: sudo ufw allow from 192.168.0.0/16 to any port {puerto} proto {protocolo.lower()}  # {nombre}')
        return 0
    codigo = 0
    for nombre, protocolo, puerto in reglas:
        subprocess.run(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name={nombre}'], capture_output=True)
        resultado = subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule', f'name={nombre}', 'dir=in',
                                    'action=allow', f'protocol={protocolo}', f'localport={puerto}',
                                    'profile=private,domain'], capture_output=True, text=True)
        if resultado.returncode == 0:
            aviso(f'Regla "{nombre}" ({protocolo} {puerto}) creada para redes privadas y de dominio')
        else:
            codigo = 1
            aviso(f'No se pudo crear "{nombre}": ejecute la consola como administrador. {resultado.stdout.strip()}')
    aviso('La red de la escuela debe estar marcada como "Privada" en Windows (Configuración > Red).')
    return codigo


def abrir_cortafuegos_automatico(paquete, aviso=print):
    """Primer arranque del servidor: abre el cortafuegos, pidiendo permiso de administrador si hace falta."""
    if os.name != 'nt':
        return 0
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        return abrir_cortafuegos(paquete, aviso)
    if not rutas.congelado():
        aviso('Ejecute "sidp cortafuegos" en una consola de administrador para abrir el cortafuegos.')
        return 1
    aviso('Windows pedirá permiso de administrador para abrir el cortafuegos: elija "Sí".')
    # ShellExecute "runas" muestra el aviso de Control de cuentas de usuario; > 32 significa que se lanzó.
    lanzado = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, 'cortafuegos', None, 0)
    if lanzado <= 32:
        aviso('Sin permiso de administrador: las demás computadoras quizá no encuentren a esta. '
              'Puede repetirlo con "sidp cortafuegos" como administrador.')
        return 1
    return 0
