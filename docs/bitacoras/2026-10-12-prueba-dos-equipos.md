# Registro de sesión — Prueba de dos equipos (PC1 ↔ PC2) — 2026-10-12

Bitácora de la puesta en marcha de la prueba de dos computadoras con `sidp.exe`: los
errores que aparecieron, su causa y cómo se resolvieron. El procedimiento oficial está
en `docs/guias/PRUEBA_DOS_EQUIPOS.md`; esto documenta un caso real que se desvió de él.

> Datos del entorno: PC1 = servidor (`192.168.100.18:8443`), PC2 = estación (host `KANEDA`,
> Windows + WSL2). Clave de escuela usada: valor de prueba de 8 dígitos (**cámbiala por una
> frase larga antes de usarla en la escuela**). En este documento no se incluyen el secreto
> derivado ni el certificado.

## 1. Objetivo

Unir PC2 como estación (rol `agente`) a la plataforma de PC1 y validar la conexión con
`sidp.exe prueba-conexion`, hasta obtener `RESULTADO: PASA` con la ida y vuelta de trabajo
entre ambos equipos.

## 2. Síntomas y errores encontrados (orden cronológico)

| # | Comando / acción | Error observado | Qué significaba |
|---|---|---|---|
| 1 | `sidp.exe unirse --invitacion CODIGO` | `No se encontró instalacion.json; indique --paquete RUTA` | PC2 no tenía el paquete de PC1. `unirse` necesita el `instalacion.json` (certificado + secreto); la invitación **no lo sustituye**. |
| 2 | Estado de PC2 antes del arreglo | `prueba-conexion` daba `PASA` pero `[AVISO] Ida y vuelta: no hay otro equipo con agente en línea` | PC2 se había convertido en **su propio servidor**: `nodo.json` con roles `[plataforma, agente]`, `url https://127.0.0.1:8443`, certificado emitido para `KANEDA/localhost` y credencial `admin`. Se estaba probando contra sí misma. |
| 3 | Doble clic en `sidp.exe` | `No hay configuración en C:\ProgramData\SIDP` y se cierra | Sin argumentos ni clave, el binario no se une; solo muestra la ayuda inicial. |
| 4 | `sidp.exe iniciar --clave X --url Y` | `unrecognized arguments: --clave --url` (exit 2) | El **binario compilado es más viejo que el repo**: su `iniciar` no acepta banderas. |
| 5 | `SIDP_CLAVE=... sidp.exe iniciar` (en segundo plano) | Volvió a `No hay configuración` (exit 2) | El exe no tomó la variable de entorno y, sin terminal interactiva (TTY), tampoco pide la clave. |

Comprobación de capacidades reales del binario:

```
sidp iniciar -h   ->  usage: sidp iniciar [-h]            (sin --clave ni --url)
sidp unirse  -h   ->  [--paquete] [--url] [--roles] [--equipo] [--invitacion] [--no-esperar]
```

## 3. Causa raíz

1. **Binario desactualizado.** El `sidp.exe` en uso no incluye la unión por *clave de
   escuela* sobre URL (ADR-025 `sidp/automatico.py`), que en el repo permite
   `iniciar --clave --url` sin USB. En este binario, la única forma de unir es
   `unirse --paquete instalacion.json`, que exige el archivo de PC1.
2. **PC2 quedó como servidor propio.** Un primer arranque sin encontrar a PC1 (red pública,
   PC1 apagado, o el descubrimiento desviado por un adaptador virtual) hizo que PC2 creara
   su propia instalación. Dos servidores separados no se ven entre sí.
3. **Adaptador virtual `192.168.56.1`** (VirtualBox/Hyper-V host-only) interfería con el
   descubrimiento UDP: la respuesta encontrada era la de la propia PC2.

## 4. Resolución aplicada

### 4.1 Reset de PC2
```bat
taskkill /IM sidp.exe /F
rmdir /s /q C:\ProgramData\SIDP
```
Se restauró `C:\SIDP\sidp.exe` (y `PRUEBA_DOS_EQUIPOS.md`) desde el artefacto descargado.

### 4.2 Reconstrucción del `instalacion.json` desde la red (sin USB)
Como el binario viejo no deriva el paquete por clave, se reprodujo manualmente lo que hace
la versión nueva (`sidp/automatico.py` + `comun/firma.py`):

1. **Derivar id + secreto** de la clave de escuela:
   `PBKDF2-HMAC-SHA256(clave_normalizada, salt=b'sidp-clave-escuela-v1', iter=200000, dklen=48)`
   → `id = UUIDv4(material[:16])`, `secreto = base64(material[16:48])`.
   Normalización de la clave: `' '.join(clave.split()).lower()`.
2. **Descargar el paquete público** de PC1 (TLS sin verificar; la confianza la da la firma):
   `GET https://192.168.100.18:8443/api/v1/enrolamiento/paquete`.
3. **Verificar la firma** `prueba` con HMAC-SHA256 sobre el JSON canónico
   (`sort_keys`, `separators=(',',':')`, `ensure_ascii=False`) usando el secreto derivado.
   El `id` devuelto por PC1 coincidió con el derivado y la firma fue válida → **la clave es
   correcta y el paquete es auténtico**.
4. **Escribir** `C:\SIDP\instalacion.json` con los campos del dataclass `Paquete`
   (`instalacion, nombre, secreto, certificado, puerto, puerto_descubrimiento, url, perfil,
   por_clave=true, formato`), fijando `url = https://192.168.100.18:8443`.

### 4.3 Unión y verificación
```bat
sidp.exe unirse --url https://192.168.100.18:8443 --no-esperar
   -> Plataforma "SIDP" encontrada; agente: kaneda-agente -> aprobada
sidp.exe iniciar            (arranca el agente)
sidp.exe prueba-conexion
```

Resultado final en PC2:

```
[ OK  ] Este equipo                 kaneda, roles: agente
[ OK  ] Puerto TCP                  192.168.100.18:8443 abierto
[ OK  ] HTTPS con certificado fijado
[ OK  ] Reloj                       desfase 3 s
[ OK  ] Credencial agente           kaneda-agente: aprobada
[ OK  ] Agente autorizado           la plataforma acepta trabajo de este equipo
[AVISO] Descubrimiento UDP          sin respuesta en UDP 47800; se usa la URL guardada
RESULTADO: PASA (8 pruebas, 1 avisos)
```

El único aviso (descubrimiento UDP) es benigno: la conexión usa la URL guardada de PC1.
La ida y vuelta de trabajo se confirma desde PC1 con `sidp.exe prueba-conexion`
(renglón `Ida y vuelta … kaneda-agente … [ OK ]`).

## 5. Recomendaciones

1. **Actualizar el binario** al build nuevo (el que trae `iniciar --clave --url` / ADR-025);
   con él, PC2 se une sin reconstruir el paquete a mano.
2. **Clave de escuela:** sustituir el valor de prueba de 8 dígitos por una frase larga.
3. **Descubrimiento:** si hay adaptadores virtuales (`192.168.56.x`), preferir `--url` con la
   IP real de PC1, o deshabilitar el adaptador durante la prueba.
4. **Red en PC1:** marcada como *Privada* y `cortafuegos` aplicado (TCP 8443, UDP 47800).
5. **Camino sin USB documentado:** la reconstrucción del paquete desde `/enrolamiento/paquete`
   usando la clave es viable y seguro (la firma valida la autenticidad), pero lo ideal es que
   lo haga el propio `sidp.exe` actualizado.
