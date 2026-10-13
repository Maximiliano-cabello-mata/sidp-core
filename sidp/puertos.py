"""Puerto de la plataforma ocupado: decirlo claro en lugar de reintentar sin fin.

Pasó en la prueba real del 2026-10-13: un sidp.exe viejo seguía abierto en el servidor,
ocupaba el 8443 y el nuevo se reiniciaba cada minuto mientras el agente hablaba con el viejo.
"""
import locale
import os
import socket
import subprocess


def ocupado(puerto, anfitrion='0.0.0.0'):
    """True si otro programa ya escucha en el puerto (la plataforma no podría abrirlo)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prueba:
        if os.name != 'nt':  # En Linux evita confundir conexiones recién cerradas con un programa abierto.
            prueba.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            prueba.bind((anfitrion, puerto))
        except OSError:
            return True
    return False


def _salida(comando):
    try:
        resultado = subprocess.run(comando, capture_output=True, timeout=10, encoding=locale.getpreferredencoding(False),
                                   errors='replace')
    except (OSError, subprocess.SubprocessError):
        return ''
    return resultado.stdout or ''


def quien_usa(puerto):
    """Nombre y PID del programa que escucha en el puerto (solo Windows; None si no se sabe)."""
    if os.name != 'nt':
        return None
    for linea in _salida(['netstat', '-ano', '-p', 'TCP']).splitlines():
        partes = linea.split()
        # TCP  0.0.0.0:8443  0.0.0.0:0  LISTENING|ESCUCHANDO  1234 (el estado cambia con el idioma).
        if len(partes) >= 5 and partes[1].endswith(f':{puerto}') and partes[2].endswith(':0') and partes[-1].isdigit():
            pid = partes[-1]
            fila = _salida(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH']).strip()
            nombre = fila.split('","')[0].strip('"') if fila.startswith('"') else 'programa desconocido'
            return f'{nombre} (PID {pid})'
    return None


def mensaje(puerto):
    quien = quien_usa(puerto)
    return (f'No se puede abrir el servidor: el puerto {puerto} de esta computadora ya está en uso'
            f'{f" por {quien}" if quien else ""}.\n'
            'Casi siempre es otra ventana de SIDP, o un sidp.exe viejo, que sigue abierta.\n'
            'Ciérrela (Administrador de tareas > Detalles > clic derecho > Finalizar árbol de procesos)\n'
            'y vuelva a abrir este programa. Si no aparece, reinicie la computadora.')
