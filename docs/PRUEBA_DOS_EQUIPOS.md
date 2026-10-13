# Prueba con dos computadoras

Guía para comprobar que dos equipos Windows de la escuela se conectan, se autorizan y comparten trabajo a través de la plataforma. Duración: 15 minutos. Usa solo datos de prueba.

**Qué significa "sincronizados" en SIDP (ADR-019):** los datos viven en una sola plataforma, en PC1. PC2 no copia la base: se conecta a ella por HTTPS, recibe trabajo y devuelve resultados confirmados. La prueba lo demuestra con una tarea creada en PC1, ejecutada por PC2 y confirmada de vuelta en PC1.

## Antes de empezar

- **Ejecutables (ADR-029):** del artefacto `sidp-windows` del CI. En PC1 se copia `SIDP-Servidor.exe` y en PC2 `SIDP-Equipo.exe`, los dos en `C:\SIDP\`. No hace falta instalar Python ni nada más. Al abrirse, cada uno muestra en la primera línea su fecha de compilación: si es vieja, es un archivo de otra descarga.
- **Clave de escuela:** una frase de al menos 8 caracteres que solo conozcan los directivos, por ejemplo `primaria delfino 2026`. Es la misma en todas las computadoras. Quien la sepa y esté en la red de la escuela se une sin pedir permiso (ADR-025).
- **Red:** los dos equipos en la misma red. En Windows debe estar marcada como **Privada** (Configuración > Red e Internet > Propiedades).
- **Reloj:** la hora de ambos equipos debe estar bien (diferencia menor a 10 minutos).

## PC1 (será el servidor)

1. Doble clic en `C:\SIDP\SIDP-Servidor.exe`.
2. Escribir la clave de escuela, Enter, escribirla otra vez y Enter. Si no coinciden, la pide de nuevo.
3. Comprueba que no haya otro servidor con esa clave en la red y se vuelve el servidor. Windows pide permiso de administrador para abrir el cortafuegos: elegir **Sí**.
4. Debe decir `Listo. Deje esta ventana abierta mientras use SIDP.` No cerrar esa ventana.

Si dice `Ya hay un servidor de esta escuela en ...`, otra PC ya es el servidor: en esta se usa `SIDP-Equipo.exe`.

## PC2

1. Doble clic en `C:\SIDP\SIDP-Equipo.exe`.
2. Escribir **la misma** clave de escuela y Enter.
3. Debe mostrar `Plataforma "SIDP" encontrada en https://IP:8443` y `Equipo autorizado.` No cerrar esa ventana.

Si PC2 no encuentra a PC1, pregunta: escriba la IP de PC1 (en PC1, `ipconfig`, "Dirección IPv4") o presione Enter para buscar otra vez. `SIDP-Equipo.exe` nunca se vuelve servidor.

Más computadoras (PC3, PC4...): `SIDP-Equipo.exe` y la misma clave. Todas reparten el trabajo.

No se copia ningún archivo ni se usan códigos. Las siguientes veces basta el doble clic: ya no pide la clave. Si por error se abre el otro archivo en una PC ya configurada, avisa y arranca con su papel de siempre.

La instalación manual con `crear-instalacion`, `instalacion.json` e invitaciones sigue disponible para quien la prefiera (`SIDP-Servidor.exe --help`).

## Prueba de conectividad

Abrir "Símbolo del sistema", escribir `cd C:\SIDP` y Enter. En esa **segunda consola de PC1**:

```bat
SIDP-Servidor.exe prueba-conexion
```

En una **segunda consola de PC2**:

```bat
SIDP-Equipo.exe prueba-conexion
```

| Prueba | Qué comprueba |
|---|---|
| Descubrimiento UDP | Encuentra la plataforma por difusión, con respuesta firmada |
| Puerto TCP | El puerto 8443 de PC1 es alcanzable |
| HTTPS con certificado fijado | Cifrado con el certificado de esta instalación; latencia mínima, promedio y máxima |
| Reloj | Desfase con el servidor |
| Credencial … | Identidades de este equipo aprobadas |
| Equipo … (solo PC1) | Último contacto de cada agente |
| Ida y vuelta … (solo PC1) | Tarea creada en PC1, ejecutada por PC2 y confirmada en PC1, con su tiempo |
| Reparto de tareas (solo PC1, con `--reparto 9`) | Varias tareas repartidas entre todos los equipos en línea |

Para ver en PC1 qué computadoras están unidas y qué aporta cada una (núcleos, memoria, disco y tareas hechas):

```bat
SIDP-Servidor.exe equipos
```

En PC1 también se puede probar el reparto: `SIDP-Servidor.exe prueba-conexion --reparto 9`.

El resultado esperado es `RESULTADO: PASA` en los dos equipos. Cada ejecución guarda un informe JSON en `C:\ProgramData\SIDP\registros\conectividad-*.json`. Esos dos archivos son la evidencia de la prueba.

## Pruebas de resiliencia (opcionales)

1. **Red caída:** desconectar el cable o WiFi de PC2 durante 1 minuto y reconectar. El agente debe reconectarse solo; repetir `prueba-conexion` en PC1.
2. **Reinicio del servidor:** cerrar la ventana de PC1 (Ctrl+C) y volver a abrir `SIDP-Servidor.exe`. PC2 se recupera solo en menos de un minuto.
3. **Cambio de IP:** si PC1 cambia de IP, PC2 la vuelve a descubrir tras unos reintentos.
4. **Revocación:** en PC1, `SIDP-Servidor.exe identidades revocar <nombre>-agente`. El agente de PC2 se detiene y `prueba-conexion` en PC2 marca la credencial como revocada.

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `Descubrimiento UDP` en AVISO | La red bloquea la difusión. No impide operar si el equipo ya está unido |
| PC2 dice `No encontré el servidor de la escuela` | El módem puede aislar los equipos Wi-Fi, o hay un adaptador virtual. Revise que PC1 esté abierto y la clave sea idéntica, y escriba la IP de PC1 |
| `Puerto TCP` en FALLA | PC1 apagado, `SIDP-Servidor.exe` cerrado en PC1, cortafuegos sin abrir o red marcada como Pública |
| `el puerto 8443 de esta computadora ya está en uso por ...` | Sigue abierto otro SIDP, casi siempre un `sidp.exe` viejo. Administrador de tareas > Detalles > clic derecho en el programa que indica > Finalizar árbol de procesos; o reiniciar la PC |
| PC2 dice `le falta ...instalacion.json` | Se borró parte de la carpeta con SIDP abierto. Escriba la clave cuando la pida: se vuelve a unir solo |
| `Ya hay un servidor de esta escuela` | Se abrió `SIDP-Servidor.exe` en una segunda PC. En esa PC use `SIDP-Equipo.exe` |
| `No coinciden` al escribir la clave | En el servidor la clave se escribe dos veces igual; vuelva a escribirla con calma |
| `Reloj` en FALLA | Corregir la hora de Windows (sincronizar con internet) |
| `Ida y vuelta … sin respuesta` | La ventana de `SIDP-Equipo.exe` en PC2 está cerrada o su agente fue revocado |

IP de PC1: `ipconfig`, línea "Dirección IPv4".

## Ensayo automático en un solo equipo

Antes de ir a la escuela se pueden validar los dos ejecutables en una sola PC. El comando simula los equipos en carpetas separadas, comprueba que un segundo servidor se niegue y lo ejecuta el CI en Windows:

```bat
python despliegue\ensayo_dos_equipos.py C:\SIDP\SIDP-Servidor.exe --estacion C:\SIDP\SIDP-Equipo.exe
```

Requiere Python y el repositorio. La salida esperada es `ENSAYO: PASA`.

## Limpiar después de la prueba

En cada equipo: cerrar la ventana de SIDP y borrar `C:\ProgramData\SIDP`. En PC1, quitar las reglas de cortafuegos:

```bat
netsh advfirewall firewall delete rule name="SIDP plataforma"
netsh advfirewall firewall delete rule name="SIDP descubrimiento"
```
