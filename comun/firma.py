"""Pruebas HMAC sobre JSON canónico. Demuestran pertenencia a una instalación."""
import base64
import hashlib
import hmac
import json
import secrets


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


def nuevo_secreto():
    return base64.b64encode(secrets.token_bytes(32)).decode()
