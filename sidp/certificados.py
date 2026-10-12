"""Certificado autofirmado de la instalación. Los equipos lo fijan desde el paquete."""
import datetime
import ipaddress
import os
import socket
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def generar(directorio, nombre, anios=10):
    """Crea clave EC P-256 (ligera para equipos modestos) y certificado. Devuelve PEM público."""
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    clave = ec.generate_private_key(ec.SECP256R1())
    sujeto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"SIDP {nombre}"[:64]),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SIDP")])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    anfitrion = "".join(c for c in socket.gethostname() if c.isascii() and (c.isalnum() or c in "-.")) or "sidp"
    alternativos = [x509.DNSName("localhost"), x509.DNSName(anfitrion),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    certificado = (x509.CertificateBuilder().subject_name(sujeto).issuer_name(sujeto)
                   .public_key(clave.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(ahora - datetime.timedelta(days=1))
                   .not_valid_after(ahora + datetime.timedelta(days=365 * anios))
                   .add_extension(x509.SubjectAlternativeName(alternativos), critical=False)
                   .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                   .sign(clave, hashes.SHA256()))
    ruta_clave = directorio / "clave.pem"
    ruta_clave.write_bytes(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    if os.name != "nt":
        os.chmod(ruta_clave, 0o600)
    pem = certificado.public_bytes(serialization.Encoding.PEM).decode()
    (directorio / "certificado.pem").write_text(pem)
    return pem


def huella(pem):
    certificado = x509.load_pem_x509_certificate(pem.encode())
    return certificado.fingerprint(hashes.SHA256()).hex(":").upper()
