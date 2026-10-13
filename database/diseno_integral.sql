-- Diseño integral de la base escolar de SIDP (fases 4 a 9). Explicación en docs/arquitectura/base_de_datos.md.
-- Es un diseño de referencia: cada módulo lo incorporará como migraciones propias y aditivas.
-- No ejecutar sobre una base existente. Las tablas técnicas actuales (esquema, identidades, tareas...) no cambian.
--
-- Contramedidas que este archivo aplica en el propio motor:
--   C1 Nada se borra: triggers impiden DELETE; se usan estados (baja, retirado, archivado).
--   C2 Sin borrados en cascada: toda clave foránea es RESTRICT.
--   C3 Identificadores UUID inmutables; la CURP es un dato, nunca la llave.
--   C4 Concurrencia optimista: columna version que solo sube de 1 en 1.
--   C5 Bitácora solo de escritura: no se modifica ni se borra.
--   C6 Archivos por contenido (sha256) e inmutables; una corrección es una versión nueva.
--   C7 Periodos y ciclos cerrados no aceptan cambios; las correcciones quedan aparte con motivo.
--   C8 Tablas STRICT y CHECK en estados, rangos y formatos.
--   C9 Importaciones idempotentes: el mismo archivo no se carga dos veces.
--   C10 La IA solo propone en su propia tabla; nunca escribe datos escolares.

PRAGMA foreign_keys = ON;

BEGIN;

-- ============================================================ Escuela y calendario

CREATE TABLE escuela (
  id INTEGER PRIMARY KEY CHECK (id = 1),                       -- una sola fila
  cct TEXT NOT NULL CHECK (length(cct) = 10 AND cct GLOB '15[A-Z]PR[0-9][0-9][0-9][0-9][A-Z]'),
  nombre TEXT NOT NULL,
  turno TEXT NOT NULL CHECK (turno IN ('matutino','vespertino','tiempo_completo')),
  zona_escolar TEXT,
  domicilio TEXT,
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE ciclo (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  nombre TEXT NOT NULL UNIQUE CHECK (nombre GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]'),
  inicio TEXT NOT NULL,
  fin TEXT NOT NULL CHECK (fin > inicio),
  estado TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('preparacion','abierto','cerrado')),
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE periodo (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  ciclo_id TEXT NOT NULL REFERENCES ciclo(id) ON DELETE RESTRICT,
  numero INTEGER NOT NULL CHECK (numero BETWEEN 1 AND 3),
  inicio TEXT NOT NULL,
  fin TEXT NOT NULL CHECK (fin > inicio),
  estado TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto','cerrado')),
  version INTEGER NOT NULL DEFAULT 1,
  UNIQUE (ciclo_id, numero)
) STRICT;

CREATE TABLE campo_formativo (                                  -- catálogo NEM, Plan 2022
  clave TEXT PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  vigente INTEGER NOT NULL DEFAULT 1 CHECK (vigente IN (0,1))
) STRICT;

-- ============================================================ Personal y cuentas

CREATE TABLE personal (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  curp TEXT UNIQUE CHECK (curp IS NULL OR (length(curp) = 18 AND curp GLOB '[A-Z][AEIOUX][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9][HMX][A-Z][A-Z][A-Z][A-Z][A-Z][0-9A-Z][0-9]')),
  nombres TEXT NOT NULL,
  primer_apellido TEXT NOT NULL,
  segundo_apellido TEXT,
  puesto TEXT NOT NULL CHECK (puesto IN ('director','subdirector','secretaria','docente','docente_especial','apoyo','intendencia')),
  telefono TEXT,
  correo TEXT,
  estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','licencia','baja')),
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE usuario (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  personal_id TEXT NOT NULL UNIQUE REFERENCES personal(id) ON DELETE RESTRICT,
  nombre_usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
  contrasena_resumen TEXT NOT NULL,                            -- scrypt o PBKDF2 con sal; nunca la contraseña
  rol TEXT NOT NULL CHECK (rol IN ('direccion','administrativo','docente','tecnico')),
  estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','bloqueado','baja')),
  intentos_fallidos INTEGER NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
  bloqueado_hasta TEXT,
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE sesion (
  token_resumen TEXT PRIMARY KEY,                              -- solo el resumen del token
  usuario_id TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  creada TEXT NOT NULL,
  vence TEXT NOT NULL CHECK (vence > creada),
  revocada TEXT
) STRICT;

-- ============================================================ Alumnos, tutores e inscripciones

CREATE TABLE alumno (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  curp TEXT UNIQUE CHECK (curp IS NULL OR (length(curp) = 18 AND curp GLOB '[A-Z][AEIOUX][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9][HMX][A-Z][A-Z][A-Z][A-Z][A-Z][0-9A-Z][0-9]')),
  curp_confirmada INTEGER NOT NULL DEFAULT 0 CHECK (curp_confirmada IN (0,1)),
  nombres TEXT NOT NULL,
  primer_apellido TEXT NOT NULL,
  segundo_apellido TEXT,
  fecha_nacimiento TEXT,
  sexo TEXT CHECK (sexo IS NULL OR sexo IN ('H','M','X')),
  estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','baja','egresado','archivado')),
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE alumno_salud (                                     -- datos sensibles separados, permiso propio
  alumno_id TEXT PRIMARY KEY REFERENCES alumno(id) ON DELETE RESTRICT,
  tipo_sangre TEXT,
  alergias TEXT,
  condiciones TEXT,
  contacto_emergencia TEXT,
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE tutor (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  curp TEXT UNIQUE CHECK (curp IS NULL OR (length(curp) = 18 AND curp GLOB '[A-Z][AEIOUX][A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9][HMX][A-Z][A-Z][A-Z][A-Z][A-Z][0-9A-Z][0-9]')),
  nombres TEXT NOT NULL,
  primer_apellido TEXT NOT NULL,
  segundo_apellido TEXT,
  telefono TEXT,
  correo TEXT,
  domicilio TEXT,
  estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','inactivo')),
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE alumno_tutor (
  alumno_id TEXT NOT NULL REFERENCES alumno(id) ON DELETE RESTRICT,
  tutor_id TEXT NOT NULL REFERENCES tutor(id) ON DELETE RESTRICT,
  parentesco TEXT NOT NULL CHECK (parentesco IN ('madre','padre','tutor_legal','abuelo','otro')),
  principal INTEGER NOT NULL DEFAULT 0 CHECK (principal IN (0,1)),
  puede_recoger INTEGER NOT NULL DEFAULT 1 CHECK (puede_recoger IN (0,1)),
  vigente INTEGER NOT NULL DEFAULT 1 CHECK (vigente IN (0,1)),
  PRIMARY KEY (alumno_id, tutor_id)
) STRICT;
CREATE UNIQUE INDEX un_tutor_principal ON alumno_tutor(alumno_id) WHERE principal = 1 AND vigente = 1;

CREATE TABLE grupo (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  ciclo_id TEXT NOT NULL REFERENCES ciclo(id) ON DELETE RESTRICT,
  grado INTEGER NOT NULL CHECK (grado BETWEEN 1 AND 6),
  letra TEXT NOT NULL CHECK (letra GLOB '[A-Z]'),
  docente_id TEXT REFERENCES personal(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL DEFAULT 1,
  UNIQUE (ciclo_id, grado, letra)
) STRICT;

CREATE TABLE inscripcion (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  alumno_id TEXT NOT NULL REFERENCES alumno(id) ON DELETE RESTRICT,
  ciclo_id TEXT NOT NULL REFERENCES ciclo(id) ON DELETE RESTRICT,
  grupo_id TEXT NOT NULL REFERENCES grupo(id) ON DELETE RESTRICT,
  tipo TEXT NOT NULL CHECK (tipo IN ('nuevo_ingreso','reinscripcion','traslado')),
  origen TEXT NOT NULL DEFAULT 'captura' CHECK (origen IN ('captura','said','importacion')),
  estado TEXT NOT NULL DEFAULT 'incompleta' CHECK (estado IN ('incompleta','completa','baja','cancelada')),
  alta TEXT NOT NULL,
  baja TEXT,
  motivo_baja TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  CHECK (estado <> 'baja' OR (baja IS NOT NULL AND motivo_baja IS NOT NULL))
) STRICT;
CREATE UNIQUE INDEX una_inscripcion_por_ciclo ON inscripcion(alumno_id, ciclo_id) WHERE estado <> 'cancelada';

-- ============================================================ Calificaciones, asistencia y diagnósticos

CREATE TABLE calificacion (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  inscripcion_id TEXT NOT NULL REFERENCES inscripcion(id) ON DELETE RESTRICT,
  periodo_id TEXT NOT NULL REFERENCES periodo(id) ON DELETE RESTRICT,
  campo TEXT NOT NULL REFERENCES campo_formativo(clave) ON DELETE RESTRICT,
  valor INTEGER NOT NULL CHECK (valor BETWEEN 5 AND 10),          -- el mínimo por grado lo aplica el servicio
  observaciones TEXT,
  capturo TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL DEFAULT 1,
  UNIQUE (inscripcion_id, periodo_id, campo)
) STRICT;

CREATE TABLE calificacion_correccion (                          -- C7: cambios después de cerrar el periodo
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  calificacion_id TEXT NOT NULL REFERENCES calificacion(id) ON DELETE RESTRICT,
  valor_nuevo INTEGER NOT NULL CHECK (valor_nuevo BETWEEN 5 AND 10),
  motivo TEXT NOT NULL CHECK (length(motivo) >= 10),
  autorizo TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL
) STRICT;

CREATE VIEW calificacion_vigente AS
SELECT c.id, c.inscripcion_id, c.periodo_id, c.campo,
       COALESCE((SELECT k.valor_nuevo FROM calificacion_correccion k WHERE k.calificacion_id = c.id
                 ORDER BY k.fecha DESC, k.id DESC LIMIT 1), c.valor) AS valor,
       c.observaciones
FROM calificacion c;

CREATE TABLE asistencia_alumno (
  inscripcion_id TEXT NOT NULL REFERENCES inscripcion(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL,
  estado TEXT NOT NULL CHECK (estado IN ('presente','falta','retardo','justificada')),
  capturo TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (inscripcion_id, fecha)
) STRICT;

CREATE TABLE asistencia_personal (
  personal_id TEXT NOT NULL REFERENCES personal(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL,
  entrada TEXT,
  salida TEXT CHECK (salida IS NULL OR entrada IS NULL OR salida > entrada),
  estado TEXT NOT NULL CHECK (estado IN ('asistio','falta','permiso','licencia','comision')),
  motivo TEXT,
  capturo TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (personal_id, fecha)
) STRICT;

CREATE TABLE examen_diagnostico (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  ciclo_id TEXT NOT NULL REFERENCES ciclo(id) ON DELETE RESTRICT,
  grado INTEGER NOT NULL CHECK (grado BETWEEN 1 AND 6),
  nombre TEXT NOT NULL,
  fecha TEXT NOT NULL,
  UNIQUE (ciclo_id, grado, nombre)
) STRICT;

CREATE TABLE resultado_diagnostico (
  examen_id TEXT NOT NULL REFERENCES examen_diagnostico(id) ON DELETE RESTRICT,
  inscripcion_id TEXT NOT NULL REFERENCES inscripcion(id) ON DELETE RESTRICT,
  campo TEXT NOT NULL REFERENCES campo_formativo(clave) ON DELETE RESTRICT,
  puntaje REAL CHECK (puntaje IS NULL OR puntaje BETWEEN 0 AND 100),
  nivel TEXT CHECK (nivel IS NULL OR nivel IN ('requiere_apoyo','en_proceso','esperado','sobresaliente')),
  capturo TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  PRIMARY KEY (examen_id, inscripcion_id, campo)
) STRICT;

-- ============================================================ Archivos y expediente documental

CREATE TABLE archivo (                                          -- C6: contenido inmutable, sin binarios en la base
  sha256 TEXT PRIMARY KEY CHECK (length(sha256) = 64),
  tamano INTEGER NOT NULL CHECK (tamano > 0 AND tamano <= 52428800),   -- tope 50 MB por archivo
  tipo_mime TEXT NOT NULL CHECK (tipo_mime IN ('application/pdf','image/jpeg','image/png','image/webp',
     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')),
  ruta_relativa TEXT NOT NULL UNIQUE CHECK (ruta_relativa NOT LIKE '/%' AND ruta_relativa NOT LIKE '%..%'),
  creado TEXT NOT NULL,
  copias_confirmadas INTEGER NOT NULL DEFAULT 0 CHECK (copias_confirmadas >= 0)   -- lo actualiza la réplica (ADR-027)
) STRICT;

CREATE TABLE tipo_documento (
  clave TEXT PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  aplica_a TEXT NOT NULL CHECK (aplica_a IN ('alumno','tutor','personal')),
  obligatorio_nuevo INTEGER NOT NULL DEFAULT 1 CHECK (obligatorio_nuevo IN (0,1)),
  obligatorio_reinscripcion INTEGER NOT NULL DEFAULT 0 CHECK (obligatorio_reinscripcion IN (0,1)),
  caducidad TEXT NOT NULL CHECK (caducidad IN ('nunca','por_ciclo','fecha')),
  vigente INTEGER NOT NULL DEFAULT 1 CHECK (vigente IN (0,1))
) STRICT;

CREATE TABLE documento (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  tipo TEXT NOT NULL REFERENCES tipo_documento(clave) ON DELETE RESTRICT,
  alumno_id TEXT REFERENCES alumno(id) ON DELETE RESTRICT,
  tutor_id TEXT REFERENCES tutor(id) ON DELETE RESTRICT,
  personal_id TEXT REFERENCES personal(id) ON DELETE RESTRICT,
  ciclo_id TEXT REFERENCES ciclo(id) ON DELETE RESTRICT,          -- para los que caducan por ciclo
  archivo_sha256 TEXT NOT NULL REFERENCES archivo(sha256) ON DELETE RESTRICT,
  reemplaza_a TEXT REFERENCES documento(id) ON DELETE RESTRICT,   -- versión anterior
  origen TEXT NOT NULL CHECK (origen IN ('escaneo','foto','buzon','papel','mige','generado')),
  estado TEXT NOT NULL DEFAULT 'recibido' CHECK (estado IN ('recibido','validado','rechazado','vencido','reemplazado')),
  motivo_rechazo TEXT,
  recibio TEXT REFERENCES usuario(id) ON DELETE RESTRICT,
  recibido TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  CHECK ((alumno_id IS NOT NULL) + (tutor_id IS NOT NULL) + (personal_id IS NOT NULL) = 1),   -- un solo dueño
  CHECK (estado <> 'rechazado' OR motivo_rechazo IS NOT NULL)
) STRICT;
CREATE INDEX documento_alumno ON documento(alumno_id, tipo);
CREATE INDEX documento_tutor ON documento(tutor_id, tipo);

CREATE TABLE revision_documento (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  documento_id TEXT NOT NULL REFERENCES documento(id) ON DELETE RESTRICT,
  resultado TEXT NOT NULL CHECK (resultado IN ('validado','rechazado')),
  motivo TEXT,
  reviso TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,  -- siempre una persona, nunca la IA
  fecha TEXT NOT NULL,
  CHECK (resultado <> 'rechazado' OR motivo IS NOT NULL)
) STRICT;

CREATE TABLE prorroga (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  inscripcion_id TEXT NOT NULL REFERENCES inscripcion(id) ON DELETE RESTRICT,
  tipo TEXT NOT NULL REFERENCES tipo_documento(clave) ON DELETE RESTRICT,
  compromiso TEXT NOT NULL,
  motivo TEXT NOT NULL,
  autorizo TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL
) STRICT;

-- ============================================================ Catálogo de formatos y documentos emitidos

CREATE TABLE formato (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  nombre TEXT NOT NULL,
  emisor TEXT NOT NULL CHECK (emisor IN ('sep','edomex','seiem','escuela','otro')),
  version INTEGER NOT NULL CHECK (version >= 1),
  plantilla_sha256 TEXT NOT NULL REFERENCES archivo(sha256) ON DELETE RESTRICT,
  estado TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador','vigente','retirado')),
  oficial INTEGER NOT NULL DEFAULT 0 CHECK (oficial IN (0,1)),     -- si no, se imprime "solo consulta"
  UNIQUE (nombre, version)
) STRICT;
CREATE UNIQUE INDEX un_formato_vigente ON formato(nombre) WHERE estado = 'vigente';

CREATE TABLE formato_campo (
  formato_id TEXT NOT NULL REFERENCES formato(id) ON DELETE RESTRICT,
  clave TEXT NOT NULL,
  etiqueta TEXT NOT NULL,
  fuente TEXT NOT NULL,                                          -- p. ej. 'alumno.curp', 'escuela.cct', 'manual'
  posicion TEXT CHECK (posicion IS NULL OR json_valid(posicion)),
  propuesto_por TEXT NOT NULL DEFAULT 'persona' CHECK (propuesto_por IN ('persona','cerebro')),
  confirmado_por TEXT REFERENCES usuario(id) ON DELETE RESTRICT,
  PRIMARY KEY (formato_id, clave)
) STRICT;

CREATE TABLE folio_serie (
  serie TEXT PRIMARY KEY,                                        -- p. ej. 'CONST-2026'
  siguiente INTEGER NOT NULL CHECK (siguiente >= 1)
) STRICT;

CREATE TABLE documento_emitido (
  folio TEXT PRIMARY KEY,                                        -- impreso con QR de verificación
  formato_id TEXT NOT NULL REFERENCES formato(id) ON DELETE RESTRICT,
  alumno_id TEXT REFERENCES alumno(id) ON DELETE RESTRICT,
  grupo_id TEXT REFERENCES grupo(id) ON DELETE RESTRICT,
  archivo_sha256 TEXT NOT NULL REFERENCES archivo(sha256) ON DELETE RESTRICT,
  datos TEXT NOT NULL CHECK (json_valid(datos)),                 -- valores usados, para reproducirlo
  emitio TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL,
  estado TEXT NOT NULL DEFAULT 'valido' CHECK (estado IN ('valido','cancelado'))
) STRICT;

-- ============================================================ Inventario

CREATE TABLE bien (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  clave_inventario TEXT UNIQUE,
  descripcion TEXT NOT NULL,
  categoria TEXT NOT NULL CHECK (categoria IN ('mobiliario','computo','material_didactico','deportivo','otro')),
  ubicacion TEXT,
  estado TEXT NOT NULL DEFAULT 'bueno' CHECK (estado IN ('bueno','regular','malo','baja')),
  alta TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE TABLE bien_movimiento (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  bien_id TEXT NOT NULL REFERENCES bien(id) ON DELETE RESTRICT,
  tipo TEXT NOT NULL CHECK (tipo IN ('alta','cambio_ubicacion','cambio_estado','baja')),
  detalle TEXT NOT NULL,
  registro TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL
) STRICT;

-- ============================================================ Padres: buzón, consentimientos y solicitudes

CREATE TABLE buzon_entrada (                                    -- C9: lo que llega del buzón, sin duplicados
  id_externo TEXT PRIMARY KEY,
  tutor_id TEXT REFERENCES tutor(id) ON DELETE RESTRICT,
  alumno_id TEXT REFERENCES alumno(id) ON DELETE RESTRICT,
  tipo TEXT REFERENCES tipo_documento(clave) ON DELETE RESTRICT,
  archivo_sha256 TEXT NOT NULL REFERENCES archivo(sha256) ON DELETE RESTRICT,
  documento_id TEXT REFERENCES documento(id) ON DELETE RESTRICT,
  recibido TEXT NOT NULL,
  confirmado_al_buzon TEXT                                       -- cuando el buzón ya puede borrarlo
) STRICT;

CREATE TABLE aviso_privacidad (
  version INTEGER PRIMARY KEY CHECK (version >= 1),
  archivo_sha256 TEXT NOT NULL REFERENCES archivo(sha256) ON DELETE RESTRICT,
  vigente_desde TEXT NOT NULL
) STRICT;

CREATE TABLE consentimiento (
  tutor_id TEXT NOT NULL REFERENCES tutor(id) ON DELETE RESTRICT,
  aviso_version INTEGER NOT NULL REFERENCES aviso_privacidad(version) ON DELETE RESTRICT,
  fecha TEXT NOT NULL,
  medio TEXT NOT NULL CHECK (medio IN ('buzon','papel')),
  PRIMARY KEY (tutor_id, aviso_version)
) STRICT;

CREATE TABLE solicitud_cambio (                                 -- el tutor propone, el personal aprueba
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  tutor_id TEXT NOT NULL REFERENCES tutor(id) ON DELETE RESTRICT,
  campo TEXT NOT NULL CHECK (campo IN ('telefono','correo','domicilio')),
  valor_nuevo TEXT NOT NULL,
  estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','aprobada','rechazada')),
  reviso TEXT REFERENCES usuario(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL,
  CHECK (estado = 'pendiente' OR reviso IS NOT NULL)
) STRICT;

CREATE TABLE aviso (
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  titulo TEXT NOT NULL,
  cuerpo TEXT NOT NULL,
  destinatarios TEXT NOT NULL CHECK (json_valid(destinatarios)),  -- grupos, grados o toda la escuela
  autor TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  estado TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador','aprobado','publicado','retirado')),
  fecha TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
) STRICT;

-- ============================================================ Operación: importaciones, respaldos, IA y bitácora

CREATE TABLE importacion (                                      -- C9: el mismo archivo no se importa dos veces
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  archivo_sha256 TEXT NOT NULL UNIQUE REFERENCES archivo(sha256) ON DELETE RESTRICT,
  tipo TEXT NOT NULL CHECK (tipo IN ('alumnos','tutores','said','personal','bienes','certificados_mige')),
  filas_leidas INTEGER NOT NULL DEFAULT 0,
  filas_aplicadas INTEGER NOT NULL DEFAULT 0,
  errores TEXT CHECK (errores IS NULL OR json_valid(errores)),
  estado TEXT NOT NULL CHECK (estado IN ('revisando','aplicada','descartada')),
  actor TEXT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
  fecha TEXT NOT NULL
) STRICT;

CREATE TABLE respaldo (                                         -- pantalla de salud y prueba mensual
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  fecha TEXT NOT NULL,
  destino TEXT NOT NULL CHECK (destino IN ('replica','disco_externo')),
  base_sha256 TEXT NOT NULL CHECK (length(base_sha256) = 64),
  archivos INTEGER NOT NULL CHECK (archivos >= 0),
  verificado INTEGER NOT NULL DEFAULT 0 CHECK (verificado IN (0,1)),   -- integrity_check sobre la copia
  restauracion_probada TEXT
) STRICT;

CREATE TABLE sugerencia_ia (                                    -- C10: la IA solo escribe aquí, vía API
  id TEXT PRIMARY KEY CHECK (length(id) = 36),
  objeto_tipo TEXT NOT NULL CHECK (objeto_tipo IN ('documento','formato','aviso','alumno','grupo')),
  objeto_id TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('validacion','campos_formato','borrador','analisis')),
  contenido TEXT NOT NULL CHECK (json_valid(contenido)),
  estado TEXT NOT NULL DEFAULT 'propuesta' CHECK (estado IN ('propuesta','aceptada','rechazada','corregida')),
  decidio TEXT REFERENCES usuario(id) ON DELETE RESTRICT,
  correccion TEXT,                                              -- lo que la persona cambió: así aprende
  fecha TEXT NOT NULL,
  CHECK (estado = 'propuesta' OR decidio IS NOT NULL)
) STRICT;

CREATE TABLE bitacora (                                         -- C5: solo se agrega
  secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha TEXT NOT NULL,
  actor TEXT NOT NULL,
  accion TEXT NOT NULL,
  objeto_tipo TEXT NOT NULL,
  objeto_id TEXT NOT NULL,
  antes TEXT CHECK (antes IS NULL OR json_valid(antes)),
  despues TEXT CHECK (despues IS NULL OR json_valid(despues))
);
CREATE INDEX bitacora_objeto ON bitacora(objeto_tipo, objeto_id, secuencia);

-- ============================================================ Defensas en el motor

-- C1: nada se borra en las tablas escolares.
CREATE TRIGGER no_borrar_alumno BEFORE DELETE ON alumno BEGIN SELECT RAISE(ABORT, 'No se borran alumnos: use estado baja, egresado o archivado'); END;
CREATE TRIGGER no_borrar_tutor BEFORE DELETE ON tutor BEGIN SELECT RAISE(ABORT, 'No se borran tutores: use estado inactivo'); END;
CREATE TRIGGER no_borrar_personal BEFORE DELETE ON personal BEGIN SELECT RAISE(ABORT, 'No se borra personal: use estado baja'); END;
CREATE TRIGGER no_borrar_inscripcion BEFORE DELETE ON inscripcion BEGIN SELECT RAISE(ABORT, 'No se borran inscripciones: use baja o cancelada'); END;
CREATE TRIGGER no_borrar_calificacion BEFORE DELETE ON calificacion BEGIN SELECT RAISE(ABORT, 'No se borran calificaciones'); END;
CREATE TRIGGER no_borrar_correccion BEFORE DELETE ON calificacion_correccion BEGIN SELECT RAISE(ABORT, 'No se borran correcciones'); END;
CREATE TRIGGER no_borrar_documento BEFORE DELETE ON documento BEGIN SELECT RAISE(ABORT, 'No se borran documentos: se reemplazan'); END;
CREATE TRIGGER no_borrar_revision BEFORE DELETE ON revision_documento BEGIN SELECT RAISE(ABORT, 'No se borran revisiones'); END;
CREATE TRIGGER no_borrar_emitido BEFORE DELETE ON documento_emitido BEGIN SELECT RAISE(ABORT, 'No se borran documentos emitidos: se cancelan'); END;
CREATE TRIGGER no_borrar_bien BEFORE DELETE ON bien BEGIN SELECT RAISE(ABORT, 'No se borran bienes: use estado baja'); END;
CREATE TRIGGER no_borrar_archivo BEFORE DELETE ON archivo BEGIN SELECT RAISE(ABORT, 'No se borran archivos'); END;
CREATE TRIGGER no_borrar_ciclo BEFORE DELETE ON ciclo BEGIN SELECT RAISE(ABORT, 'No se borran ciclos'); END;

-- C4: la versión sube exactamente de uno en uno (quien guarda con una versión vieja falla).
CREATE TRIGGER version_alumno BEFORE UPDATE ON alumno WHEN NEW.version <> OLD.version + 1 BEGIN SELECT RAISE(ABORT, 'Conflicto: el alumno cambió, vuelva a cargarlo'); END;
CREATE TRIGGER version_tutor BEFORE UPDATE ON tutor WHEN NEW.version <> OLD.version + 1 BEGIN SELECT RAISE(ABORT, 'Conflicto: el tutor cambió, vuelva a cargarlo'); END;
CREATE TRIGGER version_personal BEFORE UPDATE ON personal WHEN NEW.version <> OLD.version + 1 BEGIN SELECT RAISE(ABORT, 'Conflicto: el registro cambió, vuelva a cargarlo'); END;
CREATE TRIGGER version_inscripcion BEFORE UPDATE ON inscripcion WHEN NEW.version <> OLD.version + 1 BEGIN SELECT RAISE(ABORT, 'Conflicto: la inscripción cambió, vuelva a cargarla'); END;
CREATE TRIGGER version_calificacion BEFORE UPDATE ON calificacion WHEN NEW.version <> OLD.version + 1 BEGIN SELECT RAISE(ABORT, 'Conflicto: la calificación cambió, vuelva a cargarla'); END;
CREATE TRIGGER version_documento BEFORE UPDATE ON documento WHEN NEW.version <> OLD.version + 1 BEGIN SELECT RAISE(ABORT, 'Conflicto: el documento cambió, vuelva a cargarlo'); END;
CREATE TRIGGER version_bien BEFORE UPDATE ON bien WHEN NEW.version <> OLD.version + 1 BEGIN SELECT RAISE(ABORT, 'Conflicto: el bien cambió, vuelva a cargarlo'); END;

-- C3: los identificadores no cambian.
CREATE TRIGGER id_fijo_alumno BEFORE UPDATE OF id ON alumno BEGIN SELECT RAISE(ABORT, 'El identificador no cambia'); END;
CREATE TRIGGER id_fijo_inscripcion BEFORE UPDATE OF id, alumno_id, ciclo_id ON inscripcion BEGIN SELECT RAISE(ABORT, 'La inscripción no cambia de alumno ni de ciclo'); END;

-- C5: bitácora solo de escritura.
CREATE TRIGGER bitacora_sin_cambios BEFORE UPDATE ON bitacora BEGIN SELECT RAISE(ABORT, 'La bitácora no se modifica'); END;
CREATE TRIGGER bitacora_sin_borrar BEFORE DELETE ON bitacora BEGIN SELECT RAISE(ABORT, 'La bitácora no se borra'); END;

-- C6: un archivo guardado no cambia; solo se registra cuántas copias tiene.
CREATE TRIGGER archivo_inmutable BEFORE UPDATE OF sha256, tamano, tipo_mime, ruta_relativa, creado ON archivo
BEGIN SELECT RAISE(ABORT, 'Un archivo guardado no cambia: suba una versión nueva'); END;
CREATE TRIGGER documento_contenido_fijo BEFORE UPDATE OF archivo_sha256, tipo, alumno_id, tutor_id, personal_id ON documento
BEGIN SELECT RAISE(ABORT, 'El contenido de un documento no cambia: suba una versión nueva'); END;

-- C7: periodos y ciclos cerrados.
CREATE TRIGGER periodo_cerrado_insertar BEFORE INSERT ON calificacion
WHEN (SELECT estado FROM periodo WHERE id = NEW.periodo_id) = 'cerrado'
BEGIN SELECT RAISE(ABORT, 'Periodo cerrado: registre una corrección con motivo'); END;
CREATE TRIGGER periodo_cerrado_cambiar BEFORE UPDATE ON calificacion
WHEN (SELECT estado FROM periodo WHERE id = OLD.periodo_id) = 'cerrado'
BEGIN SELECT RAISE(ABORT, 'Periodo cerrado: registre una corrección con motivo'); END;
CREATE TRIGGER periodo_no_reabre BEFORE UPDATE OF estado ON periodo
WHEN OLD.estado = 'cerrado' AND NEW.estado <> 'cerrado'
BEGIN SELECT RAISE(ABORT, 'Un periodo cerrado no se reabre'); END;
CREATE TRIGGER ciclo_no_reabre BEFORE UPDATE OF estado ON ciclo
WHEN OLD.estado = 'cerrado' AND NEW.estado <> 'cerrado'
BEGIN SELECT RAISE(ABORT, 'Un ciclo cerrado no se reabre'); END;
CREATE TRIGGER ciclo_cerrado_inscripcion BEFORE UPDATE ON inscripcion
WHEN (SELECT estado FROM ciclo WHERE id = OLD.ciclo_id) = 'cerrado'
BEGIN SELECT RAISE(ABORT, 'Ciclo cerrado: solo lectura'); END;
CREATE TRIGGER ciclo_cerrado_asistencia BEFORE INSERT ON asistencia_alumno
WHEN (SELECT c.estado FROM inscripcion i JOIN ciclo c ON c.id = i.ciclo_id WHERE i.id = NEW.inscripcion_id) = 'cerrado'
BEGIN SELECT RAISE(ABORT, 'Ciclo cerrado: solo lectura'); END;

-- Documentos emitidos: solo pueden cancelarse.
CREATE TRIGGER emitido_inmutable BEFORE UPDATE ON documento_emitido
WHEN NOT (OLD.estado = 'valido' AND NEW.estado = 'cancelado' AND NEW.folio = OLD.folio
          AND NEW.archivo_sha256 = OLD.archivo_sha256 AND NEW.datos = OLD.datos)
BEGIN SELECT RAISE(ABORT, 'Un documento emitido solo puede cancelarse'); END;

-- ============================================================ Catálogos iniciales

INSERT INTO campo_formativo(clave, nombre) VALUES
  ('lenguajes', 'Lenguajes'),
  ('saberes', 'Saberes y pensamiento científico'),
  ('etica', 'Ética, naturaleza y sociedades'),
  ('humano', 'De lo humano y lo comunitario');

INSERT INTO tipo_documento(clave, nombre, aplica_a, obligatorio_nuevo, obligatorio_reinscripcion, caducidad) VALUES
  ('acta', 'Acta de nacimiento', 'alumno', 1, 0, 'nunca'),
  ('curp', 'CURP', 'alumno', 1, 0, 'nunca'),
  ('certificado_medico', 'Certificado médico', 'alumno', 1, 1, 'por_ciclo'),
  ('cartilla_vacunacion', 'Cartilla de vacunación', 'alumno', 1, 0, 'nunca'),
  ('fotografia', 'Fotografía', 'alumno', 1, 0, 'por_ciclo'),
  ('boleta_anterior', 'Boleta del ciclo anterior', 'alumno', 1, 0, 'nunca'),
  ('certificado', 'Certificado de primaria', 'alumno', 0, 0, 'nunca'),
  ('ine_tutor', 'Identificación del tutor', 'tutor', 1, 0, 'fecha'),
  ('comprobante_domicilio', 'Comprobante de domicilio', 'tutor', 1, 1, 'por_ciclo');

COMMIT;
