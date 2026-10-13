"""SIDP-Servidor.exe y SIDP-Equipo.exe (ADR-029): el papel lo fija el ejecutable."""
import builtins
import os
import socket
import threading
import time
import pytest
import uvicorn
from backend.main import crear_app
from comun import configuracion, descubrimiento, rutas
from comun.configuracion import Nodo
from sidp import automatico, cli
from sidp.errores import ErrorInstalacion
from pruebas.test_instalacion import puerto_libre

CLAVE = 'Primaria Delfino 2026'


@pytest.fixture
def opciones():
    udp = puerto_libre(socket.SOCK_DGRAM)
    return dict(espera=0.5, rondas=1, puerto_descubrimiento=udp, destinos=('127.0.0.1',),
                cortafuegos=False, aviso=lambda _: None)


@pytest.fixture
def servidor_en_red(tmp_path, monkeypatch, opciones):
    """Un servidor creado con SIDP-Servidor, respondiendo en la red local simulada."""
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc1'))
    assert automatico.preparar(CLAVE, 'Escuela', puerto_libre(), modo='servidor', **opciones) == 'servidor'
    paquete = configuracion.cargar_paquete()
    tls = rutas.datos_plataforma() / 'tls'
    servidor = uvicorn.Server(uvicorn.Config(crear_app(), host='127.0.0.1', port=paquete.puerto, log_config=None,
                                             ssl_certfile=str(tls / 'certificado.pem'), ssl_keyfile=str(tls / 'clave.pem')))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    respondedor = descubrimiento.Respondedor(paquete, '127.0.0.1')
    respondedor.start()
    while not servidor.started:
        time.sleep(0.05)
    try:
        yield paquete
    finally:
        respondedor.detener()
        servidor.should_exit = True
        hilo.join(5)
        os.environ.pop('SIDP_HOME', None)


def test_un_segundo_servidor_con_la_misma_clave_se_niega(servidor_en_red, tmp_path, monkeypatch, opciones):
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc2'))
    with pytest.raises(ErrorInstalacion, match='Ya hay un servidor'):
        automatico.preparar(CLAVE, modo='servidor', **opciones)
    assert Nodo.cargar() is None and configuracion.cargar_paquete() is None


def test_el_equipo_se_une_y_nunca_crea_otro_servidor(servidor_en_red, tmp_path, monkeypatch, opciones):
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc2'))
    assert automatico.preparar(CLAVE, modo='equipo', **opciones) == 'estacion'
    assert Nodo.cargar().roles == ['agente']


def test_equipo_sin_servidor_no_se_vuelve_servidor(tmp_path, monkeypatch, opciones):
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'sola'))
    with pytest.raises(ErrorInstalacion, match='No se encontró el servidor'):
        automatico.preparar(CLAVE, modo='equipo', **opciones)
    # Aunque alguien conteste "S" a una pregunta vieja, el equipo no crea una instalación.
    with pytest.raises(ErrorInstalacion):
        automatico.preparar(CLAVE, modo='equipo', decidir=lambda: 'servidor', **opciones)
    assert Nodo.cargar() is None and configuracion.cargar_paquete() is None


def test_equipo_busca_otra_vez_y_luego_desiste(tmp_path, monkeypatch, opciones):
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'sola'))
    respuestas = iter(['buscar', None])
    with pytest.raises(ErrorInstalacion):
        automatico.preparar(CLAVE, modo='equipo', decidir=lambda: next(respuestas), **opciones)
    assert next(respuestas, 'agotadas') == 'agotadas'  # Buscó dos veces antes de desistir.


def entradas(monkeypatch, *valores):
    cola = list(valores)

    def leer(_pregunta=''):
        if not cola:
            raise EOFError
        return cola.pop(0)
    monkeypatch.setattr(builtins, 'input', leer)


def test_pregunta_del_equipo_no_ofrece_ser_servidor(monkeypatch, capsys):
    entradas(monkeypatch, '', '192.168.1.20', 'S')
    assert cli._decidir_equipo() == 'buscar'
    assert cli._decidir_equipo() == 'https://192.168.1.20:8443'
    assert cli._decidir_equipo() == 'https://S:8443'  # "S" se toma como dirección, no como "ser servidor".
    assert cli._decidir_equipo() is None  # Sin nadie al teclado: desiste.
    assert 'PRIMERA computadora' not in capsys.readouterr().out


def test_el_servidor_pide_la_clave_dos_veces(monkeypatch):
    entradas(monkeypatch, 'primaria delfino', 'primaria delfin0', 'primaria delfino', ' Primaria  Delfino ')
    assert cli._pedir_clave('servidor') == 'primaria delfino'
    entradas(monkeypatch, 'primaria delfino')
    assert cli._pedir_clave('equipo') == 'primaria delfino'  # En los equipos basta una vez.


def test_el_ejecutable_fija_el_modo_del_doble_clic(monkeypatch):
    vistos = []
    monkeypatch.setattr(cli, 'iniciar', lambda args: vistos.append(args.modo) or 0)
    for argumentos, modo, esperado in (([], 'servidor', 'servidor'), (['iniciar'], 'equipo', 'equipo'),
                                       (['iniciar', '--modo', 'auto'], 'equipo', 'auto'), ([], None, None)):
        with pytest.raises(SystemExit):
            cli.main(argumentos, modo=modo)
        assert vistos.pop() == esperado


def test_puerto_ocupado_se_dice_claro_y_no_arranca(tmp_path, monkeypatch, opciones, capsys):
    """Un sidp.exe viejo abierto ocupaba el 8443: el nuevo debe decirlo, no reintentar cada minuto."""
    from sidp import puertos, supervisor
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc1'))
    automatico.preparar(CLAVE, 'Escuela', puerto_libre(), modo='servidor', **opciones)
    paquete = configuracion.cargar_paquete()
    assert not puertos.ocupado(paquete.puerto)
    monkeypatch.setattr(supervisor, 'supervisar', lambda roles: pytest.fail('no debía arrancar'))
    with socket.socket() as viejo:
        viejo.bind(('0.0.0.0', paquete.puerto))
        viejo.listen()
        assert puertos.ocupado(paquete.puerto)
        assert cli._arrancar(Nodo.cargar()) == 1
    assert f'el puerto {paquete.puerto} de esta computadora ya está en uso' in capsys.readouterr().err


def test_el_agente_dice_por_que_no_llega_al_servidor():
    """En la prueba real PC2 solo decía "Plataforma no disponible", sin la causa."""
    import httpx
    from comun import red
    for rechazo in ('[Errno 111] Connection refused', '[WinError 10061] No se puede establecer una conexión'):
        assert 'rechazó la conexión' in red.causa(httpx.ConnectError(rechazo))
    tls = httpx.ConnectError('[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:1000)')
    assert 'certificado del servidor no es el que guardó' in red.causa(tls)
    assert 'no contesta' in red.causa(httpx.ConnectTimeout('timed out'))


def test_estacion_sin_instalacion_json_se_vuelve_a_unir(servidor_en_red, tmp_path, monkeypatch, opciones):
    """En PC2 quedó nodo.json sin instalacion.json: el agente decía "no disponible" sin fin."""
    import argparse
    monkeypatch.setenv('SIDP_HOME', str(tmp_path / 'pc2'))
    assert automatico.preparar(CLAVE, modo='equipo', **opciones) == 'estacion'
    configuracion.ruta_paquete().unlink()
    arrancado = []
    monkeypatch.setattr(cli, '_arrancar', lambda nodo: arrancado.append(nodo) or 0)
    monkeypatch.setattr(cli, '_interactivo', lambda: False)
    args = argparse.Namespace(modo='equipo', clave=CLAVE, nombre=None, puerto=None,
                              url=f'https://127.0.0.1:{servidor_en_red.puerto}')
    assert cli.iniciar(args) == 0
    assert configuracion.cargar_paquete().instalacion == servidor_en_red.instalacion
    assert arrancado and arrancado[0].roles == ['agente']


def test_ida_y_vuelta_aguanta_una_respuesta_lenta():
    """En CI una consulta tardó más de 5 s y prueba-conexion terminaba con un error de Python."""
    import httpx
    from sidp import conectividad

    class Cliente:
        def __init__(self):
            self.consultas = 0

        def post(self, ruta, json):
            self.mensaje = json['mensaje']
            return httpx.Response(200, json={'id': 't1'}, request=httpx.Request('POST', ruta))

        def get(self, ruta):
            self.consultas += 1
            if self.consultas == 1:
                raise httpx.ReadTimeout('The read operation timed out')
            return httpx.Response(200, json={'estado': 'completada', 'resultado': self.mensaje})

    segundos, error = conectividad.ida_y_vuelta(Cliente(), 'pc2-agente', espera=30)
    assert error is None and segundos is not None
