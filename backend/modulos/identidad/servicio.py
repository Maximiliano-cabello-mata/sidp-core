"""Ciclo de vida de identidades técnicas: solicitud, aprobación, revocación.

Usado por la API y por la línea de comandos del servidor (misma lógica, misma auditoría).
"""
import secrets
import time
from backend.auditoria import anotar
from comun import firma

TOLERANCIA_SELLO = 600
MAXIMO_PENDIENTES = 20
ROLES = ("admin", "cerebro", "agente")


class Rechazo(ValueError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo


def crear_directa(bd, equipo, rol, token, actor="instalador", identificador=None):
    """Identidad ya aprobada; solo para el arranque local del servidor."""
    if rol not in ROLES:
        raise Rechazo(422, f"Rol desconocido: {rol}")
    identificador = identificador or f"{equipo}-{rol}"
    ahora = time.time()
    with bd.transaccion() as db:
        db.execute("INSERT INTO identidades(id,equipo,rol,token_resumen,estado,creada,aprobada,origen) "
                   "VALUES(?,?,?,?,'aprobada',?,?,'local') ON CONFLICT(id) DO UPDATE SET "
                   "token_resumen=excluded.token_resumen, estado='aprobada', aprobada=excluded.aprobada",
                   (identificador, equipo, rol, firma.resumen_token(token), ahora, ahora))
        anotar(db, actor, "identidad.creada", identificador, {"rol": rol})
    return identificador


def solicitar(bd, paquete, solicitud):
    """Registra una solicitud firmada. Con invitación válida queda aprobada al instante."""
    if not paquete:
        raise Rechazo(503, "Plataforma en modo laboratorio: sin enrolamiento")
    if solicitud.instalacion != paquete.instalacion:
        raise Rechazo(403, "Instalación distinta")
    if not firma.verificar(paquete.secreto, solicitud.firmable(), solicitud.prueba):
        raise Rechazo(403, "Prueba de instalación inválida")
    ahora = time.time()
    if abs(ahora - solicitud.sello) > TOLERANCIA_SELLO:
        raise Rechazo(400, "Reloj del equipo desfasado más de 10 minutos")
    identificador = f"{solicitud.equipo}-{solicitud.rol}"
    with bd.transaccion() as db:
        actual = db.execute("SELECT * FROM identidades WHERE id=?", (identificador,)).fetchone()
        if actual and actual["token_resumen"] == solicitud.token_resumen:
            return {"id": identificador, "estado": actual["estado"]}
        if actual and actual["estado"] != "revocada":
            raise Rechazo(409, "La identidad ya existe; revóquela antes de reinstalar el equipo")
        if db.execute("SELECT COUNT(*) FROM identidades WHERE estado='pendiente'").fetchone()[0] >= MAXIMO_PENDIENTES:
            raise Rechazo(429, "Demasiadas solicitudes pendientes")
        estado = "pendiente"
        if solicitud.invitacion:
            invitacion = db.execute(
                "SELECT * FROM invitaciones WHERE codigo_resumen=? AND usada IS NULL AND vence>? AND rol=?",
                (firma.resumen_token(solicitud.invitacion), ahora, solicitud.rol)).fetchone()
            if not invitacion:
                raise Rechazo(403, "Invitación inválida, usada, vencida o de otro rol")
            db.execute("UPDATE invitaciones SET usada=?, identidad=? WHERE codigo_resumen=?",
                       (ahora, identificador, invitacion["codigo_resumen"]))
            estado = "aprobada"
        db.execute("INSERT INTO identidades(id,equipo,rol,token_resumen,estado,creada,aprobada,origen) "
                   "VALUES(?,?,?,?,?,?,?,'enrolamiento') ON CONFLICT(id) DO UPDATE SET "
                   "token_resumen=excluded.token_resumen, estado=excluded.estado, creada=excluded.creada, "
                   "aprobada=excluded.aprobada",
                   (identificador, solicitud.equipo, solicitud.rol, solicitud.token_resumen, estado,
                    ahora, ahora if estado == "aprobada" else None))
        anotar(db, identificador, "identidad.solicitada", identificador,
               {"rol": solicitud.rol, "invitacion": bool(solicitud.invitacion)})
    return {"id": identificador, "estado": estado}


def cambiar(bd, identificador, estado, actor):
    permitidos = {"aprobada": ("pendiente",), "revocada": ("pendiente", "aprobada")}[estado]
    with bd.transaccion() as db:
        fila = db.execute("SELECT estado FROM identidades WHERE id=?", (identificador,)).fetchone()
        if not fila:
            raise Rechazo(404, "Identidad inexistente")
        if fila["estado"] == estado:
            return {"id": identificador, "estado": estado}
        if fila["estado"] not in permitidos:
            raise Rechazo(409, f"No se puede pasar de {fila['estado']} a {estado}")
        db.execute("UPDATE identidades SET estado=?, aprobada=CASE WHEN ?='aprobada' THEN ? ELSE aprobada END "
                   "WHERE id=?", (estado, estado, time.time(), identificador))
        anotar(db, actor, f"identidad.{estado}", identificador)
    return {"id": identificador, "estado": estado}


def listar(bd):
    with bd.conexion() as db:
        return [dict(f) for f in db.execute(
            "SELECT id,equipo,rol,estado,origen,creada,aprobada,ultimo FROM identidades ORDER BY equipo,rol")]


def invitar(bd, rol, horas, actor):
    """Código de un solo uso; se muestra una vez y se guarda solo su resumen."""
    codigo = "-".join(secrets.token_hex(2).upper() for _ in range(4))
    vence = time.time() + horas * 3600
    with bd.transaccion() as db:
        db.execute("INSERT INTO invitaciones(codigo_resumen,rol,creada,vence,actor) VALUES(?,?,?,?,?)",
                   (firma.resumen_token(codigo), rol, time.time(), vence, actor))
        anotar(db, actor, "invitacion.creada", rol, {"horas": horas})
    return {"codigo": codigo, "rol": rol, "vence": vence}
