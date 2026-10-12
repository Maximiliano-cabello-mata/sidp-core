# Despliegue

Un solo ejecutable para todos los equipos. Guía completa: [docs/arquitectura/instalacion.md](../docs/arquitectura/instalacion.md).

| Paso | Orden |
|---|---|
| Compilar genérico | `python -m pip install -r requirements-build.txt` y `python despliegue/compilar.py` |
| Servidor | `sidp crear-instalacion --nombre "..."` y luego `sidp` |
| Compilar preconfigurado | `python despliegue/compilar.py --paquete <SIDP_HOME>/instalacion.json` |
| Equipo nuevo | Abrir `sidp.exe` (con paquete incrustado o `instalacion.json` al lado) |
| Aprobar | En el servidor: `sidp identidades aprobar <equipo>-agente` |
| Arranque automático | `schtasks /Create /TN SIDP /SC ONSTART /RU SYSTEM /TR "\"C:\SIDP\sidp.exe\" iniciar"` |

PyInstaller no compila de forma cruzada: el `.exe` se genera en Windows. CI publica el genérico como artefacto `sidp-windows`. Un ejecutable con paquete incrustado contiene el secreto de la escuela: no se sube a Git ni a CI.
