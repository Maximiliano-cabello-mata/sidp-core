"""Reparto de trabajo entre equipos y vista de recursos (ADR-026)."""
import pytest
from backend.modulos.orquestacion.almacen import Almacen
from comun import descubrimiento
from comun.politicas import Cola
from contratos.infraestructura import CambiarPolitica, PoliticaNodo, Telemetria
from contratos.v1 import NuevaTarea, Resultado
from sidp import automatico


def muestra(cpu=5):
    return Telemetria(cpu_porcentaje=cpu, memoria_disponible_mb=2048, disco_libre_mb=9000, nucleos=4, memoria_total_mb=8192)


@pytest.fixture
def cola(tmp_path):
    cola = Almacen(tmp_path / 'cola.db', Cola(pendientes_maximos=50, ejecuciones_maximas=10))
    for equipo in ('servidor', 'aula-1', 'aula-2'):
        cola.registrar(equipo, ['diagnostico.echo'], recursos=True)
        cola.latido(equipo, muestra())
    return cola


def hacer(cola, equipo):
    tarea = cola.reclamar(equipo)
    if tarea:
        cola.completar(equipo, tarea['id'], Resultado(reserva=tarea['reserva'], mensaje=tarea['mensaje']))
    return tarea


def test_el_equipo_mas_rapido_no_se_queda_con_todo(cola):
    for numero in range(6):
        cola.crear('operador', NuevaTarea(clave=str(numero), mensaje=f'm{numero}'))
    # El servidor reclama primero siempre (como su agente local, más cercano): igual cede su turno.
    hechas = {}
    for _ in range(4):
        for equipo in ('servidor', 'aula-1', 'aula-2'):
            if hacer(cola, equipo):
                hechas[equipo] = hechas.get(equipo, 0) + 1
    assert hechas == {'servidor': 2, 'aula-1': 2, 'aula-2': 2}


def test_un_equipo_pausado_o_ocupado_no_retiene_trabajo(cola):
    cola.cambiar_politica('admin', 'aula-1', CambiarPolitica(revision_esperada=0, politica=PoliticaNodo(pausado=True)))
    cola.latido('aula-2', muestra(cpu=99))  # Sobrecargado: no cuenta como disponible.
    for numero in range(3):
        cola.crear('operador', NuevaTarea(clave=str(numero)))
    assert all(hacer(cola, 'servidor') for _ in range(3))


def test_equipo_sin_contacto_no_cuenta(cola):
    with cola.conexion() as db:
        db.execute("UPDATE dispositivos SET ultimo=0 WHERE id<>'servidor'")
    for numero in range(2):
        cola.crear('operador', NuevaTarea(clave=str(numero)))
    assert hacer(cola, 'servidor') and hacer(cola, 'servidor')


def test_vista_de_equipos_con_recursos(cola):
    cola.crear('operador', NuevaTarea(clave='1'))
    hacer(cola, 'aula-1')
    equipos = {e['id']: e for e in cola.equipos()}
    assert set(equipos) == {'servidor', 'aula-1', 'aula-2'}
    assert equipos['aula-1']['tareas_completadas'] == 1 and equipos['aula-1']['en_linea']
    assert equipos['servidor']['recursos']['nucleos'] == 4


def test_busqueda_sale_por_cada_red_del_equipo(monkeypatch):
    monkeypatch.setattr(descubrimiento, 'direcciones_locales', lambda: ['192.168.56.1', '192.168.100.18'])
    assert descubrimiento.destinos_lan() == ('255.255.255.255', '192.168.56.255', '192.168.100.255', '127.0.0.1')


def test_url_del_servidor_escrita_a_mano():
    assert automatico.url_servidor('192.168.1.20') == 'https://192.168.1.20:8443'
    assert automatico.url_servidor(' https://10.0.0.5:9000/ ') == 'https://10.0.0.5:9000'


def test_sin_servidor_pregunta_antes_de_crear_otro(hogar_aislado):
    respuestas = iter(['buscar', 'servidor'])
    preguntas = []

    def decidir():
        preguntas.append(1)
        return next(respuestas)
    resultado = automatico.preparar('clave de prueba larga', espera=0.1, rondas=1, destinos=(), cortafuegos=False,
                                    aviso=lambda _: None, decidir=decidir)
    assert resultado == 'servidor' and len(preguntas) == 2


def test_ip_equivocada_permite_reintentar(hogar_aislado):
    respuestas = iter(['https://127.0.0.1:1', 'servidor'])
    avisos = []
    resultado = automatico.preparar('clave de prueba larga', espera=0.1, rondas=1, destinos=(), cortafuegos=False,
                                    aviso=avisos.append, decidir=lambda: next(respuestas))
    assert resultado == 'servidor' and any('No se pudo unir' in a for a in avisos)
