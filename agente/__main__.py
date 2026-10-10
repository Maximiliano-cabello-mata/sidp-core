import os
import sqlite3
import time
from pathlib import Path
import httpx
from contratos.v1 import Dispositivo, Resultado


def ciclo(cliente, db):
    # Los resultados se guardan antes de enviarse y sobreviven a un reinicio.
    for identificador, reserva, mensaje in db.execute('SELECT id,reserva,mensaje FROM pendientes').fetchall():
        respuesta = cliente.post(f'/api/v1/tareas/{identificador}/resultado',
                                 json=Resultado(reserva=reserva, mensaje=mensaje).model_dump())
        if respuesta.status_code == 409:
            print(f'Resultado obsoleto {identificador}: reserva vencida o reemplazada', flush=True)
        else:
            respuesta.raise_for_status()
        with db:
            db.execute('DELETE FROM pendientes WHERE id=?', (identificador,))
    respuesta = cliente.post('/api/v1/dispositivos/registro', json=Dispositivo(capacidades=['diagnostico.echo']).model_dump())
    respuesta.raise_for_status()
    respuesta = cliente.post('/api/v1/tareas/reclamar')
    respuesta.raise_for_status()
    tarea = respuesta.json()
    if tarea:
        if tarea['operacion'] != 'diagnostico.echo':
            raise ValueError('Capacidad no autorizada')
        with db:
            db.execute('INSERT OR REPLACE INTO pendientes VALUES(?,?,?)',
                       (tarea['id'], tarea['reserva'], tarea['mensaje']))


def main():
    ruta = Path(os.environ.get('SIDP_AGENTE_DIR', 'datos-agente'))
    ruta.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ruta / 'pendientes.db') as db, httpx.Client(
        base_url=os.environ.get('SIDP_URL', 'http://127.0.0.1:8000'),
        headers={'Authorization': 'Bearer ' + os.environ['SIDP_TOKEN']}, timeout=10
    ) as cliente:
        db.execute('CREATE TABLE IF NOT EXISTS pendientes(id TEXT PRIMARY KEY,reserva TEXT,mensaje TEXT)')
        while True:
            try:
                ciclo(cliente, db)
            except httpx.TransportError:
                print('Plataforma no disponible; pendientes conservados', flush=True)
            time.sleep(2)


if __name__ == '__main__':
    main()
