"""Creación de una instalación nueva en el servidor y alta de equipos (enrolamiento)."""
import time
import uuid
import httpx
from comun import configuracion, descubrimiento, firma, red, rutas
from comun.configuracion import Credencial, Nodo, Paquete
from contratos.v1 import SolicitudIngreso
from sidp.errores import ErrorInstalacion


def crear(nombre, puerto=configuracion.PUERTO_PLATAFORMA, tls=True, con_agente=True, equipo=None):
    """Primera ejecución en el servidor: paquete, certificado, base, operador y agente local."""
    from backend.main import preparar
    from backend.modulos.identidad import servicio
    from sidp import certificados

    if configuracion.ruta_paquete().exists():
        raise ErrorInstalacion(f'Ya existe una instalación en {rutas.hogar()}; no se sobrescribe')
    equipo = equipo or configuracion.nombre_equipo()
    certificado = certificados.generar(rutas.datos_plataforma() / 'tls', nombre) if tls else None
    paquete = Paquete(instalacion=str(uuid.uuid4()), nombre=nombre, secreto=firma.nuevo_secreto(),
                      certificado=certificado, puerto=puerto)
    ctx = preparar(paquete=paquete)
    url_local = f'{paquete.esquema}://127.0.0.1:{puerto}'
    token_operador = firma.nuevo_token()
    servicio.crear_directa(ctx.bd, equipo, 'admin', token_operador, identificador='operador')
    Credencial('operador', token_operador, url_local).guardar('admin')
    roles = ['plataforma']
    if con_agente:
        token = firma.nuevo_token()
        identificador = servicio.crear_directa(ctx.bd, equipo, 'agente', token)
        Credencial(identificador, token, url_local).guardar('agente')
        roles.append('agente')
    Nodo(equipo=equipo, roles=roles, url=url_local).guardar()
    paquete.guardar(configuracion.ruta_paquete())  # Último paso: marca la instalación como completa.
    return {'paquete': paquete, 'token_operador': token_operador, 'roles': roles,
            'huella': certificados.huella(certificado) if certificado else None}


def localizar(paquete, url=None):
    url = url or paquete.url or descubrimiento.buscar(paquete)
    if not url:
        raise ErrorInstalacion('No se encontró la plataforma en la red. Verifique que el servidor esté '
                               'encendido o indique la dirección con --url https://IP:PUERTO')
    try:
        with red.cliente(url, paquete=paquete, timeout=5) as cliente:
            cliente.get('/api/v1/sistema/latido').raise_for_status()
    except httpx.HTTPError as error:
        raise ErrorInstalacion(f'{url} no responde como plataforma de esta instalación: {error}') from error
    return url


def solicitar(paquete, url, equipo, rol, invitacion=None):
    """Pide identidad para un rol. El token se genera y queda en este equipo."""
    credencial = Credencial.cargar(rol)
    if not credencial or credencial.url is None:
        credencial = Credencial(f'{equipo}-{rol}', firma.nuevo_token(), url)
        credencial.guardar(rol)  # Antes de enviar: reintentar reutiliza el mismo token.
    datos = SolicitudIngreso(instalacion=paquete.instalacion, equipo=equipo, rol=rol,
                             token_resumen=firma.resumen_token(credencial.token), sello=int(time.time()),
                             invitacion=invitacion, prueba='0' * 64)
    datos.prueba = firma.firmar(paquete.secreto, datos.firmable())
    with red.cliente(url, paquete=paquete) as cliente:
        respuesta = cliente.post('/api/v1/enrolamiento/solicitud', json=datos.model_dump())
    if respuesta.status_code >= 400:
        raise ErrorInstalacion(f'Solicitud de {rol} rechazada ({respuesta.status_code}): '
                               f'{respuesta.json().get("detail", respuesta.text)}', respuesta.status_code)
    resultado = respuesta.json()
    credencial.identidad, credencial.url = resultado['id'], url
    credencial.guardar(rol)
    return resultado


def estado(paquete, rol):
    credencial = Credencial.cargar(rol)
    if not credencial:
        return None
    with red.cliente(credencial.url, credencial.token, paquete, timeout=5) as cliente:
        respuesta = cliente.get('/api/v1/enrolamiento/estado')
    return respuesta.json()['estado'] if respuesta.status_code == 200 else 'desconocida'


def unirse(paquete, roles, equipo=None, url=None, invitacion=None, esperar=True, aviso=None, pausa=5):
    aviso = aviso or (lambda texto: print(texto, flush=True))
    url = localizar(paquete, url)
    aviso(f'Plataforma "{paquete.nombre}" encontrada en {url}')
    # Nombre automático ocupado (equipos clonados con el mismo nombre): probar un sufijo.
    candidatos = [equipo] if equipo else [configuracion.nombre_equipo()[:37] + s for s in ('', '-2', '-3', '-4')]
    for indice, rol in enumerate(r for r in roles if r != 'plataforma'):
        for candidato in candidatos:
            try:
                resultado = solicitar(paquete, url, candidato, rol, invitacion)
                break
            except ErrorInstalacion as error:
                if error.codigo != 409 or indice or candidato == candidatos[-1]:
                    raise
        candidatos = [candidato]
        aviso(f'  {rol}: identidad {resultado["id"]} -> {resultado["estado"]}')
    equipo = candidatos[0]
    Nodo(equipo=equipo, roles=list(roles), url=url).guardar()
    if not esperar:
        return
    avisado = False
    while True:
        estados = {rol: estado(paquete, rol) for rol in roles if rol != 'plataforma'}
        if all(e == 'aprobada' for e in estados.values()):
            aviso('Equipo autorizado.')
            return
        if any(e == 'revocada' for e in estados.values()):
            raise ErrorInstalacion('La solicitud fue revocada por el administrador')
        if not avisado:
            aviso('Esperando aprobación. En el servidor ejecute: sidp identidades aprobar <identidad>')
            avisado = True
        time.sleep(pausa)
