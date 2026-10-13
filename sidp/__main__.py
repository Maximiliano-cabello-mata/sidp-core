import sys
from sidp.cli import main

if __name__ == '__main__':
    # El .exe ignora PYTHONIOENCODING; con salida redirigida Windows usaría cp1252 y rompería los acentos.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, 'reconfigure'):
            flujo.reconfigure(encoding='utf-8', errors='replace')
    main()
