"""Línea de comandos de sidp.exe. Sin argumentos equivale a "sidp iniciar"."""
import argparse
import json
import os
import sys
from comun import configuracion, registros, rutas
from comun.configuracion import PERFILES, Credencial, Nodo
from sidp.errores import ErrorInstalacion

# Importaciones pesadas dentro de cada orden: el supervisor residente debe ocupar poca memoria.

AYUDA_INICIAL = """No hay configuración en {hogar}.

  Con clave de escuela:  sidp iniciar --clave "la clave de la escuela"
                         (o abra sidp.exe con doble clic y escríbala)
  Servidor manual:       sidp crear-instalacion --nombre "Primaria Delfino Pando"
  Equipo adicional:      copie instalacion.json junto a sidp.exe y vuelva a ejecutarlo.
"""

TITULOS = {'auto': 'SIDP', 'servidor': 'SIDP-Servidor', 'equipo': 'SIDP-Equipo'}

BIENVENIDA = {
    'auto': """Primera vez en esta computadora.

Escriba la clave de escuela. Debe ser la misma en todas las computadoras de la escuela
(al menos {minimo} caracteres). La primera computadora que la use será el servidor;
las demás la encontrarán en la red y se unirán solas.
""",
    'servidor': """Primera vez: esta computadora será el SERVIDOR de la escuela.

Invente una clave de escuela de al menos {minimo} caracteres, por ejemplo una frase.
Solo deben conocerla los directivos. En las demás computadoras se abre SIDP-Equipo.exe
con la misma clave.
""",
    'equipo': """Primera vez: esta computadora se unirá al servidor de la escuela.

Escriba la clave de escuela, la misma que se usó en el servidor (al menos {minimo} caracteres).
""",
}


def _version():
    """Fecha y versión de compilación incrustadas por despliegue/compilar.py: evita usar un .exe viejo."""
    archivo = rutas.recurso_empaquetado('compilacion.txt')
    return archivo.read_text(encoding='utf-8').strip() if archivo else 'versión de desarrollo'


def _interactivo():
    return bool(sys.stdin and sys.stdin.isatty())


def _leer(pregunta):
    try:
        return input(pregunta).strip()
    except EOFError:  # Sin nadie al teclado (en Windows, NUL también parece una terminal).
        return None


def _pedir_clave(modo='auto'):
    from comun.firma import MINIMO_CLAVE
    print(BIENVENIDA[modo].format(minimo=MINIMO_CLAVE))
    while True:
        clave = _leer('Clave de escuela: ')
        if clave is None:
            return None
        if len(' '.join(clave.split())) < MINIMO_CLAVE:
            print(f'Muy corta: use al menos {MINIMO_CLAVE} caracteres.')
            continue
        if modo != 'servidor':
            return clave
        # En el servidor la clave se inventa: un error de dedo dejaría fuera a todas las demás computadoras.
        if ' '.join((_leer('Escríbala otra vez: ') or '').split()).lower() == ' '.join(clave.split()).lower():
            return clave
        print('No coinciden. Escríbala de nuevo.')


PREGUNTA_SERVIDOR = """
No encontré otra computadora con esta clave en la red.
  - Si esta es la PRIMERA computadora de la escuela, escriba S y Enter.
  - Si ya hay un servidor, escriba su dirección IP (por ejemplo 192.168.1.20) y Enter.
    La IP se ve en el servidor con el comando ipconfig ("Dirección IPv4").
  - Para buscar otra vez, solo presione Enter.
"""

PREGUNTA_EQUIPO = """
No encontré el servidor de la escuela en la red.
  - Revise que SIDP-Servidor esté abierto en el servidor y que la clave sea la misma.
  - Si la red no deja buscar, escriba la dirección IP del servidor (por ejemplo 192.168.1.20) y Enter.
    La IP se ve en el servidor con el comando ipconfig ("Dirección IPv4").
  - Para buscar otra vez, solo presione Enter.
"""


def _decidir():
    from sidp import automatico
    print(PREGUNTA_SERVIDOR)
    respuesta = _leer('Respuesta: ')
    if respuesta is None:
        print('S (sin respuesta: esta computadora será el servidor)')
        return 'servidor'
    if not respuesta:
        return 'buscar'
    if respuesta.lower() in ('s', 'si', 'sí'):
        return 'servidor'
    return automatico.url_servidor(respuesta)


def _decidir_equipo():
    """Como _decidir, pero un equipo nunca se vuelve servidor: solo buscar otra vez o escribir la IP."""
    from sidp import automatico
    print(PREGUNTA_EQUIPO)
    respuesta = _leer('IP del servidor (o Enter para buscar otra vez): ')
    if respuesta is None:
        return None
    return automatico.url_servidor(respuesta) if respuesta else 'buscar'


def _pausa_final():
    if rutas.congelado() and _interactivo():
        try:
            input('Presione Enter para cerrar...')  # Doble clic en Windows: que se alcance a leer.
        except EOFError:
            pass


def iniciar(args):
    modo = getattr(args, 'modo', None) or 'auto'
    print(f'{TITULOS[modo]} · {_version()}', flush=True)
    nodo = Nodo.cargar()
    if nodo:
        _avisar_papel(nodo, modo)
    if not nodo:
        paquete = configuracion.cargar_paquete()
        clave = getattr(args, 'clave', None) or os.environ.get('SIDP_CLAVE')
        if not paquete and not clave and _interactivo():
            clave = _pedir_clave(modo)
        if not paquete and not clave:
            print(AYUDA_INICIAL.format(hogar=rutas.hogar()))
            _pausa_final()
            return 2
        if not paquete:
            from sidp import automatico
            try:
                automatico.preparar(clave, getattr(args, 'nombre', None),
                                    getattr(args, 'puerto', None) or configuracion.PUERTO_PLATAFORMA,
                                    url=getattr(args, 'url', None) and automatico.url_servidor(args.url),
                                    decidir=_DECIDIR.get(modo) if _interactivo() else None, modo=modo)
            except (ErrorInstalacion, ValueError) as error:
                print(f'Error: {error}', file=sys.stderr)
                _pausa_final()
                return 1
            print('\nListo. Deje esta ventana abierta mientras use SIDP.', flush=True)
            return _arrancar(Nodo.cargar())
        # Primer arranque con paquete: el equipo se une solo y espera aprobación.
        from sidp import instalacion
        instalacion.unirse(paquete, PERFILES.get(paquete.perfil, ['agente']))
        nodo = Nodo.cargar()
    return _arrancar(nodo)


_DECIDIR = {'auto': _decidir, 'equipo': _decidir_equipo}


def _avisar_papel(nodo, modo):
    """Ya configurado: el papel lo decide la configuración guardada, no el ejecutable que se abrió."""
    servidor = 'plataforma' in nodo.roles
    if modo == 'servidor' and not servidor:
        print('Esta computadora ya está unida como equipo de la escuela; arranca como equipo.', flush=True)
    elif modo == 'equipo' and servidor:
        print('Esta computadora es el servidor de la escuela; arranca como servidor.', flush=True)


def _arrancar(nodo):
    from sidp import puertos, supervisor
    paquete = configuracion.cargar_paquete()
    if 'plataforma' in nodo.roles and paquete and puertos.ocupado(paquete.puerto):
        print(f'Error: {puertos.mensaje(paquete.puerto)}', file=sys.stderr)
        _pausa_final()
        return 1
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


def equipos(args):
    from backend.modulos.orquestacion.almacen import Almacen
    lista = Almacen(_local().bd).equipos()
    if args.json:
        print(json.dumps(lista, indent=2, ensure_ascii=False))
        return 0
    if not lista:
        print('Todavía no hay equipos registrados.')
        return 0
    total_nucleos = total_memoria = total_disco = 0
    print(f"{'Equipo':<28} {'Estado':<16} {'CPU':>5} {'Núcleos':>7} {'Memoria libre/total':>20} {'Disco libre':>12} {'Tareas':>7}")
    for equipo in lista:
        recursos = equipo['recursos'] or {}
        estado = 'en línea' if equipo['en_linea'] else f"sin contacto {equipo['hace_s']} s"
        if equipo['pausado']:
            estado = 'en pausa'
        memoria = f"{recursos.get('memoria_disponible_mb', 0)}/{recursos.get('memoria_total_mb') or '?'} MB"
        print(f"{equipo['id']:<28} {estado:<16} {recursos.get('cpu_porcentaje', 0):>4.0f}% "
              f"{recursos.get('nucleos') or '?':>7} {memoria:>20} {recursos.get('disco_libre_mb', 0):>9} MB "
              f"{equipo['tareas_completadas']:>7}")
        if equipo['en_linea']:
            total_nucleos += recursos.get('nucleos') or 0
            total_memoria += recursos.get('memoria_disponible_mb', 0)
            total_disco += recursos.get('disco_libre_mb', 0)
    en_linea = sum(e['en_linea'] for e in lista)
    print(f"\n{en_linea} de {len(lista)} equipos en línea. Juntos ofrecen {total_nucleos} núcleos, "
          f"{total_memoria} MB de memoria libre y {total_disco} MB de disco libre.")
    return 0


def respaldo(args):
    from backend.respaldos import crear
    print(json.dumps(crear(_local().bd, args.destino), indent=2))
    return 0


def prueba_conexion(args):
    from sidp import conectividad
    return conectividad.ejecutar(args.url, args.equipo, args.espera, reparto=args.reparto).cerrar()


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
    p = sub.add_parser('iniciar', help='Arranca los roles de este equipo (predeterminado)')
    p.add_argument('--clave', help='Clave de escuela para el primer arranque (también SIDP_CLAVE)')
    p.add_argument('--nombre', help='Nombre de la instalación si este equipo resulta ser el servidor')
    p.add_argument('--puerto', type=int, help='Puerto de la plataforma si este equipo resulta ser el servidor')
    p.add_argument('--url', help='https://IP:PUERTO del servidor si la red bloquea el descubrimiento')
    p.add_argument('--modo', choices=['auto', 'servidor', 'equipo'],
                   help='Papel en el primer arranque (SIDP-Servidor.exe y SIDP-Equipo.exe lo traen fijo)')
    p.set_defaults(funcion=iniciar)

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

    p = sub.add_parser('equipos', help='Servidor: equipos unidos, sus recursos y el trabajo que hicieron')
    p.add_argument('--json', action='store_true')
    p.set_defaults(funcion=equipos)

    p = sub.add_parser('respaldo', help='Servidor: snapshot SQLite consistente y manifiesto')
    p.add_argument('--destino', required=True, help='Archivo nuevo, preferentemente en medio externo')
    p.set_defaults(funcion=respaldo)

    p = sub.add_parser('prueba-conexion', help='Red, TLS, reloj, credenciales e ida y vuelta con otros equipos')
    p.add_argument('--url', help='https://IP:PUERTO de la plataforma (si no, la guardada o la descubierta)')
    p.add_argument('--equipo', action='append', help='Agente a probar (repetible); por omisión todos los remotos en línea')
    p.add_argument('--espera', type=int, default=90, help='Segundos máximos por ida y vuelta')
    p.add_argument('--reparto', type=int, default=0, help='Servidor: enviar N tareas sin destino y ver cómo se reparten')
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


def main(argumentos=None, modo=None):
    """modo: papel fijo de SIDP-Servidor.exe o SIDP-Equipo.exe para "iniciar" (doble clic)."""
    for flujo in (sys.stdout, sys.stderr):
        if flujo and hasattr(flujo, 'reconfigure'):
            flujo.reconfigure(errors='replace')  # Consola o tubería con otra codificación: no fallar.
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    parser = construir()
    if argumentos and argumentos[0] == 'cerebro':  # Sus opciones las interpreta el propio rol.
        return sys.exit(_rol('cerebro', argumentos[1:]) or 0)
    args = parser.parse_args(argumentos or ['iniciar'])
    if args.orden in (None, 'iniciar') and modo and not getattr(args, 'modo', None):
        args.modo = modo
    try:
        sys.exit(args.funcion(args) or 0)
    except ErrorInstalacion as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)

