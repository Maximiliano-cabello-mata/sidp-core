"""Punto de entrada de SIDP-Servidor.exe (ADR-029): con doble clic, esta computadora es el servidor."""
from sidp.cli import main

if __name__ == '__main__':
    main(modo='servidor')
