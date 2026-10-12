"""Bucle del agente: entregar pendientes, reclamar, ejecutar y guardar antes de enviar."""
import logging
import sqlite3
import sys
import time
import httpx
from agente.capacidades import CAPACIDADES
from agente.recursos import medir
from comun import configuracion, descubrimiento, red, registros, rutas
from comun.politicas import Transporte, espera_reintento
from contratos.infraestructura import PoliticaNodo, motivo_bloqueo
from contratos.v1 import Dispositivo, Resultado

registro = logging.getLogger('sidp.agente')
ESPERA_MINIMA, ESPERA_MAXIMA = 2, 15
SALIDA_CONFIGURACION = 3


def preparar(db):
    db.execute('CREATE TABLE IF NOT EXISTS pendientes(id TEXT PRIMARY KEY,reserva TEXT,mensaje TEXT)')


def registrar(cliente, recursos=False):
    respuesta = cliente.post('/api/v1/dispositivos/registro', json=Dispositivo(capacidades=list(CAPACIDADES), protocolo_recursos=recursos).model_dump())
    respuesta.raise_for_status()


def entregar(cliente, db):
    # Los resultados se guardan antes de enviarse y sobreviven a un reinicio.
    filas = db.execute('SELECT id,reserva,mensaje FROM pendientes').fetchall()
    for identificador, reserva, mensaje in filas:
        respuesta = cliente.post(f'/api/v1/tareas/{identificador}/resultado',
                                 json=Resultado(reserva=reserva, mensaje=mensaje).model_dump())
        if respuesta.status_code == 409:
            registro.warning('Resultado obsoleto %s: reserva vencida o reemplazada', identificador)
        else:
            respuesta.raise_for_status()
        with db:
            db.execute('DELETE FROM pendientes WHERE id=?', (identificador,))
    return bool(filas)


def ciclo(cliente, db):
    """Una vuelta completa. Devuelve True si hubo trabajo (para no esperar)."""
    preparar(db)
    entrego = entregar(cliente, db)
    respuesta = cliente.post('/api/v1/tareas/reclamar')
    if respuesta.status_code == 409:  # Plataforma reiniciada o equipo nuevo: volver a registrarse.
        registrar(cliente)
        respuesta = cliente.post('/api/v1/tareas/reclamar')
    respuesta.raise_for_status()
    tarea = respuesta.json()
    if not tarea:
        return entrego
    funcion = CAPACIDADES.get(tarea['operacion'])
    if not funcion:
        raise ValueError(f"Capacidad no autorizada: {tarea['operacion']}")
    resultado = funcion(tarea)
    with db:
        db.execute('INSERT OR REPLACE INTO pendientes VALUES(?,?,?)', (tarea['id'], tarea['reserva'], resultado))
    return True


def redescubrir(paquete):
    if not paquete:
        return None
    url = descubrimiento.buscar(paquete)
    if url:
        nodo = configuracion.Nodo.cargar() or configuracion.Nodo()
        nodo.url = url
        nodo.guardar()
        registro.info('Plataforma encontrada en %s', url)
    return url


def main():
    registros.configurar('agente')
    paquete = configuracion.cargar_paquete()
    url, token = red.resolver('agente', paquete)
    politica_red = Transporte.cargar()
    fallos, espera = 0, politica_red.espera_minima_s
    with sqlite3.connect(rutas.datos_agente() / 'pendientes.db') as db:
        cliente = red.cliente(url, token, paquete)
        registro.info('Agente iniciado contra %s con %s', url, list(CAPACIDADES))
        while True:
            try:
                # Entregar resultados incluso si el equipo está pausado o sobrecargado.
                preparar(db)
                entrego = entregar(cliente, db)
                muestra = medir(rutas.datos_agente())
                respuesta = cliente.post('/api/v1/dispositivos/latido', json=muestra.model_dump())
                if respuesta.status_code == 409:
                    registrar(cliente, recursos=True)
                    respuesta = cliente.post('/api/v1/dispositivos/latido', json=muestra.model_dump())
                respuesta.raise_for_status()
                politica = PoliticaNodo.model_validate(respuesta.json()['politica'])
                bloqueado = motivo_bloqueo(muestra, politica)
                trabajo = entrego or False
                if not bloqueado:
                    trabajo = ciclo(cliente, db) or trabajo
                fallos = 0
                espera = politica_red.espera_minima_s if trabajo else min(max(espera, politica_red.espera_minima_s) * 2, politica_red.espera_maxima_s)
            except httpx.TransportError:
                fallos += 1
                espera = espera_reintento(fallos, politica_red)
                registro.warning('Plataforma no disponible; pendientes conservados')
                if fallos % 5 == 0 and (nueva := redescubrir(paquete)) and nueva != url:
                    cliente.close()
                    url, cliente = nueva, red.cliente(nueva, token, paquete)
            except httpx.HTTPStatusError as error:
                if error.response.status_code in (401, 403):
                    registro.error('Credencial rechazada (%s): revise aprobación o revocación', error.response.status_code)
                    sys.exit(SALIDA_CONFIGURACION)
                registro.warning('Plataforma respondió %s; reintento', error.response.status_code)
                fallos += 1
                espera = espera_reintento(fallos, politica_red)
            time.sleep(espera)


if __name__ == '__main__':
    main()

