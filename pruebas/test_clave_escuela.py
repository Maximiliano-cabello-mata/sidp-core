"""Alta automática con clave de escuela (ADR-025): mismo sidp.exe, sin USB ni invitaciones."""
import os
import socket
import threading
import time
import pytest
import uvicorn
from fastapi.testclient import TestClient
from backend.main import crear_app
from comun import configuracion, descubrimiento, firma, rutas
from comun.configuracion import Credencial, Nodo, Paquete
from sidp import automatico, instalacion
from sidp.errores import ErrorInstalacion
from pruebas.test_instalacion import puerto_libre, solicitud

CLAVE = 'Primaria Delfino 2026'


def test_clave_deriva_la_misma_instalacion_en_cualquier_equipo():
    assert firma.derivar_clave(CLAVE) == firma.derivar_clave('  primaria   delfino 2026 ')
    assert firma.derivar_clave(CLAVE) != firma.derivar_clave('Primaria Delfino 2027')
    with pytest.raises(ValueError):
        firma.derivar_clave('corta')


@pytest.fixture
def servidor_con_clave():
    resultado = instalacion.crear('Escuela con clave', puerto=puerto_libre(), equipo='servidor', clave=CLAVE)
    with TestClient(crear_app()) as cliente:
        yield cliente, resultado['paquete']


def test_quien_conoce_la_clave_queda_aprobado(servidor_con_clave):
    cliente, paquete = servidor_con_clave
    assert paquete.instalacion == firma.derivar_clave(CLAVE)[0] and paquete.por_clave
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=solicitud(paquete)).json()['estado'] == 'aprobada'
    # Un nombre ya usado no se reemplaza (el alta prueba otro sufijo): nadie le quita la credencial a otro equipo.
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=solicitud(paquete, token='n' * 43)).status_code == 409
    ajena = solicitud(paquete, secreto=firma.derivar_clave('otra clave distinta')[1])
    assert cliente.post('/api/v1/enrolamiento/solicitud', json=ajena).status_code == 403


def test_paquete_publico_firmado_y_sin_secreto(servidor_con_clave):
    cliente, paquete = servidor_con_clave
    datos = cliente.get('/api/v1/enrolamiento/paquete').json()
    assert 'secreto' not in datos and datos['certificado'] == paquete.certificado
    prueba = datos.pop('prueba')
    assert firma.verificar(paquete.secreto, datos, prueba)


def test_instalacion_sin_clave_no_publica_paquete():
    instalacion.crear('Escuela manual', puerto=puerto_libre(), equipo='servidor')
    with TestClient(crear_app()) as cliente:
        assert cliente.get('/api/v1/enrolamiento/paquete').status_code == 404


def test_primer_equipo_servidor_y_segundo_se_une_solo(tmp_path, monkeypatch):
    udp = puerto_libre(socket.SOCK_DGRAM)
    opciones = dict(espera=1, rondas=1, puerto_descubrimiento=udp, destinos=('127.0.0.1',),
                    cortafuegos=False, aviso=lambda _: None)
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc1'))
    assert automatico.preparar(CLAVE, 'Escuela', puerto_libre(), **opciones) == 'servidor'
    paquete = configuracion.cargar_paquete()
    assert Nodo.cargar().roles == ['plataforma', 'agente']
    tls = rutas.datos_plataforma() / 'tls'
    servidor = uvicorn.Server(uvicorn.Config(crear_app(), host='127.0.0.1', port=paquete.puerto, log_config=None,
                                             ssl_certfile=str(tls / 'certificado.pem'), ssl_keyfile=str(tls / 'clave.pem')))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    respondedor = descubrimiento.Respondedor(paquete, '127.0.0.1')
    respondedor.start()
    try:
        while not servidor.started:
            time.sleep(0.05)
        monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc2'))
        # Otra clave: la plataforma no contesta y el equipo no se une a esta escuela.
        assert automatico.buscar('una clave equivocada', 1, 1, udp, ('127.0.0.1',))[0] is None
        with pytest.raises(ErrorInstalacion):  # Y un paquete pedido con la clave equivocada no valida.
            automatico.descargar_paquete(f'https://127.0.0.1:{paquete.puerto}',
                                         automatico.buscar('una clave equivocada', 0.1, 1, udp, ('127.0.0.1',))[1])
        assert automatico.preparar(CLAVE, **opciones) == 'estacion'
        nodo = Nodo.cargar()
        assert nodo.roles == ['agente'] and nodo.url == f'https://127.0.0.1:{paquete.puerto}'
        recibido = configuracion.cargar_paquete()
        assert recibido.certificado == paquete.certificado and recibido.secreto == paquete.secreto
        assert instalacion.estado(recibido, 'agente') == 'aprobada'
        assert Credencial.cargar('agente').identidad.endswith('-agente')
        # Red sin difusión: con la dirección del servidor se une igual, sin buscar ni crear otra instalación.
        monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc3'))
        directa = dict(opciones, destinos=())
        assert automatico.preparar(CLAVE, url=f'https://127.0.0.1:{paquete.puerto}', **directa) == 'estacion'
        assert instalacion.estado(configuracion.cargar_paquete(), 'agente') == 'aprobada'
    finally:
        respondedor.detener()
        servidor.should_exit = True
        hilo.join(5)
        os.environ.pop('SIDP_HOME', None)
