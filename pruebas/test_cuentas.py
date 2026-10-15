"""Cuentas del personal: contraseñas con PBKDF2, bloqueo tras intentos fallidos y permisos por rol."""
import sqlite3
from pathlib import Path

import pytest
from validacion.cuentas import Cuentas, ErrorCuenta, contrasena_correcta, puede, resumen_contrasena

DISENO = Path(__file__).resolve().parent.parent / 'database' / 'diseno_integral.sql'


@pytest.fixture
def cuentas():
    db = sqlite3.connect(':memory:', isolation_level=None)
    db.executescript(DISENO.read_text(encoding='utf-8'))
    return Cuentas(db)


def test_la_contrasena_solo_se_guarda_como_resumen():
    resumen = resumen_contrasena('secreta123')
    assert 'secreta123' not in resumen and contrasena_correcta(resumen, 'secreta123')
    assert not contrasena_correcta(resumen, 'otra') and not contrasena_correcta('x', 'x')


def test_crear_entrar_y_salir(cuentas):
    assert not cuentas.hay_cuentas()
    cuentas.crear({'nombres': 'Ana', 'primer_apellido': 'Ruiz', 'rol': 'docente', 'usuario': 'Ana.Ruiz', 'contrasena': 'secreta123'})
    assert cuentas.hay_cuentas()
    with pytest.raises(ErrorCuenta, match='Ya existe'):
        cuentas.crear({'nombres': 'Ana', 'primer_apellido': 'Ruiz', 'rol': 'docente', 'usuario': 'ana.ruiz', 'contrasena': 'secreta123'})
    token = cuentas.entrar('ana.ruiz', 'secreta123')
    usuario = cuentas.sesion(token)
    assert usuario['rol'] == 'docente' and not puede(usuario, 'expedientes')
    cuentas.salir(token)
    assert cuentas.sesion(token) is None


def test_cinco_intentos_fallidos_bloquean(cuentas):
    cuentas.crear({'nombres': 'Luz', 'primer_apellido': 'Paz', 'rol': 'apoyo', 'usuario': 'luz', 'contrasena': 'secreta123'})
    for _ in range(5):
        with pytest.raises(ErrorCuenta, match='incorrectos'):
            cuentas.entrar('luz', 'mal')
    with pytest.raises(ErrorCuenta, match='Demasiados intentos'):
        cuentas.entrar('luz', 'secreta123')


def test_los_roles_van_de_mas_a_menos_acceso(cuentas):
    cuentas.crear({'nombres': 'Eva', 'primer_apellido': 'Sol', 'rol': 'direccion', 'usuario': 'eva', 'contrasena': 'secreta123'})
    cuentas.crear({'nombres': 'Luz', 'primer_apellido': 'Paz', 'rol': 'apoyo', 'usuario': 'luz', 'contrasena': 'secreta123'})
    direccion, apoyo = (cuentas.sesion(cuentas.entrar(u, 'secreta123')) for u in ('eva', 'luz'))
    assert puede(direccion, 'personal') and puede(apoyo, 'renapo') and not puede(apoyo, 'decidir')
    with pytest.raises(ErrorCuenta, match='propia'):
        cuentas.cambiar_estado(direccion['id'], False, direccion['id'])
    token = cuentas.entrar('luz', 'secreta123')
    cuentas.cambiar_estado(apoyo['id'], False, direccion['id'])
    assert cuentas.sesion(token) is None
