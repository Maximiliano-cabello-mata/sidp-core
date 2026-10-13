# Despliegue

Dos ejecutables con el mismo programa (ADR-029): `SIDP-Servidor.exe` para el servidor y `SIDP-Equipo.exe` para las demás PCs. Guía completa: [docs/arquitectura/instalacion.md](../docs/arquitectura/instalacion.md).

| Paso | Orden |
|---|---|
| Compilar | `python -m pip install -r requirements-build.txt` y `python despliegue/compilar.py --tipo servidor` (y `--tipo equipo`) |
| Servidor con clave de escuela | Abrir `SIDP-Servidor.exe` y escribir la clave dos veces |
| Equipo con clave de escuela | Abrir `SIDP-Equipo.exe` con la misma clave |
| Servidor (manual) | `sidp crear-instalacion --nombre "..."` y luego `sidp` |
| Compilar preconfigurado | `python despliegue/compilar.py --paquete <SIDP_HOME>/instalacion.json` |
| Equipo nuevo (manual) | Abrir `SIDP-Equipo.exe` (con paquete incrustado o `instalacion.json` al lado) |
| Aprobar | En el servidor: `sidp identidades aprobar <equipo>-agente` |
| Abrir cortafuegos (servidor) | `sidp cortafuegos` en consola de administrador |
| Comprobar conexión | `sidp prueba-conexion` en cada equipo ([guía](../docs/PRUEBA_DOS_EQUIPOS.md)) |
| Ensayo del binario | `python despliegue/ensayo_dos_equipos.py dist/SIDP-Servidor.exe --estacion dist/SIDP-Equipo.exe` (lo corre CI) |
| Arranque automático | `schtasks /Create /TN SIDP /SC ONSTART /RU SYSTEM /TR "\"C:\SIDP\SIDP-Servidor.exe\" iniciar"` |

PyInstaller no compila de forma cruzada: el `.exe` se genera en Windows. CI publica los dos como artefacto `sidp-windows`; cada uno lleva su fecha y commit de compilación y la muestra al abrirse. `--tipo generico` produce el `sidp.exe` de modo automático, solo para desarrollo. Un ejecutable con paquete incrustado contiene el secreto de la escuela: no se sube a Git ni a CI.
