# Prueba con dos computadoras

Guía para comprobar que dos equipos Windows de la escuela se conectan, se autorizan y comparten trabajo a través de la plataforma. Duración: 15 minutos. Usa solo datos de prueba.

**Qué significa "sincronizados" en SIDP (ADR-019):** los datos viven en una sola plataforma, en PC1. PC2 no copia la base: se conecta a ella por HTTPS, recibe trabajo y devuelve resultados confirmados. La prueba lo demuestra con una tarea creada en PC1, ejecutada por PC2 y confirmada de vuelta en PC1.

## Antes de empezar

- **Ejecutable:** `sidp.exe` (artefacto `sidp-windows` del CI) copiado en `C:\SIDP\` en ambos equipos. No hace falta instalar Python.
- **Red:** los dos equipos en la misma red. En Windows debe estar marcada como **Privada** (Configuración > Red e Internet > Propiedades).
- **Reloj:** la hora de ambos equipos debe estar bien (diferencia menor a 10 minutos).
- **Consola:** abrir "Símbolo del sistema" o PowerShell en `C:\SIDP`.

## PC1 (servidor)

```bat
sidp.exe crear-instalacion --nombre "Prueba Delfino Pando"
sidp.exe cortafuegos
sidp.exe invitacion --rol agente
sidp.exe
```

1. La primera orden crea la instalación en `C:\ProgramData\SIDP`.
2. `cortafuegos` abre TCP 8443 y UDP 47800 solo en redes privadas. **Requiere consola de administrador.** Si Windows muestra un aviso de cortafuegos al arrancar, elegir "Redes privadas".
3. `invitacion` muestra un código de un solo uso; anotarlo.
4. La última orden deja corriendo la plataforma y su agente. No cerrar esa ventana.

Copiar `C:\ProgramData\SIDP\instalacion.json` a una USB. Contiene el secreto de la instalación: no enviarlo por correo ni subirlo a Internet.

## PC2 (estación)

1. Copiar `instalacion.json` de la USB a `C:\SIDP\`, junto a `sidp.exe`.
2. Ejecutar:

```bat
sidp.exe unirse --invitacion CODIGO-DE-PC1
sidp.exe
```

Debe mostrar `Plataforma "Prueba Delfino Pando" encontrada en https://IP:8443` y `Equipo autorizado.` La segunda orden deja corriendo el agente; no cerrar la ventana.

Sin invitación: `sidp.exe unirse` deja el equipo pendiente. En PC1 se aprueba con `sidp.exe identidades aprobar <nombre>-agente`.

## Prueba de conectividad

En una **segunda consola de PC1**:

```bat
sidp.exe prueba-conexion
```

En una **segunda consola de PC2**:

```bat
sidp.exe prueba-conexion
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

El resultado esperado es `RESULTADO: PASA` en los dos equipos. Cada ejecución guarda un informe JSON en `C:\ProgramData\SIDP\registros\conectividad-*.json`. Esos dos archivos son la evidencia de la prueba.

## Pruebas de resiliencia (opcionales)

1. **Red caída:** desconectar el cable o WiFi de PC2 durante 1 minuto y reconectar. El agente debe reconectarse solo; repetir `prueba-conexion` en PC1.
2. **Reinicio del servidor:** cerrar la ventana de PC1 (Ctrl+C) y volver a ejecutar `sidp.exe`. PC2 se recupera solo en menos de un minuto.
3. **Cambio de IP:** si PC1 cambia de IP, PC2 la vuelve a descubrir tras unos reintentos.
4. **Revocación:** en PC1, `sidp.exe identidades revocar <nombre>-agente`. El agente de PC2 se detiene y `prueba-conexion` en PC2 marca la credencial como revocada.

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `Descubrimiento UDP` en AVISO | La red bloquea la difusión. No impide operar: usar `sidp.exe unirse --url https://IP-DE-PC1:8443` |
| `Puerto TCP` en FALLA | PC1 apagado, `sidp.exe` cerrado en PC1, cortafuegos sin abrir o red marcada como Pública |
| `el certificado no es el de esta instalación` | El `instalacion.json` de PC2 no es el de PC1; copiarlo de nuevo |
| `Reloj` en FALLA | Corregir la hora de Windows (sincronizar con internet) |
| `Credencial agente: pendiente` | Aprobar en PC1: `sidp.exe identidades aprobar <nombre>-agente` |
| `Ida y vuelta … sin respuesta` | La ventana de `sidp.exe` en PC2 está cerrada o su agente fue revocado |

IP de PC1: `ipconfig`, línea "Dirección IPv4".

## Ensayo automático en un solo equipo

Antes de ir a la escuela se puede validar el binario en una sola PC. El comando simula dos equipos en carpetas separadas y lo ejecuta el CI en Windows:

```bat
python despliegue\ensayo_dos_equipos.py C:\SIDP\sidp.exe
```

Requiere Python y el repositorio. La salida esperada es `ENSAYO: PASA`.

## Limpiar después de la prueba

En cada equipo: cerrar `sidp.exe` y borrar `C:\ProgramData\SIDP`. En PC1, quitar las reglas de cortafuegos:

```bat
netsh advfirewall firewall delete rule name="SIDP plataforma"
netsh advfirewall firewall delete rule name="SIDP descubrimiento"
```
