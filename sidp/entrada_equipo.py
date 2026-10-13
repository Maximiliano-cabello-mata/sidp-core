"""Punto de entrada de SIDP-Equipo.exe (ADR-029): con doble clic, esta computadora se une al servidor."""
from sidp.cli import main

if __name__ == '__main__':
    main(modo='equipo')
