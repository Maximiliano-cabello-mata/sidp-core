"""Pruebas HMAC sobre JSON canónico. Demuestran pertenencia a una instalación."""
import base64
import hashlib
import hmac
import json
import secrets
import uuid

MINIMO_CLAVE = 8


def canonico(datos):
    return json.dumps(datos, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def firmar(secreto_b64, datos):
    clave = base64.b64decode(secreto_b64)
    return hmac.new(clave, canonico(datos), hashlib.sha256).hexdigest()


def verificar(secreto_b64, datos, prueba):
    return hmac.compare_digest(firmar(secreto_b64, datos), prueba or '')


def resumen_token(token):
    """El servidor guarda solo el SHA-256 del token; el token nunca sale del equipo."""
    return hashlib.sha256(token.encode()).hexdigest()


def nuevo_token():
    return secrets.token_urlsafe(32)


def derivar_clave(clave):
    """Identificador y secreto de instalación a partir de la clave de escuela (ADR-025).

    Misma clave, misma instalación en cualquier equipo. PBKDF2 encarece adivinar la clave
    a partir de una respuesta de descubrimiento capturada en la red.
    """
    normalizada = ' '.join(clave.split()).lower()
    if len(normalizada) < MINIMO_CLAVE:
        raise ValueError(f'La clave de escuela debe tener al menos {MINIMO_CLAVE} caracteres')
    material = hashlib.pbkdf2_hmac('sha256', normalizada.encode(), b'sidp-clave-escuela-v1', 200_000, dklen=48)
    return str(uuid.UUID(bytes=material[:16], version=4)), base64.b64encode(material[16:]).decode()


def nuevo_secreto():
    return base64.b64encode(secrets.token_bytes(32)).decode()
