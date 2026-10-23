"""Las otras computadoras de la escuela usan el servidor con usuario y contraseña: lo que escanean se guarda en él."""
import pytest

from validacion import aplicacion
from pruebas import test_entorno_pruebas
from pruebas.test_entorno_pruebas import expediente_escaneado, pedir

entorno = test_entorno_pruebas.entorno  # El mismo servidor de prueba (fixture).


@pytest.fixture
def otra_pc(entorno, monkeypatch):
    """Las pruebas corren en esta PC: sin direcciones locales, cada petición llega como de otra computadora."""
    app, url = entorno
    app.cuentas.crear({'nombres': 'Rosa', 'primer_apellido': 'Luna', 'rol': 'secretaria', 'usuario': 'rosa', 'contrasena': 'secreta123'})
    app.cuentas.crear({'nombres': 'Iván', 'primer_apellido': 'Sol', 'rol': 'docente', 'usuario': 'ivan', 'contrasena': 'secreta123'})
    app.cuentas.crear({'nombres': 'Eva', 'primer_apellido': 'Mar', 'rol': 'apoyo', 'usuario': 'eva', 'contrasena': 'secreta123'})
    monkeypatch.setattr(aplicacion, 'LOCALES', ())
    return app, url


def entrar(url, usuario):
    codigo, respuesta = pedir(url, '/api/entrar', {'usuario': usuario, 'contrasena': 'secreta123'})
    assert codigo == 200, respuesta
    return {'X-SIDP-Token': respuesta['token']}


def test_desde_otra_pc_el_panel_pide_entrar_y_lo_escaneado_queda_en_el_servidor(otra_pc):
    app, url = otra_pc
    import urllib.request
    with urllib.request.urlopen(url + '/') as respuesta:
        pagina = respuesta.read().decode()
    assert '"modo": "red"' in pagina and app.token not in pagina  # El token del servidor nunca sale de él.
    codigo, respuesta = pedir(url, '/api/estado')
    assert codigo == 401 and respuesta['entrar']
    assert pedir(url, '/api/entrar', {'usuario': 'rosa', 'contrasena': 'otra'})[0] == 400
    sesion = entrar(url, 'rosa')
    assert pedir(url, '/api/yo', cabeceras=sesion)[1]['nombre'] == 'Rosa Luna'
    # Secretaría escanea desde su PC: el expediente se guarda en el servidor, a su nombre.
    codigo, leido = escanear_con(url, sesion)
    assert codigo == 200, leido
    codigo, guardado = pedir(url, '/api/escaneo/guardar', {'lote': leido['lote'], 'alumno': leido['propuesta']['alumno']}, sesion)
    assert codigo == 200 and guardado['expediente'] == '0001', guardado
    assert (app.carpeta / 'expedientes' / '0001').is_dir()
    assert app.bandeja.decisiones()['0001']['quien'] == 'Rosa Luna'
    # Los ajustes del cerebro solo se cambian en el servidor mismo.
    assert pedir(url, '/api/configuracion', cabeceras=sesion)[0] == 403
    assert pedir(url, '/api/cuentas', cabeceras=sesion)[0] == 403  # Las cuentas son de Dirección.
    pedir(url, '/api/salir', {}, sesion)
    assert pedir(url, '/api/estado', cabeceras=sesion)[0] == 401


def escanear_con(url, sesion):
    import uuid
    limite = uuid.uuid4().hex
    cuerpo = (f'--{limite}\r\nContent-Disposition: form-data; name="archivo"; filename="expediente.pdf"\r\n'
              f'Content-Type: application/pdf\r\n\r\n'.encode() + expediente_escaneado() + f'\r\n--{limite}--\r\n'.encode())
    return pedir(url, '/api/escaneo/leer', cuerpo, sesion, tipo=f'multipart/form-data; boundary={limite}')


def test_cada_rol_ve_solo_lo_suyo(otra_pc):
    app, url = otra_pc
    apoyo, docente = entrar(url, 'eva'), entrar(url, 'ivan')
    assert pedir(url, '/api/curps', cabeceras=apoyo)[0] == 200  # Apoyo valida CURP en RENAPO...
    assert pedir(url, '/api/expediente?id=0001', cabeceras=apoyo)[0] == 403  # ...pero no abre documentos.
    assert pedir(url, '/api/estado', cabeceras=docente)[0] == 403  # Docente: su plataforma viene después.


def test_direccion_crea_las_cuentas_desde_el_servidor(entorno):
    app, url = entorno
    token = {'X-SIDP-Token': app.token}
    codigo, respuesta = pedir(url, '/api/cuentas/crear', {'nombres': 'Ana', 'primer_apellido': 'Ríos', 'rol': 'secretaria',
                                                          'usuario': 'ana', 'contrasena': 'corta'}, token)
    assert codigo == 400 and '8 caracteres' in respuesta['error']
    codigo, respuesta = pedir(url, '/api/cuentas/crear', {'nombres': 'Ana', 'primer_apellido': 'Ríos', 'rol': 'secretaria',
                                                          'usuario': 'ana', 'contrasena': 'secreta123'}, token)
    assert codigo == 200 and [c['usuario'] for c in respuesta['cuentas']] == ['ana']
    assert respuesta['direccion'].endswith(f':{app.puerto}/')
    cuenta = respuesta['cuentas'][0]['id']
    respuesta = pedir(url, '/api/cuentas/estado', {'id': cuenta, 'activo': False}, token)[1]
    assert respuesta['cuentas'][0]['estado'] == 'baja'
