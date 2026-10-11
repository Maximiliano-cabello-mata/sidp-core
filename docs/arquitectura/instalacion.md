# Instalación y alta de equipos

Objetivo: que agregar una computadora consista en **abrir `sidp.exe`** y aprobarla desde el servidor.

## Carpeta del nodo (`SIDP_HOME`)

Por defecto `C:\ProgramData\SIDP` en Windows y `~/.sidp` en Linux. Se puede cambiar con la variable `SIDP_HOME`. El ejecutable no guarda nada junto a sí mismo, así que puede vivir en una carpeta de solo lectura.

```
SIDP_HOME/
  instalacion.json          paquete: id, nombre, secreto, certificado público, puertos, perfil
  nodo.json                 equipo, roles y última URL conocida de la plataforma
  credenciales/<rol>.json   token propio de cada proceso (permisos 600 en Linux)
  plataforma/plataforma.db  solo en el servidor
  plataforma/tls/           certificado.pem y clave.pem (solo en el servidor)
  agente/pendientes.db      resultados guardados antes de enviarse
  registros/<rol>.log       rotación 1 MB × 3
```

Precedencia: argumentos > variables de entorno (`SIDP_URL`, `SIDP_TOKEN`, `SIDP_DATA_DIR`, `SIDP_AGENTE_DIR`) > archivos de `SIDP_HOME` > paquete incrustado en el ejecutable.

## 1. Servidor (una sola vez)

```bat
sidp.exe crear-instalacion --nombre "Primaria Delfino Pando"
sidp.exe
```

La primera orden crea el paquete, el certificado, la base, la identidad `operador` y la del agente local, y muestra **una sola vez** el token del operador (también lo guarda en `credenciales/admin.json`). Se niega a sobrescribir una instalación existente. La segunda orden arranca el nodo.

Opciones: `--puerto` (8443), `--equipo`, `--sin-agente`, `--sin-tls` (solo laboratorio).

## 2. Ejecutable de la escuela

Hay dos formas equivalentes:

- **Preconfigurado:** en una PC Windows con Python, ejecutar `python despliegue/compilar.py --paquete C:\ProgramData\SIDP\instalacion.json`. El resultado es `dist\sidp.exe` con el paquete incrustado.
- **Genérico + paquete:** usar el `sidp.exe` que genera CI (artefacto `sidp-windows`) y copiar `instalacion.json` en la misma carpeta.

El paquete contiene el secreto de la instalación. Se distribuye solo dentro de la escuela, por USB o carpeta restringida, nunca por Git, correo público ni CI.

## 3. Equipo nuevo

Abrir `sidp.exe` con doble clic o desde una consola. Sin `nodo.json` y con paquete disponible, el programa:

1. Busca la plataforma (difusión UDP 47800, respuesta firmada). Si no la encuentra: `sidp unirse --url https://IP:8443`.
2. Comprueba HTTPS contra el certificado del paquete.
3. Pide identidad para los roles del perfil del paquete (`estacion` = agente). El token se genera en el equipo y solo su resumen viaja.
4. Espera la aprobación y luego arranca el supervisor.

En el servidor:

```bat
sidp.exe identidades listar
sidp.exe identidades aprobar aula-2-agente
```

Alta sin espera: `sidp invitacion --rol agente --horas 24` produce un código de un solo uso. En el equipo nuevo: `sidp unirse --invitacion ABCD-1234-...`.

Otros roles: `sidp unirse --roles agente,cerebro` (perfil coordinador).

## 4. Arranque automático

El nodo es un proceso de consola. Para que arranque con el equipo:

- **Windows:** `schtasks /Create /TN SIDP /SC ONSTART /RU SYSTEM /TR "\"C:\SIDP\sidp.exe\" iniciar"`. Con `/RU SYSTEM`, `SIDP_HOME` sigue siendo `C:\ProgramData\SIDP`.
- **Linux:** una unidad systemd con `ExecStart=/opt/sidp/sidp iniciar`, `Restart=always` y `Environment=SIDP_HOME=/var/lib/sidp`.

Cortafuegos del servidor: permitir TCP 8443 y UDP 47800 **solo en la red privada**.

## 5. Reinstalar, retirar o mover equipos

- **Reinstalar un equipo:** `sidp identidades revocar <id>` y luego abrir `sidp.exe` de nuevo en ese equipo. La identidad vuelve a quedar pendiente.
- **Retirar un equipo:** revocar sus identidades y borrar su `SIDP_HOME`.
- **Cambio de IP del servidor:** no requiere acción. Los agentes redescubren solos.
- **Cambio de servidor:** ver [operación](operacion.md). Nunca dos plataformas con la misma base al mismo tiempo.

## Protocolo de descubrimiento

Solicitud UDP: `{"sidp":"buscar","instalacion":ID,"reto":aleatorio}`. Solo responde la plataforma de esa instalación, con `{"sidp":"plataforma","instalacion","reto","esquema","puerto","prueba"}`, donde `prueba = HMAC-SHA256(secreto, JSON canónico de los demás campos)`. La URL se forma con la IP de origen del paquete. Las respuestas sin firma válida se ignoran.

## Solicitud de ingreso

`POST /api/v1/enrolamiento/solicitud` con el contrato `SolicitudIngreso`: `instalacion`, `equipo`, `rol`, `token_resumen`, `sello`, `invitacion?` y `prueba`. La identidad resultante es `{equipo}-{rol}`. Si se repite con el mismo token, la respuesta es idempotente. Si llega otro token para una identidad vigente, responde 409. Con más de 20 solicitudes pendientes, responde 429.
