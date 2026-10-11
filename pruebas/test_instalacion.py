"""Instalación, enrolamiento, descubrimiento y TLS fijado."""
import json
import socket
import ssl
import threading
import time
import pytest
import uvicorn
from fastapi.testclient import TestClient
from backend.main import crear_app
from comun import configuracion, descubrimiento, firma, red
from comun.configuracion import Credencial, Paquete
from contratos.v1 import SolicitudIngreso
from sidp import certificados, instalacion


def puerto_libre(tipo=socket.SOCK_STREAM):
    with socket.socket(socket.AF_INET, tipo) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def solicitud(paquete, equipo='aula-1', rol='agente', token='t' * 43, invitacion=None, sello=None, secreto=None):
    datos = SolicitudIngreso(instalacion=paquete.instalacion, equipo=equipo, rol=rol,
                             token_resumen=firma.resumen_token(token), sello=sello or int(time.time()),
                             invitacion=invitacion, prueba='0' * 64)
    datos.prueba = firma.firmar(secreto or paquete.secreto, datos.firmable())
    return datos.model_dump()


@pytest.fixture
def servidor():
    resultado = instalacion.crear('Escuela de prueba', puerto=puerto_libre(), equipo='servidor')
    with TestClient(crear_app()) as cliente:
        yield cliente, resultado['paquete'], resultado['token_operador']


def test_crear_instalacion_es_unica_y_completa(servidor, hogar_aislado):
    _, paquete, _ = servidor
    assert configuracion.cargar_paquete().instalacion == paquete.instalacion
    assert configuracion.Nodo.cargar().roles == ['plataforma', 'agente']
    assert Credencial.cargar('agente').identidad == 'servidor-agente'
    assert (hogar_aislado / 'plataforma' / 'tls' / 'clave.pem').exists()
    with pytest.raises(instalacion.ErrorInstalacion):
        instalacion.crear('Otra')


def test_enrolamiento_con_aprobacion_y_revocacion(servidor):
    cliente, paquete, operador = servidor
    token = firma.nuevo_token()
    respuesta = cliente.post('/api/v1/enrolamiento/solicitud', json=solicitud(paquete, token=token))
    assert respuesta.json() == {'id': 'aula-1-agente', 'estado': 'pendiente'}
    # Repetir la misma solicitud es idempotente; otro token para la misma identidad no.
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=solicitud(paquete, token=token)).status_code == 200
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=solicitud(paquete)).status_code == 409
    agente = {'Authorization': f'Bearer {token}'}
    admin = {'Authorization': f'Bearer {operador}'}
    assert cliente.get('/api/v1/enrolamiento/estado', headers=agente).json()['estado'] == 'pendiente'
    assert cliente.post('/api/v1/tareas/reclamar', headers=agente).status_code == 401
    assert cliente.post('/api/v1/identidades/aula-1-agente/aprobar', headers=agente).status_code == 401
    assert cliente.post('/api/v1/identidades/aula-1-agente/aprobar', headers=admin).json()['estado'] == 'aprobada'
    registro = cliente.post('/api/v1/dispositivos/registro', headers=agente,
                            json={'capacidades': ['diagnostico.echo']})
    assert registro.status_code == 200
    assert cliente.post('/api/v1/identidades/aula-1-agente/revocar', headers=admin).json()['estado'] == 'revocada'
    assert cliente.post('/api/v1/tareas/reclamar', headers=agente).status_code == 401
    # Reinstalar tras revocar: nueva solicitud con nuevo token vuelve a pendiente.
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=solicitud(paquete)).json()['estado'] == 'pendiente'
    identidades = {i['id']: i['estado'] for i in cliente.get('/api/v1/identidades', headers=admin).json()}
    assert identidades == {'operador': 'aprobada', 'servidor-agente': 'aprobada', 'aula-1-agente': 'pendiente'}


def test_invitacion_de_un_solo_uso(servidor):
    cliente, paquete, operador = servidor
    codigo = cliente.post('/api/v1/invitaciones', headers={'Authorization': f'Bearer {operador}'},
                          json={'rol': 'cerebro'}).json()['codigo']
    primera = cliente.post('/api/v1/enrolamiento/solicitud',
                           json=solicitud(paquete, 'direccion', 'cerebro', firma.nuevo_token(), codigo))
    assert primera.json()['estado'] == 'aprobada'
    segunda = cliente.post('/api/v1/enrolamiento/solicitud',
                           json=solicitud(paquete, 'otra', 'cerebro', firma.nuevo_token(), codigo))
    assert segunda.status_code == 403


def test_solicitudes_ajenas_rechazadas(servidor):
    cliente, paquete, _ = servidor
    falsa = solicitud(paquete, secreto=firma.nuevo_secreto())
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=falsa).status_code == 403
    vieja = solicitud(paquete, sello=int(time.time()) - 3600)
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=vieja).status_code == 400
    otra = dict(solicitud(paquete), instalacion='otra-escuela')
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=otra).status_code == 403
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=dict(solicitud(paquete), rol='admin')).status_code == 422


def test_protocolo_de_descubrimiento():
    paquete = Paquete('inst-1', 'Escuela', firma.nuevo_secreto(), puerto=8443)
    reto = 'abc'
    mensaje = json.dumps({'sidp': 'buscar', 'instalacion': 'inst-1', 'reto': reto}).encode()
    respuesta = descubrimiento.responder(paquete, mensaje)
    assert descubrimiento.validar(paquete, reto, respuesta, '10.0.0.5') == 'http://10.0.0.5:8443'
    assert descubrimiento.validar(paquete, 'otro-reto', respuesta, '10.0.0.5') is None
    alterada = json.loads(respuesta)
    alterada['puerto'] = 9999
    assert descubrimiento.validar(paquete, reto, json.dumps(alterada).encode(), '10.0.0.5') is None
    ajena = json.dumps({'sidp': 'buscar', 'instalacion': 'otra', 'reto': reto}).encode()
    assert descubrimiento.responder(paquete, ajena) is None
    assert descubrimiento.responder(paquete, b'basura') is None


def test_descubrimiento_udp_real():
    paquete = Paquete('inst-udp', 'Escuela', firma.nuevo_secreto(), puerto=8443,
                      puerto_descubrimiento=puerto_libre(socket.SOCK_DGRAM))
    respondedor = descubrimiento.Respondedor(paquete, '127.0.0.1')
    respondedor.start()
    try:
        assert descubrimiento.buscar(paquete, espera=2, destinos=('127.0.0.1',)) == 'http://127.0.0.1:8443'
        intruso = Paquete('inst-udp', 'Impostor', firma.nuevo_secreto(), puerto_descubrimiento=paquete.puerto_descubrimiento)
        assert descubrimiento.buscar(intruso, espera=1, destinos=('127.0.0.1',)) is None
    finally:
        respondedor.detener()


def test_tls_fijado_y_enrolamiento_por_red(hogar_aislado):
    resultado = instalacion.crear('Escuela TLS', puerto=puerto_libre(), equipo='servidor')
    paquete = resultado['paquete']
    tls = hogar_aislado / 'plataforma' / 'tls'
    servidor = uvicorn.Server(uvicorn.Config(crear_app(), host='127.0.0.1', port=paquete.puerto, log_config=None,
                                             ssl_certfile=str(tls / 'certificado.pem'), ssl_keyfile=str(tls / 'clave.pem')))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    try:
        while not servidor.started:
            time.sleep(0.05)
        url = f'https://127.0.0.1:{paquete.puerto}'
        with red.cliente(url, paquete=paquete) as cliente:
            assert cliente.get('/api/v1/sistema/latido').status_code == 200
        impostor = Paquete.desde({**paquete.__dict__, 'certificado': certificados.generar(hogar_aislado / 'x', 'x')})
        with red.cliente(url, paquete=impostor) as cliente, pytest.raises(Exception, match='CERTIFICATE_VERIFY_FAILED'):
            cliente.get('/api/v1/sistema/latido')
        # Equipo nuevo: se une sin esperar y queda pendiente con su credencial guardada.
        (hogar_aislado / 'credenciales' / 'agente.json').unlink()
        instalacion.unirse(paquete, ['agente'], equipo='aula-9', url=url, esperar=False, aviso=lambda _: None)
        assert instalacion.estado(paquete, 'agente') == 'pendiente'
        assert Credencial.cargar('agente').identidad == 'aula-9-agente'
    finally:
        servidor.should_exit = True
        hilo.join(5)


def test_contexto_tls_rechaza_pem_invalido():
    with pytest.raises(ssl.SSLError):
        red.contexto_tls('-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n')


def test_supervisor_espera_tras_error_de_credencial(monkeypatch):
    import sys
    from sidp import supervisor
    monkeypatch.setattr(supervisor, 'comando', lambda rol: [sys.executable, '-c', 'import sys; sys.exit(3)'])
    proceso = supervisor.Proceso('agente')
    proceso.revisar(0)
    proceso.hijo.wait(10)
    proceso.revisar(1)
    assert proceso.hijo is None and proceso.proximo == 1 + supervisor.ESPERA_MAXIMA
