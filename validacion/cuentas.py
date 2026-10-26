"""Cuentas del personal, inicio de sesión y qué puede hacer cada rol.

Cuatro roles, de más a menos acceso:

- Dirección: todo, incluso crear cuentas y los ajustes.
- Secretaría (administrativos): expedientes, autorizar o rechazar, RENAPO, grupos, y ver
  asistencias y calificaciones.
- Apoyo (servicio social, ayudantes): la lista de expedientes con su estado y la validación de
  la CURP en RENAPO. No abre documentos ni autoriza.
- Docente: solo sus grupos: pase de lista, calificaciones y el contacto de los tutores (nombre,
  parentesco, teléfono y correo). No ve expedientes, documentos, CURP ni domicilios.

Las contraseñas se guardan solo como PBKDF2 con sal; la sesión, solo como resumen del token.
"""
import datetime
import hashlib
import secrets
import uuid

ROLES = {'direccion': 'Dirección', 'secretaria': 'Secretaría', 'apoyo': 'Apoyo (servicio social)', 'docente': 'Docente'}
# Rol de la pantalla -> (usuario.rol, personal.puesto) del diseño de 39 tablas.
EN_BASE = {'direccion': ('direccion', 'director'), 'secretaria': ('administrativo', 'secretaria'),
           'apoyo': ('administrativo', 'apoyo'), 'docente': ('docente', 'docente')}
PERMISOS = {
    'direccion': {'expedientes', 'documentos', 'decidir', 'renapo', 'grupos', 'ver_grupos', 'capturar', 'personal', 'ajustes', 'biblioteca'},
    'secretaria': {'expedientes', 'documentos', 'decidir', 'renapo', 'grupos', 'ver_grupos', 'biblioteca'},
    'apoyo': {'expedientes', 'renapo', 'biblioteca'},  # Quien atiende la biblioteca presta y registra libros.
    'docente': set(),  # Sus grupos se revisan uno por uno (Escolar.revisar_grupo).
}
ITERACIONES = 240_000
HORAS_SESION = 12
INTENTOS = 5
MINUTOS_BLOQUEO = 15


class ErrorCuenta(Exception):
    """Algo que la persona hizo mal o no puede hacer; el mensaje es para ella."""


def _ahora():
    return datetime.datetime.now().replace(microsecond=0)


def resumen_contrasena(contrasena, sal=None):
    sal = sal or secrets.token_hex(16)
    valor = hashlib.pbkdf2_hmac('sha256', contrasena.encode(), bytes.fromhex(sal), ITERACIONES).hex()
    return f'pbkdf2${ITERACIONES}${sal}${valor}'


def contrasena_correcta(resumen, contrasena):
    try:
        metodo, iteraciones, sal, valor = resumen.split('$')
    except ValueError:
        return False  # Cuentas sin contraseña (el administrador del entorno de pruebas) no entran.
    calculado = hashlib.pbkdf2_hmac('sha256', contrasena.encode(), bytes.fromhex(sal), int(iteraciones)).hex()
    return metodo == 'pbkdf2' and secrets.compare_digest(calculado, valor)


def rol_de(rol, puesto):
    if rol == 'direccion':
        return 'direccion'
    if rol == 'docente':
        return 'docente'
    return 'apoyo' if puesto == 'apoyo' or rol == 'tecnico' else 'secretaria'


def puede(usuario, permiso):
    return permiso in PERMISOS.get(usuario['rol'], set())


class Cuentas:
    def __init__(self, db):
        self.db = db

    def hay_cuentas(self):
        return bool(self.db.execute("SELECT 1 FROM usuario WHERE contrasena_resumen LIKE 'pbkdf2$%' AND estado = 'activo'").fetchone())

    def _anotar(self, actor, accion, objeto_id, despues):
        import json
        self.db.execute('INSERT INTO bitacora(fecha, actor, accion, objeto_tipo, objeto_id, despues) VALUES(?,?,?,?,?,?)',
                        (_ahora().isoformat(), actor, accion, 'usuario', objeto_id, json.dumps(despues, ensure_ascii=False)))

    def crear(self, datos, actor='primera_cuenta'):
        """Cuenta nueva: nombres, primer_apellido, segundo_apellido, rol, usuario, contrasena, telefono, correo."""
        rol = datos.get('rol')
        if rol not in EN_BASE:
            raise ErrorCuenta('Elige un rol: Dirección, Secretaría, Apoyo o Docente.')
        nombres, apellido = str(datos.get('nombres', '')).strip(), str(datos.get('primer_apellido', '')).strip()
        usuario = str(datos.get('usuario', '')).strip().lower()
        contrasena = str(datos.get('contrasena', ''))
        if not nombres or not apellido:
            raise ErrorCuenta('Faltan el nombre o el primer apellido.')
        if len(usuario) < 3 or not usuario.replace('.', '').replace('_', '').isalnum():
            raise ErrorCuenta('El usuario debe tener al menos 3 letras o números, sin espacios.')
        if len(contrasena) < 8:
            raise ErrorCuenta('La contraseña debe tener al menos 8 caracteres.')
        if self.db.execute('SELECT 1 FROM usuario WHERE nombre_usuario = ?', (usuario,)).fetchone():
            raise ErrorCuenta(f'Ya existe el usuario "{usuario}". Elige otro.')
        rol_bd, puesto = EN_BASE[rol]
        personal, identificador = str(uuid.uuid4()), str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO personal(id, nombres, primer_apellido, segundo_apellido, puesto, telefono, correo) '
                            'VALUES(?,?,?,?,?,?,?)', (personal, nombres, apellido, str(datos.get('segundo_apellido') or '').strip() or None,
                                                      puesto, datos.get('telefono') or None, datos.get('correo') or None))
            self.db.execute('INSERT INTO usuario(id, personal_id, nombre_usuario, contrasena_resumen, rol) VALUES(?,?,?,?,?)',
                            (identificador, personal, usuario, resumen_contrasena(contrasena), rol_bd))
            self._anotar(actor, 'usuario.creado', identificador, {'usuario': usuario, 'rol': rol, 'nombre': f'{nombres} {apellido}'})
        return {'id': identificador, 'usuario': usuario, 'rol': rol}

    def _fila(self, condicion, valor):
        fila = self.db.execute(
            'SELECT u.id, u.personal_id, u.nombre_usuario, u.contrasena_resumen, u.rol, u.estado, u.intentos_fallidos, u.bloqueado_hasta, '
            'p.nombres, p.primer_apellido, p.puesto FROM usuario u JOIN personal p ON p.id = u.personal_id WHERE ' + condicion,
            (valor,)).fetchone()
        if not fila:
            return None
        claves = ('id', 'personal_id', 'usuario', 'resumen', 'rol_bd', 'estado', 'intentos', 'bloqueado_hasta', 'nombres', 'apellido', 'puesto')
        return dict(zip(claves, fila))

    @staticmethod
    def _publico(fila):
        rol = rol_de(fila['rol_bd'], fila['puesto'])
        return {'id': fila['id'], 'personal_id': fila['personal_id'], 'usuario': fila['usuario'], 'rol': rol,
                'rol_texto': ROLES[rol], 'nombre': f"{fila['nombres']} {fila['apellido']}", 'nombres': fila['nombres'],
                'permisos': sorted(PERMISOS.get(rol, set()))}  # El panel muestra solo lo que la cuenta puede usar.

    def entrar(self, usuario, contrasena):
        """Token de sesión, o ErrorCuenta. Tras 5 intentos fallidos la cuenta espera 15 minutos."""
        fila = self._fila('u.nombre_usuario = ?', str(usuario or '').strip().lower())
        ahora = _ahora()
        if fila and fila['bloqueado_hasta'] and fila['bloqueado_hasta'] > ahora.isoformat():
            raise ErrorCuenta('Demasiados intentos. Espera 15 minutos o pide a Dirección que revise tu cuenta.')
        if not fila or fila['estado'] != 'activo' or not contrasena_correcta(fila['resumen'], str(contrasena or '')):
            if fila:
                intentos = fila['intentos'] + 1
                bloqueo = (ahora + datetime.timedelta(minutes=MINUTOS_BLOQUEO)).isoformat() if intentos >= INTENTOS else None
                with self.db:
                    self.db.execute('UPDATE usuario SET intentos_fallidos = ?, bloqueado_hasta = ?, version = version + 1 WHERE id = ?',
                                    (0 if bloqueo else intentos, bloqueo, fila['id']))
            raise ErrorCuenta('Usuario o contraseña incorrectos.')
        token = secrets.token_urlsafe(32)
        with self.db:
            if fila['intentos'] or fila['bloqueado_hasta']:
                self.db.execute('UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL, version = version + 1 WHERE id = ?',
                                (fila['id'],))
            self.db.execute('INSERT INTO sesion(token_resumen, usuario_id, creada, vence) VALUES(?,?,?,?)',
                            (hashlib.sha256(token.encode()).hexdigest(), fila['id'], ahora.isoformat(),
                             (ahora + datetime.timedelta(hours=HORAS_SESION)).isoformat()))
            self._anotar(fila['id'], 'usuario.entro', fila['id'], {'usuario': fila['usuario']})
        return token

    def sesion(self, token):
        """El usuario de un token vigente, o None."""
        if not token:
            return None
        fila = self.db.execute('SELECT usuario_id FROM sesion WHERE token_resumen = ? AND revocada IS NULL AND vence > ?',
                               (hashlib.sha256(token.encode()).hexdigest(), _ahora().isoformat())).fetchone()
        usuario = fila and self._fila('u.id = ?', fila[0])
        return self._publico(usuario) if usuario and usuario['estado'] == 'activo' else None

    def salir(self, token):
        with self.db:
            self.db.execute('UPDATE sesion SET revocada = ? WHERE token_resumen = ?',
                            (_ahora().isoformat(), hashlib.sha256((token or '').encode()).hexdigest()))

    def lista(self):
        filas = self.db.execute(
            "SELECT u.id, u.nombre_usuario, u.rol, u.estado, p.nombres, p.primer_apellido, p.puesto FROM usuario u "
            "JOIN personal p ON p.id = u.personal_id WHERE u.contrasena_resumen LIKE 'pbkdf2$%' ORDER BY p.primer_apellido, p.nombres")
        return [{'id': i, 'usuario': u, 'rol': rol_de(r, p), 'rol_texto': ROLES[rol_de(r, p)], 'estado': e, 'nombre': f'{n} {a}'}
                for i, u, r, e, n, a, p in filas]

    def cambiar_estado(self, usuario_id, activo, actor):
        """Dar de baja o reactivar una cuenta (nunca se borra). Al darla de baja se cierran sus sesiones."""
        if usuario_id == actor:
            raise ErrorCuenta('No puedes dar de baja tu propia cuenta.')
        if not self.db.execute('SELECT 1 FROM usuario WHERE id = ?', (usuario_id,)).fetchone():
            raise ErrorCuenta('No existe esa cuenta.')
        estado = 'activo' if activo else 'baja'
        with self.db:
            self.db.execute('UPDATE usuario SET estado = ?, version = version + 1 WHERE id = ?', (estado, usuario_id))
            if not activo:
                self.db.execute('UPDATE sesion SET revocada = ? WHERE usuario_id = ? AND revocada IS NULL', (_ahora().isoformat(), usuario_id))
            self._anotar(actor, f'usuario.{estado}', usuario_id, {'estado': estado})
        return self.lista()
