"""Línea de comandos de sidp.exe. Sin argumentos equivale a "sidp iniciar"."""
import argparse
import json
import sys
from comun import configuracion, registros, rutas
from comun.configuracion import PERFILES, Credencial, Nodo
from sidp.errores import ErrorInstalacion

# Importaciones pesadas dentro de cada orden: el supervisor residente debe ocupar poca memoria.

AYUDA_INICIAL = """No hay configuración en {hogar}.

  Servidor nuevo:      sidp crear-instalacion --nombre "Primaria Delfino Pando"
  Equipo adicional:    copie instalacion.json junto a sidp.exe (o use un sidp.exe
                       compilado con el paquete) y vuelva a ejecutarlo.
"""


def iniciar(args):
    nodo = Nodo.cargar()
    if not nodo:
        paquete = configuracion.cargar_paquete()
        if not paquete:
            print(AYUDA_INICIAL.format(hogar=rutas.hogar()))
            if rutas.congelado() and sys.stdin and sys.stdin.isatty():
                input('Presione Enter para cerrar...')  # Doble clic en Windows: que se alcance a leer.
            return 2
        # Primer arranque con paquete: el equipo se une solo y espera aprobación.
        from sidp import instalacion
        instalacion.unirse(paquete, PERFILES.get(paquete.perfil, ['agente']))
        nodo = Nodo.cargar()
    from sidp import supervisor
    registros.configurar('nodo')
    supervisor.supervisar(nodo.roles)
    return 0


def crear_instalacion(args):
    from sidp import instalacion
    resultado = instalacion.crear(args.nombre, args.puerto, tls=not args.sin_tls,
                                  con_agente=not args.sin_agente, equipo=args.equipo)
    paquete = resultado['paquete']
    print(f'Instalación "{paquete.nombre}" creada en {rutas.hogar()}')
    print(f'  Identificador: {paquete.instalacion}')
    if resultado['huella']:
        print(f'  Huella TLS:    {resultado["huella"]}')
    print(f'  Roles locales: {", ".join(resultado["roles"])}')
    print('\nToken del operador (se muestra una sola vez; también en credenciales/admin.json):')
    print(f'  {resultado["token_operador"]}')
    print('\nSiguientes pasos:\n  1. sidp iniciar               (arranca este servidor)'
          '\n  2. python despliegue/compilar.py --paquete "' + str(configuracion.ruta_paquete()) + '"'
          '\n     o copie instalacion.json junto a sidp.exe en cada equipo')
    return 0


def unirse(args):
    paquete = configuracion.cargar_paquete(args.paquete)
    if not paquete:
        print('No se encontró instalacion.json; indique --paquete RUTA', file=sys.stderr)
        return 2
    from sidp import instalacion
    lista = args.roles.split(',') if args.roles else PERFILES.get(paquete.perfil, ['agente'])
    instalacion.unirse(paquete, lista, equipo=args.equipo, url=args.url,
                       invitacion=args.invitacion, esperar=not args.no_esperar)
    return 0


def estado(args):
    from sidp import instalacion
    paquete = configuracion.cargar_paquete()
    nodo = Nodo.cargar()
    informe = {'hogar': str(rutas.hogar()),
               'instalacion': {'nombre': paquete.nombre, 'id': paquete.instalacion} if paquete else None,
               'nodo': nodo.__dict__ if nodo else None, 'credenciales': {}}
    for rol in ('admin', 'agente', 'cerebro'):
        credencial = Credencial.cargar(rol)
        if credencial:
            try:
                situacion = instalacion.estado(paquete, rol)
            except Exception as error:  # Informe de diagnóstico: nunca fallar por la red.
                situacion = f'sin conexión ({type(error).__name__})'
            informe['credenciales'][rol] = {'identidad': credencial.identidad, 'estado': situacion}
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return 0


def _local():
    """Acceso directo a la base: solo en el equipo que aloja la plataforma."""
    from backend.main import preparar
    nodo = Nodo.cargar()
    if not nodo or 'plataforma' not in nodo.roles:
        raise SystemExit('Este comando se ejecuta en el servidor de plataforma')
    return preparar(paquete=configuracion.cargar_paquete())


def identidades(args):
    from backend.modulos.identidad import servicio
    ctx = _local()
    if args.accion == 'listar':
        for fila in servicio.listar(ctx.bd):
            print(f"{fila['id']:<32} {fila['rol']:<8} {fila['estado']:<10} {fila['origen']}")
    else:
        if not args.identidad:
            raise SystemExit('Indique la identidad')
        estado_nuevo = 'aprobada' if args.accion == 'aprobar' else 'revocada'
        print(servicio.cambiar(ctx.bd, args.identidad, estado_nuevo, 'operador-local'))
    return 0


def invitacion(args):
    from backend.modulos.identidad import servicio
    resultado = servicio.invitar(_local().bd, args.rol, args.horas, 'operador-local')
    print(f"Código de un solo uso para {resultado['rol']} (vigente {args.horas} h): {resultado['codigo']}")
    print(f"En el equipo nuevo: sidp unirse --invitacion {resultado['codigo']}")
    return 0


def respaldo(args):
    from backend.respaldos import crear
    print(json.dumps(crear(_local().bd, args.destino), indent=2))
    return 0


def prueba_conexion(args):
    from sidp import conectividad
    return conectividad.ejecutar(args.url, args.equipo, args.espera).cerrar()


def cortafuegos(args):
    from sidp import conectividad
    paquete = configuracion.cargar_paquete()
    if not paquete:
        raise SystemExit('Sin instalación en este equipo')
    return conectividad.abrir_cortafuegos(paquete)


def _rol(nombre, *argumentos):
    from sidp import roles
    return getattr(roles, nombre)(*argumentos)


def construir():
    parser = argparse.ArgumentParser(prog='sidp', description='SIDP: plataforma, agente y cerebro en un ejecutable')
    sub = parser.add_subparsers(dest='orden')
    sub.add_parser('iniciar', help='Arranca los roles de este equipo (predeterminado)').set_defaults(funcion=iniciar)

    p = sub.add_parser('crear-instalacion', help='Servidor nuevo: crea instalación, certificado y operador')
    p.add_argument('--nombre', required=True)
    p.add_argument('--puerto', type=int, default=configuracion.PUERTO_PLATAFORMA)
    p.add_argument('--equipo', help='Nombre de este equipo (predeterminado: nombre del host)')
    p.add_argument('--sin-agente', action='store_true', help='No ejecutar agente en el servidor')
    p.add_argument('--sin-tls', action='store_true', help='Solo laboratorio: HTTP sin cifrar')
    p.set_defaults(funcion=crear_instalacion)

    p = sub.add_parser('unirse', help='Equipo adicional: localiza la plataforma y solicita autorización')
    p.add_argument('--paquete', help='Ruta a instalacion.json')
    p.add_argument('--url', help='https://IP:PUERTO si la red bloquea el descubrimiento')
    p.add_argument('--roles', help='agente,cerebro (predeterminado: perfil del paquete)')
    p.add_argument('--equipo')
    p.add_argument('--invitacion', help='Código de un solo uso: aprobación inmediata')
    p.add_argument('--no-esperar', action='store_true')
    p.set_defaults(funcion=unirse)

    sub.add_parser('estado', help='Diagnóstico de este equipo').set_defaults(funcion=estado)

    p = sub.add_parser('identidades', help='Servidor: listar, aprobar o revocar equipos')
    p.add_argument('accion', choices=['listar', 'aprobar', 'revocar'])
    p.add_argument('identidad', nargs='?')
    p.set_defaults(funcion=identidades)

    p = sub.add_parser('invitacion', help='Servidor: código de alta inmediata')
    p.add_argument('--rol', choices=['agente', 'cerebro'], default='agente')
    p.add_argument('--horas', type=int, default=24)
    p.set_defaults(funcion=invitacion)

    p = sub.add_parser('respaldo', help='Servidor: snapshot SQLite consistente y manifiesto')
    p.add_argument('--destino', required=True, help='Archivo nuevo, preferentemente en medio externo')
    p.set_defaults(funcion=respaldo)

    p = sub.add_parser('prueba-conexion', help='Red, TLS, reloj, credenciales e ida y vuelta con otros equipos')
    p.add_argument('--url', help='https://IP:PUERTO de la plataforma (si no, la guardada o la descubierta)')
    p.add_argument('--equipo', action='append', help='Agente a probar (repetible); por omisión todos los remotos en línea')
    p.add_argument('--espera', type=int, default=90, help='Segundos máximos por ida y vuelta')
    p.set_defaults(funcion=prueba_conexion)

    sub.add_parser('cortafuegos', help='Servidor Windows: abrir TCP de la plataforma y UDP de descubrimiento '
                   'en redes privadas (consola de administrador)').set_defaults(funcion=cortafuegos)

    p = sub.add_parser('plataforma', help='Rol plataforma (lo usa el supervisor)')
    p.add_argument('--anfitrion')
    p.add_argument('--puerto', type=int)
    p.set_defaults(funcion=lambda a: _rol('plataforma', a.anfitrion, a.puerto))
    sub.add_parser('agente', help='Rol agente (lo usa el supervisor)').set_defaults(funcion=lambda a: _rol('agente'))
    sub.add_parser('cerebro', help='Rol cerebro: plan técnico de un paso (sidp cerebro --clave X)')
    return parser


def main(argumentos=None):
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    parser = construir()
    if argumentos and argumentos[0] == 'cerebro':  # Sus opciones las interpreta el propio rol.
        return sys.exit(_rol('cerebro', argumentos[1:]) or 0)
    args = parser.parse_args(argumentos or ['iniciar'])
    try:
        sys.exit(args.funcion(args) or 0)
    except ErrorInstalacion as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)

