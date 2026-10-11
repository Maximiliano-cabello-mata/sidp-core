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
Aceptada. Por solicitud del usuario no se implementan CURP, actas ni OCR. La ruta heredada devuelve 501.

## ADR-008 — SQLite WAL como base de producción, una base por instalación
Aceptada (2026-10-11). Con tres equipos modestos y unos 140 alumnos, PostgreSQL añade un servicio, memoria y administración sin beneficio medible. Una sola `plataforma.db` en modo WAL, con `synchronous=FULL`, migraciones por módulo y `BEGIN IMMEDIATE`. Permite transacciones atómicas entre el cambio escolar y su auditoría. Se elimina SQLAlchemy/aiosqlite, lo que reduce dependencias y tamaño del ejecutable. Condición de revisión: más de un escritor concurrente sostenido, más de 2 GB de datos o acceso de muchos usuarios simultáneos. La base nunca se comparte por SMB.

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
