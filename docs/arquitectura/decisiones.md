# Decisiones de arquitectura

## ADR-001 — Dos productos y un agente, un monorepo
Aceptada. Entradas independientes y contratos compartidos, sin imports cruzados de implementación. Ampliada por ADR-009 (`sidp` como raíz de composición y `comun` como biblioteca).

## ADR-002 — Monolito modular, ejecución distribuida
Aceptada. No se crea un microservicio por función escolar: menos despliegues y una autoridad consistente, con trabajadores independientes. El contrato de módulo está en `docs/arquitectura/modulos.md`.

## ADR-003 — Servidor escolar local
Aceptada. La LAN funciona sin Internet. El acceso remoto requiere HTTPS y permisos. La nube es opcional, solo para respaldo.

## ADR-004 — SQLite transitorio
Reemplazada por ADR-008.

## ADR-005 — Repetición tolerable, efectos protegidos
Aceptada. Idempotencia en la creación, reserva exclusiva y confirmación deduplicada. No se promete ejecución exactamente una vez. Las acciones externas necesitan reconciliación antes de reintentarse.

## ADR-006 — Autonomía mediante políticas
Aceptada. El cerebro coordina y la plataforma autoriza. Sin shell genérico ni autoprogramación. La IA es opcional.

## ADR-007 — Documentos fuera de alcance
Sustituida por ADR-022. Antes: los documentos (CURP, actas, OCR) estaban fuera de alcance. La ruta heredada con simulacion RENAPO devuelve 501 hasta que exista el verificador oficial asistido.

## ADR-008 — SQLite WAL como base de producción, una base por instalación
Aceptada (2026-10-11). Con tres equipos modestos y unos 140 alumnos, PostgreSQL añade un servicio, memoria y administración sin beneficio medible. Una sola `plataforma.db` en modo WAL, con `synchronous=FULL`, migraciones por módulo y `BEGIN IMMEDIATE`. Permite transacciones atómicas entre el cambio escolar y su auditoría. Se elimina SQLAlchemy/aiosqlite, lo que reduce dependencias y tamaño del ejecutable. Condición de revisión: contención sostenida medida, necesidad de escritores independientes o requisitos de réplica; no un umbral fijo de tamaño. La base nunca se comparte por SMB.

## ADR-009 — Un solo ejecutable con roles
Aceptada. `sidp.exe` contiene plataforma, agente, cerebro y supervisor; la configuración decide qué corre en cada equipo. Se distribuye y actualiza un solo archivo. Cada rol sigue siendo un proceso con su propia credencial. Paquetes: `sidp` (composición, único que importa todo) y `comun` (sin dependencias internas).

## ADR-010 — Paquete de instalación y enrolamiento con aprobación
Aceptada. La instalación se define con un paquete: id, secreto de 256 bits y certificado público. Puede incrustarse en el ejecutable o acompañarlo. Los equipos prueban pertenencia con HMAC, generan su token localmente (el servidor guarda solo su SHA-256) y quedan pendientes hasta que el administrador los aprueba, o entran al instante con una invitación de un solo uso. Alternativas descartadas: tokens en variables de entorno (difícil de instalar y propenso a errores) y mTLS con autoridad certificadora propia (más complejo de operar sin aportar más en una LAN escolar). `SIDP_IDENTIDADES` queda solo para laboratorio y pruebas.

## ADR-011 — TLS autofirmado con certificado fijado
Aceptada. Las IP de la LAN cambian y no hay DNS interno, así que la confianza se basa en el certificado exacto del paquete (sin verificar el nombre del host), no en una CA pública. Clave EC P-256, con 10 años de vigencia. Pendiente: procedimiento de rotación.

## ADR-012 — Descubrimiento UDP firmado
Aceptada. Difusión en UDP 47800 y respuesta firmada con HMAC del secreto, lo que evita impostores y mezclar escuelas. Plan B: URL fija (`--url` o `nodo.json`). Se descarta mDNS/zeroconf: más dependencias y comportamiento irregular en Windows.

## ADR-013 — Supervisor propio en lugar de servicios del sistema
Aceptada. `sidp iniciar` lanza un proceso hijo por rol y lo reinicia con espera creciente; el código de salida 3 indica un error de credencial. El arranque con el equipo se delega en el programador de tareas o systemd, con una sola línea. Así se evita mantener instaladores de servicios por cada sistema operativo.

## ADR-014 — Módulos estáticos
Aceptada. Los módulos y capacidades se registran en código y se compilan en el ejecutable. Sin descarga ni carga dinámica: lo que corre es exactamente lo que se probó. Las actualizaciones reemplazan el ejecutable completo (actualización firmada pendiente).


## ADR-015 — Base investigada: comunicación, recursos y SQL

Aceptada 2026-10-11 UTC. Ver investigación con fuentes primarias. HTTPS/JSON y pull de tareas, outbox transaccional con inbox del cerebro; autoridad de escritura única. MQTT/gRPC/consenso quedan como alternativas documentadas. SQLite se mantiene sin inventar procedimientos almacenados: servicios transaccionales Python, SQL restringido, vista e integridad mediante trigger. El esquema se exporta desde migraciones.

## ADR-016 — Admisión y revisiones

Aceptada. Telemetría acotada, política por equipo con revisión esperada y cupos de cola. No elevar recursos por código remoto. Agentes anteriores conservan compatibilidad echo; los nuevos exigen muestra vigente. Las muestras no son atestación de seguridad ni límites duros del SO.

## ADR-017 — Eventos, no event sourcing

Aceptada. Diario append-only a nivel de aplicación, con UUID/cursor y consumo idempotente. No almacena mensajes de tareas en sus metadatos. Tablas de dominio siguen siendo autoridad. Retención y tratamiento de cursores después de una restauración requieren operación explícita. El observador no ejecuta automáticamente acciones administrativas.

## ADR-018 — Transporte y supervisor

Corregir confianza TLS: contexto sin autoridades del sistema; solo certificado del paquete. Rechazar degradación HTTP. Cerebro supervisado usa --servicio; --clave es comando puntual. No reintentos automáticos de cualquier POST; backoff solo en bucles que conocen la semántica.

## ADR-019 - Plataforma unica en una PC administrativa; OneDrive para respaldo

Aceptada 2026-10-11. No hay servidor dedicado ni presupuesto para base de datos o nube de pago; se dispone de una cuenta Microsoft institucional de 100 GB. Se adopta la base tecnica (ADR-003, 008 a 018): una plataforma con SQLite WAL corre en una PC administrativa encendida en horario escolar; su costo medido es de decenas de MB. Los demas equipos y celulares se conectan a ella. La cuenta Microsoft guarda respaldos cifrados automaticos y sirve de recuperacion de emergencia; no es autoridad de datos. Las replicas por dispositivo con escritura multiple quedan como mejora futura por su complejidad. Riesgo aceptado: esa PC es punto unico de falla; mitigar con respaldo diario automatico, copia externa y recuperacion en otro equipo.

## ADR-020 - Acceso remoto de docentes

Aceptada como direccion, pendiente de validar. Algunos docentes necesitan usar el sistema fuera de la escuela. No se abren puertos del router: un tunel saliente desde la PC de la plataforma (por ejemplo Cloudflare Tunnel o Tailscale, con nivel gratuito) publica solo la PWA y la API con HTTPS de certificado publico valido, porque un navegador de celular no acepta el certificado autofirmado fijado de ADR-011, que se mantiene solo para agentes. Requiere login de personal (usuarios, roles, sesion con expiracion, limite de intentos y registro) antes de habilitarse. Sin la PC encendida no hay acceso remoto. Pendiente: elegir tunel, privacidad de menores en transito y aviso de privacidad. El mismo problema de certificado existe dentro de la LAN: un celular conectado al WiFi de la escuela tampoco acepta el certificado autofirmado. Antes de la PWA docente hay que decidir como llega el navegador a la plataforma en la LAN (opciones a evaluar: usar siempre el tunel, nombre de dominio con certificado publico, o instalar una autoridad propia en cada celular).

## ADR-021 - Nucleo consolidado y modulos de automatizacion

Aceptada 2026-10-11. El nucleo ofrece identidad, roles de personal, dispositivos, auditoria, documentos, comunicacion y cola de tareas sobre el contrato de modulos de la base tecnica. Cada funcion escolar es un modulo con tablas, migraciones, rutas y permisos propios, sin importar a otros. Ver catalogo_modulos.md.

## ADR-022 - Expediente documental con validacion tecnica (sustituye ADR-007)

Aceptada 2026-10-11. Los documentos del alumno deben cumplir validacion real. Se define una base tecnica de cuatro niveles (integridad y estructura, extraccion y cruce, verificacion oficial asistida, cotejo humano) con evidencia auditable por cada comprobacion. Un documento solo es alidado si cumple las reglas obligatorias de su tipo y una persona lo confirma; ningun proceso automatico lo valida solo. La verificacion oficial (CURP en RENAPO, acta por QR y CEVAR) es asistida hasta confirmar un canal autorizado de API. Ver validacion_documental.md y modulo_expediente.md.

## ADR-023 - Dos plataformas sobre un nucleo; el cerebro es un producto aparte

Aceptada 2026-10-11. El producto escolar se organiza en dos plataformas sobre un mismo nucleo:

- **Docentes:** celular (PWA) y PC. Evaluaciones, asistencia, reportes de alumno y contacto con padres.
- **Administrativos:** PC. Inscripcion y expediente, validacion de documentos, estadistica e impresion.

Ambas usan la misma plataforma, base y permisos (ADR-019, ADR-021); se distinguen por interfaz y rol, no por servidor. El cerebro que aprende (`cerebro_aprendizaje.md`) es un producto aparte: el sistema administrativo opera completo sin el, y el cerebro solo accede por la API con identidad propia (ADR-006). Nada del sistema administrativo importa codigo del cerebro. Foro y anuncios quedan fuera de alcance.

## ADR-024 - Tareas dirigidas y prueba de conectividad

Aceptada 2026-10-13. Una tarea puede llevar `destino` (identidad de un agente); solo ese agente la reclama. Se usa para comprobar un equipo concreto y, en el futuro, para perifericos conectados a una PC (impresion). `sidp prueba-conexion` verifica descubrimiento, puerto, TLS fijado, reloj, credenciales y, desde el servidor, una ida y vuelta con cada agente remoto; guarda un informe JSON como evidencia. CI ejecuta el mismo flujo con el `.exe` real simulando dos equipos (`despliegue/ensayo_dos_equipos.py`). No sustituye la prueba en las computadoras de la escuela (`docs/PRUEBA_DOS_EQUIPOS.md`).
