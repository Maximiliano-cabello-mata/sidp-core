# Despliegue

Un solo ejecutable para todos los equipos. Guía completa: [docs/arquitectura/instalacion.md](../docs/arquitectura/instalacion.md).

| Paso | Orden |
|---|---|
| Compilar genérico | `python -m pip install -r requirements-build.txt` y `python despliegue/compilar.py` |
| Servidor | `sidp crear-instalacion --nombre "..."` y luego `sidp` |
| Compilar preconfigurado | `python despliegue/compilar.py --paquete <SIDP_HOME>/instalacion.json` |
| Equipo nuevo | Abrir `sidp.exe` (con paquete incrustado o `instalacion.json` al lado) |
| Aprobar | En el servidor: `sidp identidades aprobar <equipo>-agente` |
| Abrir cortafuegos (servidor) | `sidp cortafuegos` en consola de administrador |
| Comprobar conexión | `sidp prueba-conexion` en cada equipo ([guía](../docs/PRUEBA_DOS_EQUIPOS.md)) |
| Ensayo del binario | `python despliegue/ensayo_dos_equipos.py dist/sidp.exe` (lo corre CI) |
| Arranque automático | `schtasks /Create /TN SIDP /SC ONSTART /RU SYSTEM /TR "\"C:\SIDP\sidp.exe\" iniciar"` |

PyInstaller no compila de forma cruzada: el `.exe` se genera en Windows. CI publica el genérico como artefacto `sidp-windows`. Un ejecutable con paquete incrustado contiene el secreto de la escuela: no se sube a Git ni a CI.
