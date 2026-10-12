"""Registro de capacidades locales. Solo funciones incorporadas; nunca código recibido por red.

Agregar una capacidad: declararla en contratos.v1.Capacidad y registrar aquí su función.
Cada función recibe la tarea y devuelve el resultado a confirmar. Debe ser repetible
(idempotente) porque una reserva vencida provoca reejecución.
"""


def echo(tarea):
    return tarea['mensaje']


CAPACIDADES = {'diagnostico.echo': echo}
