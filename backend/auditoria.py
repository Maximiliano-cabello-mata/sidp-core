"""Bitácora de cambios. Se escribe en la misma transacción que el cambio auditado."""
import json
import time


def anotar(db, actor, accion, objeto, detalle=None):
    db.execute("INSERT INTO auditoria(fecha,actor,accion,objeto,detalle) VALUES(?,?,?,?,?)",
               (time.time(), actor, accion, str(objeto), json.dumps(detalle, ensure_ascii=False) if detalle else None))
