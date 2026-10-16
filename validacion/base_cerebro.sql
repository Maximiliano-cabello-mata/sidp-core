-- Base de datos de la PC 4 (PostgreSQL), versión 2: el expediente escolar completo para procesar.
--
-- Qué guarda: ciclos, grupos, alumnos, tutores, inscripciones, documentos del expediente (sin el
-- archivo: solo su huella sha256), revisiones de una persona, lecturas del cerebro, propuestas de la
-- IA, importaciones y una bitácora de todo cambio. Explicación en docs/arquitectura/base_cerebro.md.
--
-- Defensas en el motor (las mismas del diseño integral, database/diseno_integral.sql):
--   C1 Nada se borra: DELETE y TRUNCATE fallan; se usan estados (baja, archivado, reemplazado).
--   C2 Claves foráneas sin borrado en cascada.
--   C4 Cada cambio sube la versión de 1 en 1, y un cambio que no cambia nada no se guarda.
--   C5 Bitácora solo de escritura, con el antes y el después de cada cambio y quién lo hizo.
--   C8 CHECK en estados, rangos y formatos (CURP, grado, letra).
--   C9 El mismo archivo no se importa dos veces (por su sha256).
--   C10 La IA solo escribe en sugerencia_ia; una persona decide.
--
-- Se puede correr las veces que sea: crea lo que falta y no borra datos. Si encuentra la versión 1
-- (public.padron_alumno), pasa sus alumnos a esta y la renombra a padron_alumno_v1.

CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- parecido entre textos (trigramas)
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;  -- levenshtein: cuántas letras cambian
CREATE SCHEMA IF NOT EXISTS sidp;

-- ============================================================ Funciones básicas (sin tablas)

-- Mayúsculas, sin acentos ni letras griegas o cirílicas que parecen latinas; solo letras y números.
CREATE OR REPLACE FUNCTION sidp.normalizar(texto text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT btrim(regexp_replace(
        translate(upper(coalesce(texto, '')),
                  'ÁÉÍÓÚÜÀÈÌÒÙÂÊÎÔÛÄËÏÖáéíóúüàèìòùâêîôûäëïöñΑΒΕΖΗΙΚΜΝΟΡΤΥΧАВЕКМНОРСТУХ',
                  'AEIOUUAEIOUAEIOUAEIOAEIOUUAEIOUAEIOUAEIOÑABEZHIKMNOPTYXABEKMHOPCTYX'),
        '[^A-Z0-9Ñ]+', ' ', 'g'))
$$;

-- Dígito verificador de la CURP (el último carácter), calculado con los primeros 17.
CREATE OR REPLACE FUNCTION sidp.curp_digito(curp text) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    diccionario CONSTANT text := '0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ';
    suma integer := 0;
    posicion integer;
BEGIN
    IF curp IS NULL OR length(curp) < 17 THEN
        RETURN NULL;
    END IF;
    FOR i IN 1..17 LOOP
        posicion := strpos(diccionario, substr(upper(curp), i, 1));
        IF posicion = 0 THEN
            RETURN NULL;
        END IF;
        suma := suma + (posicion - 1) * (19 - i);
    END LOOP;
    RETURN ((10 - suma % 10) % 10)::text;
END $$;

-- Fecha de nacimiento que trae la CURP (NULL si la CURP no tiene la forma correcta).
CREATE OR REPLACE FUNCTION sidp.curp_fecha(curp text) RETURNS date
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    IF curp IS NULL OR upper(curp) !~ '^[A-Z]{4}[0-9]{6}[HMX][A-Z]{5}[0-9A-Z][0-9]$' THEN
        RETURN NULL;
    END IF;
    RETURN make_date(CASE WHEN substr(curp, 17, 1) ~ '[0-9]' THEN 1900 ELSE 2000 END + substr(curp, 5, 2)::integer,
                     substr(curp, 7, 2)::integer, substr(curp, 9, 2)::integer);
EXCEPTION WHEN others THEN
    RETURN NULL;  -- Fecha imposible (31 de febrero, mes 13).
END $$;

-- La CURP tiene la forma correcta, una fecha posible y su dígito verificador cuadra.
CREATE OR REPLACE FUNCTION sidp.curp_valida(curp text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT sidp.curp_fecha(curp) IS NOT NULL AND sidp.curp_digito(curp) = substr(upper(curp), 18, 1)
$$;

-- Años cumplidos en una fecha.
CREATE OR REPLACE FUNCTION sidp.edad_al(nacimiento date, fecha date) RETURNS integer
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN nacimiento IS NULL OR fecha IS NULL THEN NULL ELSE extract(year FROM age(fecha, nacimiento))::integer END
$$;

-- Grado que le corresponde por edad: en primaria se entra a 1° con 6 años cumplidos al 31 de
-- diciembre del año en que empieza el ciclo. Un ciclo se escribe '2026-2027'.
CREATE OR REPLACE FUNCTION sidp.grado_esperado(nacimiento date, ciclo text) RETURNS integer
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT sidp.edad_al(nacimiento, make_date(left(ciclo, 4)::integer, 12, 31)) - 5
$$;

-- El ciclo escolar de una fecha (de agosto a julio).
CREATE OR REPLACE FUNCTION sidp.ciclo_de(fecha date) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN extract(month FROM fecha) >= 8
                THEN extract(year FROM fecha)::integer || '-' || (extract(year FROM fecha)::integer + 1)
                ELSE (extract(year FROM fecha)::integer - 1) || '-' || extract(year FROM fecha)::integer END
$$;

-- ============================================================ Tablas

CREATE TABLE IF NOT EXISTS sidp.meta (
    clave  text PRIMARY KEY,
    valor  text NOT NULL
);

CREATE TABLE IF NOT EXISTS sidp.ciclo (
    nombre  text PRIMARY KEY CHECK (nombre ~ '^[0-9]{4}-[0-9]{4}$'),
    inicio  date NOT NULL,
    fin     date NOT NULL CHECK (fin > inicio),
    estado  text NOT NULL DEFAULT 'abierto' CHECK (estado IN ('preparacion', 'abierto', 'cerrado'))
);

CREATE TABLE IF NOT EXISTS sidp.grupo (
    id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ciclo  text NOT NULL REFERENCES sidp.ciclo(nombre) ON DELETE RESTRICT,
    grado  smallint NOT NULL CHECK (grado BETWEEN 1 AND 6),
    letra  text NOT NULL CHECK (letra ~ '^[A-Z]$'),
    UNIQUE (ciclo, grado, letra)
);

CREATE TABLE IF NOT EXISTS sidp.alumno (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    curp                text UNIQUE CHECK (curp IS NULL OR curp ~ '^[A-Z]{4}[0-9]{6}[HMX][A-Z]{5}[0-9A-Z][0-9]$'),
    nombres             text NOT NULL CHECK (btrim(nombres) <> ''),
    primer_apellido     text NOT NULL CHECK (btrim(primer_apellido) <> ''),
    segundo_apellido    text NOT NULL DEFAULT '',
    fecha_nacimiento    date,
    sexo                text CHECK (sexo IN ('H', 'M', 'X')),
    entidad_nacimiento  text CHECK (entidad_nacimiento ~ '^[A-Z]{2}$'),
    curp_digito_ok      boolean GENERATED ALWAYS AS (sidp.curp_digito(curp) = substr(curp, 18, 1)) STORED,
    curp_renapo         text NOT NULL DEFAULT 'sin_validar'
                        CHECK (curp_renapo IN ('sin_validar', 'validada', 'no_encontrada', 'no_coincide')),
    nombre_busqueda     text GENERATED ALWAYS AS (sidp.normalizar(nombres || ' ' || primer_apellido || ' ' || segundo_apellido)) STORED,
    estado              text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'baja', 'egresado', 'archivado')),
    creado              timestamptz NOT NULL DEFAULT now(),
    actualizado         timestamptz NOT NULL DEFAULT now(),
    version             integer NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS alumno_nombre ON sidp.alumno USING gin (nombre_busqueda gin_trgm_ops);

CREATE TABLE IF NOT EXISTS sidp.tutor (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    curp              text UNIQUE CHECK (curp IS NULL OR curp ~ '^[A-Z]{4}[0-9]{6}[HMX][A-Z]{5}[0-9A-Z][0-9]$'),
    nombres           text NOT NULL CHECK (btrim(nombres) <> ''),
    primer_apellido   text NOT NULL CHECK (btrim(primer_apellido) <> ''),
    segundo_apellido  text NOT NULL DEFAULT '',
    telefono          text,
    correo            text,
    domicilio         text,
    nombre_busqueda   text GENERATED ALWAYS AS (sidp.normalizar(nombres || ' ' || primer_apellido || ' ' || segundo_apellido)) STORED,
    estado            text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
    actualizado       timestamptz NOT NULL DEFAULT now(),
    version           integer NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sidp.alumno_tutor (
    alumno_id   bigint NOT NULL REFERENCES sidp.alumno(id) ON DELETE RESTRICT,
    tutor_id    bigint NOT NULL REFERENCES sidp.tutor(id) ON DELETE RESTRICT,
    parentesco  text NOT NULL CHECK (parentesco IN ('madre', 'padre', 'tutor_legal', 'abuelo', 'otro')),
    principal   boolean NOT NULL DEFAULT false,
    vigente     boolean NOT NULL DEFAULT true,
    PRIMARY KEY (alumno_id, tutor_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS un_tutor_principal ON sidp.alumno_tutor (alumno_id) WHERE principal AND vigente;

CREATE TABLE IF NOT EXISTS sidp.inscripcion (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alumno_id    bigint NOT NULL REFERENCES sidp.alumno(id) ON DELETE RESTRICT,
    ciclo        text NOT NULL REFERENCES sidp.ciclo(nombre) ON DELETE RESTRICT,
    grupo_id     bigint NOT NULL REFERENCES sidp.grupo(id) ON DELETE RESTRICT,
    tipo         text NOT NULL CHECK (tipo IN ('nuevo_ingreso', 'reinscripcion', 'traslado')),
    origen       text NOT NULL CHECK (origen IN ('lista_oficial', 'validador', 'captura', 'pagina_padres')),
    estado       text NOT NULL DEFAULT 'incompleta' CHECK (estado IN ('incompleta', 'completa', 'baja', 'cancelada')),
    alta         date NOT NULL DEFAULT current_date,
    baja         date,
    motivo_baja  text,
    actualizado  timestamptz NOT NULL DEFAULT now(),
    version      integer NOT NULL DEFAULT 1,
    CHECK (estado <> 'baja' OR (baja IS NOT NULL AND motivo_baja IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS una_inscripcion_por_ciclo ON sidp.inscripcion (alumno_id, ciclo) WHERE estado <> 'cancelada';

CREATE TABLE IF NOT EXISTS sidp.tipo_documento (
    clave           text PRIMARY KEY,
    nombre          text NOT NULL UNIQUE,
    de_quien        text NOT NULL CHECK (de_quien IN ('alumno', 'tutor', 'escuela')),
    obligatorio     boolean NOT NULL DEFAULT true,
    desde_grado     smallint NOT NULL DEFAULT 1 CHECK (desde_grado BETWEEN 1 AND 6),  -- La boleta se pide desde 2°.
    vigencia_meses  smallint,  -- NULL = no vence. El comprobante de domicilio vale 3 meses.
    orden           smallint NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sidp.documento (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alumno_id        bigint NOT NULL REFERENCES sidp.alumno(id) ON DELETE RESTRICT,  -- El expediente donde va.
    tutor_id         bigint REFERENCES sidp.tutor(id) ON DELETE RESTRICT,           -- Si es del tutor.
    tipo             text NOT NULL REFERENCES sidp.tipo_documento(clave) ON DELETE RESTRICT,
    sha256           text CHECK (sha256 ~ '^[0-9a-f]{64}$'),  -- La huella del archivo; el archivo vive en la PC del administrador.
    paginas          smallint CHECK (paginas > 0),
    origen           text NOT NULL CHECK (origen IN ('escaneo', 'foto', 'pagina_padres', 'papel', 'mige', 'generado')),
    estado           text NOT NULL DEFAULT 'recibido' CHECK (estado IN ('recibido', 'validado', 'rechazado', 'vencido', 'reemplazado')),
    motivo_rechazo   text,
    fecha_documento  date,  -- La que trae el documento (para la vigencia del comprobante).
    reemplaza_a      bigint REFERENCES sidp.documento(id) ON DELETE RESTRICT,
    recibido         timestamptz NOT NULL DEFAULT now(),
    actualizado      timestamptz NOT NULL DEFAULT now(),
    version          integer NOT NULL DEFAULT 1,
    CHECK (estado <> 'rechazado' OR motivo_rechazo IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS documento_alumno ON sidp.documento (alumno_id, tipo);

CREATE TABLE IF NOT EXISTS sidp.revision_documento (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    documento_id  bigint NOT NULL REFERENCES sidp.documento(id) ON DELETE RESTRICT,
    resultado     text NOT NULL CHECK (resultado IN ('validado', 'rechazado')),
    motivo        text,
    reviso        text NOT NULL CHECK (btrim(reviso) <> '' AND lower(reviso) NOT IN ('ia', 'cerebro', 'modelo')),  -- Siempre una persona.
    fecha         timestamptz NOT NULL DEFAULT now(),
    CHECK (resultado <> 'rechazado' OR motivo IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS sidp.importacion (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256           text NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    tipo             text NOT NULL CHECK (tipo IN ('lista_oficial', 'lista_grupo', 'padron_validador')),
    filas_leidas     integer NOT NULL,
    resumen          jsonb NOT NULL,
    actor            text NOT NULL,
    fecha            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sidp.lectura (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recibida        timestamptz NOT NULL DEFAULT now(),
    metodo          text,      -- pdf, ocr, qr...
    caracteres      integer,   -- Cuánto texto salió (0 = no se pudo leer).
    tipo_detectado  text,
    curp_leida      text,      -- Tal como se leyó.
    alumno_id       bigint REFERENCES sidp.alumno(id) ON DELETE RESTRICT,  -- El del padrón que más se le parece.
    distancia       smallint,  -- Letras distintas entre la CURP leída y la del alumno (0 = idéntica).
    parecido        real       -- Si se reconoció por el nombre: qué tanto se parece (1 = idéntico).
);

CREATE TABLE IF NOT EXISTS sidp.sugerencia_ia (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    objeto_tipo  text NOT NULL CHECK (objeto_tipo IN ('documento', 'alumno', 'tutor', 'lectura')),
    objeto_id    bigint NOT NULL,
    tipo         text NOT NULL CHECK (tipo IN ('validacion', 'correccion', 'analisis')),
    contenido    jsonb NOT NULL,
    estado       text NOT NULL DEFAULT 'propuesta' CHECK (estado IN ('propuesta', 'aceptada', 'rechazada', 'corregida')),
    decidio      text,
    correccion   jsonb,  -- Lo que la persona cambió: con esto se mide y se mejora.
    fecha        timestamptz NOT NULL DEFAULT now(),
    CHECK (estado = 'propuesta' OR decidio IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS sidp.bitacora (
    secuencia  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha      timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor      text NOT NULL,
    accion     text NOT NULL,
    tabla      text NOT NULL,
    registro   text NOT NULL,
    antes      jsonb,
    despues    jsonb
);
CREATE INDEX IF NOT EXISTS bitacora_registro ON sidp.bitacora (tabla, registro, secuencia);

INSERT INTO sidp.tipo_documento (clave, nombre, de_quien, obligatorio, desde_grado, vigencia_meses, orden) VALUES
    ('acta_nacimiento',       'Acta de nacimiento del alumno',      'alumno',  true,  1, NULL, 1),
    ('constancia_curp',       'Constancia de la CURP del alumno',   'alumno',  false, 1, NULL, 2),
    ('certificado_medico',    'Certificado médico',                 'alumno',  true,  1, NULL, 3),
    ('boleta_anterior',       'Boleta del grado anterior',          'alumno',  true,  2, NULL, 4),
    ('ine_tutor',             'INE del padre, madre o tutor',       'tutor',   true,  1, NULL, 5),
    ('acta_tutor',            'Acta de nacimiento del tutor',       'tutor',   true,  1, NULL, 6),
    ('curp_tutor',            'CURP del tutor',                     'tutor',   true,  1, NULL, 7),
    ('comprobante_domicilio', 'Comprobante de domicilio',           'tutor',   true,  1, 3,    8),
    ('ficha_inscripcion',     'Ficha de inscripción',               'escuela', true,  1, NULL, 9),
    ('ficha_autorizacion',    'Ficha de autorización',              'escuela', true,  1, NULL, 10)
ON CONFLICT (clave) DO NOTHING;  -- Si la escuela cambió algo, se respeta.

-- ============================================================ Defensas (C1, C4, C5)

CREATE OR REPLACE FUNCTION sidp.no_borrar() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- La única excepción: sidp.borrar_alumno, cuando un administrador borra a un alumno (queda en la bitácora).
    IF current_setting('sidp.borrando', true) = 'si' THEN
        RETURN CASE WHEN TG_LEVEL = 'ROW' THEN OLD END;
    END IF;
    RAISE EXCEPTION 'En SIDP no se borra nada (tabla %): usa un estado como baja, archivado o reemplazado', TG_TABLE_NAME;
END $$;

CREATE OR REPLACE FUNCTION sidp.bitacora_fija() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora no se cambia ni se borra';
END $$;

-- Si nada cambió, no se guarda; si cambió algo, la versión sube de 1 en 1.
CREATE OR REPLACE FUNCTION sidp.subir_version() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Las columnas calculadas todavía no tienen valor en NEW: se comparan las demás.
    IF to_jsonb(NEW) - 'actualizado' - 'version' - 'nombre_busqueda' - 'curp_digito_ok'
       = to_jsonb(OLD) - 'actualizado' - 'version' - 'nombre_busqueda' - 'curp_digito_ok' THEN
        RETURN NULL;
    END IF;
    NEW.version := OLD.version + 1;
    NEW.actualizado := now();
    RETURN NEW;
END $$;

-- La fecha, el sexo y la entidad salen de la CURP cuando no se escribieron.
CREATE OR REPLACE FUNCTION sidp.completar_por_curp() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.curp IS NOT NULL THEN
        NEW.curp := upper(NEW.curp);
        NEW.fecha_nacimiento := coalesce(NEW.fecha_nacimiento, sidp.curp_fecha(NEW.curp));
        NEW.sexo := coalesce(NEW.sexo, substr(NEW.curp, 11, 1));
        NEW.entidad_nacimiento := coalesce(NEW.entidad_nacimiento, substr(NEW.curp, 12, 2));
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION sidp.anotar_cambio() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    nuevo jsonb := to_jsonb(NEW);
BEGIN
    INSERT INTO sidp.bitacora (actor, accion, tabla, registro, antes, despues)
    VALUES (coalesce(nullif(current_setting('sidp.actor', true), ''), 'sistema'), lower(TG_OP), TG_TABLE_NAME,
            coalesce(nuevo->>'id', (nuevo->>'alumno_id') || ':' || (nuevo->>'tutor_id')),
            CASE WHEN TG_OP = 'UPDATE' THEN to_jsonb(OLD) END, nuevo);
    RETURN NEW;
END $$;

DO $$
DECLARE
    tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['ciclo', 'grupo', 'alumno', 'tutor', 'alumno_tutor', 'inscripcion', 'tipo_documento',
                                 'documento', 'revision_documento', 'importacion', 'lectura', 'sugerencia_ia'] LOOP
        EXECUTE format('CREATE OR REPLACE TRIGGER no_borrar BEFORE DELETE ON sidp.%I FOR EACH ROW EXECUTE FUNCTION sidp.no_borrar()', tabla);
        EXECUTE format('CREATE OR REPLACE TRIGGER no_vaciar BEFORE TRUNCATE ON sidp.%I FOR EACH STATEMENT EXECUTE FUNCTION sidp.no_borrar()', tabla);
    END LOOP;
    FOREACH tabla IN ARRAY ARRAY['alumno', 'tutor', 'inscripcion', 'documento'] LOOP
        EXECUTE format('CREATE OR REPLACE TRIGGER subir_version BEFORE UPDATE ON sidp.%I FOR EACH ROW EXECUTE FUNCTION sidp.subir_version()', tabla);
    END LOOP;
    FOREACH tabla IN ARRAY ARRAY['alumno', 'tutor', 'alumno_tutor', 'inscripcion', 'documento', 'sugerencia_ia'] LOOP
        EXECUTE format('CREATE OR REPLACE TRIGGER anotar_cambio AFTER INSERT OR UPDATE ON sidp.%I FOR EACH ROW EXECUTE FUNCTION sidp.anotar_cambio()', tabla);
    END LOOP;
END $$;
CREATE OR REPLACE TRIGGER completar_por_curp BEFORE INSERT OR UPDATE ON sidp.alumno FOR EACH ROW EXECUTE FUNCTION sidp.completar_por_curp();
CREATE OR REPLACE TRIGGER fija BEFORE UPDATE OR DELETE ON sidp.bitacora FOR EACH ROW EXECUTE FUNCTION sidp.bitacora_fija();
CREATE OR REPLACE TRIGGER fija_vaciar BEFORE TRUNCATE ON sidp.bitacora FOR EACH STATEMENT EXECUTE FUNCTION sidp.bitacora_fija();

-- ============================================================ Vistas

-- La inscripción vigente de cada alumno (la del ciclo más reciente que no está cancelada).
CREATE OR REPLACE VIEW sidp.v_inscripcion_actual AS
SELECT DISTINCT ON (alumno_id) id, alumno_id, ciclo, grupo_id, tipo, origen, estado
FROM sidp.inscripcion
WHERE estado <> 'cancelada'
ORDER BY alumno_id, ciclo DESC, id DESC;

CREATE OR REPLACE VIEW sidp.v_alumnos AS
SELECT a.id, a.curp, a.primer_apellido, a.segundo_apellido, a.nombres, a.nombre_busqueda, a.sexo, a.fecha_nacimiento,
       a.curp_digito_ok, a.curp_renapo, a.estado, i.ciclo, g.grado, g.letra, i.estado AS inscripcion,
       sidp.edad_al(a.fecha_nacimiento, make_date(left(i.ciclo, 4)::integer, 12, 31)) AS edad_31_dic,
       sidp.grado_esperado(a.fecha_nacimiento, i.ciclo) AS grado_esperado
FROM sidp.alumno a
LEFT JOIN sidp.v_inscripcion_actual i ON i.alumno_id = a.id
LEFT JOIN sidp.grupo g ON g.id = i.grupo_id;

-- Los alumnos inscritos ahora (activos, con inscripción incompleta o completa).
CREATE OR REPLACE VIEW sidp.v_inscritos AS
SELECT * FROM sidp.v_alumnos WHERE estado = 'activo' AND inscripcion IN ('incompleta', 'completa');

-- Qué documentos obligatorios le faltan a cada alumno (validados por una persona).
CREATE OR REPLACE VIEW sidp.v_faltantes AS
SELECT a.id AS alumno_id, a.ciclo, a.grado, a.letra,
       array_agg(t.clave ORDER BY t.orden) AS faltan, count(*)::integer AS cuantos
FROM sidp.v_inscritos a
JOIN sidp.tipo_documento t ON t.obligatorio AND t.desde_grado <= coalesce(a.grado, 1)
WHERE NOT EXISTS (SELECT 1 FROM sidp.documento d WHERE d.alumno_id = a.id AND d.tipo = t.clave AND d.estado = 'validado')
GROUP BY a.id, a.ciclo, a.grado, a.letra;

-- Matrícula para la estadística 911: por grado, sexo y edad al 31 de diciembre.
CREATE OR REPLACE VIEW sidp.v_matricula_911 AS
SELECT ciclo, grado, sexo, edad_31_dic AS edad, count(*)::integer AS alumnos
FROM sidp.v_inscritos
GROUP BY ciclo, grado, sexo, edad_31_dic;

CREATE OR REPLACE VIEW sidp.v_resumen_grupo AS
SELECT a.ciclo, a.grado, a.letra, count(*)::integer AS alumnos,
       count(*) FILTER (WHERE a.sexo = 'H')::integer AS hombres,
       count(*) FILTER (WHERE a.sexo = 'M')::integer AS mujeres,
       count(*) FILTER (WHERE a.curp IS NULL)::integer AS sin_curp,
       count(*) FILTER (WHERE a.curp_renapo = 'validada')::integer AS curp_validadas,
       count(*) FILTER (WHERE a.grado_esperado - a.grado >= 2)::integer AS extraedad,
       count(*) FILTER (WHERE f.alumno_id IS NULL)::integer AS expediente_completo
FROM sidp.v_inscritos a
LEFT JOIN sidp.v_faltantes f ON f.alumno_id = a.id
GROUP BY a.ciclo, a.grado, a.letra;

-- Lo que una persona debería revisar. Nada de esto cambia datos: solo avisa.
CREATE OR REPLACE VIEW sidp.v_alertas AS
SELECT 'curp_digito' AS tipo, 'alta' AS gravedad, id AS alumno_id, 'La CURP no cuadra su dígito verificador' AS detalle
FROM sidp.v_inscritos WHERE curp IS NOT NULL AND NOT curp_digito_ok
UNION ALL
SELECT 'curp_fecha', 'alta', id, 'La fecha de nacimiento no es la de la CURP'
FROM sidp.v_inscritos WHERE curp IS NOT NULL AND fecha_nacimiento IS DISTINCT FROM sidp.curp_fecha(curp)
UNION ALL
SELECT 'renapo', 'alta', id, CASE curp_renapo WHEN 'no_encontrada' THEN 'RENAPO no encontró la CURP'
                                             ELSE 'Los datos de RENAPO no coinciden' END
FROM sidp.v_inscritos WHERE curp_renapo IN ('no_encontrada', 'no_coincide')
UNION ALL
SELECT 'sin_curp', 'media', id, 'No tiene CURP'
FROM sidp.v_inscritos WHERE curp IS NULL
UNION ALL
SELECT 'extraedad', 'media', id, format('Tiene %s años al 31 de diciembre; para %s° se esperan %s', edad_31_dic, grado, grado + 5)
FROM sidp.v_inscritos WHERE grado_esperado - grado >= 2
UNION ALL
SELECT 'menor_edad', 'media', id, format('Tiene %s años al 31 de diciembre; para %s° se esperan %s', edad_31_dic, grado, grado + 5)
FROM sidp.v_inscritos WHERE grado_esperado < grado
UNION ALL
SELECT 'posible_duplicado', 'media', a.id, format('Se parece mucho a otro alumno (número %s)', b.id)
FROM sidp.v_inscritos a
JOIN sidp.v_inscritos b ON a.id < b.id AND a.nombre_busqueda % b.nombre_busqueda
WHERE similarity(a.nombre_busqueda, b.nombre_busqueda) >= 0.75
  AND (a.curp IS NULL OR b.curp IS NULL OR a.fecha_nacimiento = b.fecha_nacimiento)
UNION ALL
SELECT 'renapo_pendiente', 'baja', id, 'La CURP no se ha validado en RENAPO'
FROM sidp.v_inscritos WHERE curp IS NOT NULL AND curp_renapo = 'sin_validar';

-- ============================================================ Funciones de trabajo

CREATE OR REPLACE FUNCTION sidp.asegurar_ciclo(nombre_ciclo text) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO sidp.ciclo (nombre, inicio, fin)
    VALUES (nombre_ciclo, make_date(left(nombre_ciclo, 4)::integer, 8, 1), make_date(right(nombre_ciclo, 4)::integer, 7, 31))
    ON CONFLICT (nombre) DO NOTHING;
    RETURN nombre_ciclo;
END $$;

CREATE OR REPLACE FUNCTION sidp.asegurar_grupo(nombre_ciclo text, grado_grupo integer, letra_grupo text) RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE
    encontrado bigint;
BEGIN
    PERFORM sidp.asegurar_ciclo(nombre_ciclo);
    SELECT id INTO encontrado FROM sidp.grupo WHERE ciclo = nombre_ciclo AND grado = grado_grupo AND letra = upper(letra_grupo);
    IF encontrado IS NULL THEN
        INSERT INTO sidp.grupo (ciclo, grado, letra) VALUES (nombre_ciclo, grado_grupo, upper(letra_grupo)) RETURNING id INTO encontrado;
    END IF;
    RETURN encontrado;
END $$;

-- Carga alumnos de una lista: [{curp, primer_apellido, segundo_apellido, nombres, grado, letra, sexo?, fecha_nacimiento?}].
-- El mismo alumno se reconoce por su CURP, o por el nombre idéntico si no tenía CURP. Nadie se duplica,
-- nadie se da de baja solo: los que ya no vienen en la lista se cuentan en "no_vinieron" para que una
-- persona decida.
CREATE OR REPLACE FUNCTION sidp.cargar_alumnos(datos jsonb, nombre_ciclo text, origen_carga text, actor text DEFAULT 'sistema')
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    fila jsonb;
    v_curp text;
    v_nombres text;
    v_primer text;
    v_segundo text;
    v_alumno bigint;
    v_grupo bigint;
    v_inscripcion record;
    vistos bigint[] := '{}';
    nuevos integer := 0;
    actualizados integer := 0;
    inscritos integer := 0;
    cambios_grupo integer := 0;
    rechazados jsonb := '[]';
    numero integer := 0;
BEGIN
    PERFORM set_config('sidp.actor', actor, true);
    PERFORM sidp.asegurar_ciclo(nombre_ciclo);
    FOR fila IN SELECT value FROM jsonb_array_elements(datos) LOOP
        numero := numero + 1;
        v_curp := nullif(upper(btrim(coalesce(fila->>'curp', ''))), '');
        v_nombres := upper(btrim(coalesce(fila->>'nombres', '')));
        v_primer := upper(btrim(coalesce(fila->>'primer_apellido', '')));
        v_segundo := upper(btrim(coalesce(fila->>'segundo_apellido', '')));
        IF v_nombres = '' OR v_primer = '' THEN
            rechazados := rechazados || jsonb_build_object('renglon', numero, 'motivo', 'falta el nombre o el primer apellido');
            CONTINUE;
        END IF;
        IF v_curp IS NOT NULL AND v_curp !~ '^[A-Z]{4}[0-9]{6}[HMX][A-Z]{5}[0-9A-Z][0-9]$' THEN
            rechazados := rechazados || jsonb_build_object('renglon', numero, 'motivo', 'la CURP no tiene la forma correcta');
            CONTINUE;
        END IF;
        v_alumno := NULL;
        IF v_curp IS NOT NULL THEN
            SELECT id INTO v_alumno FROM sidp.alumno WHERE curp = v_curp;
        END IF;
        IF v_alumno IS NULL THEN
            SELECT id INTO v_alumno FROM sidp.alumno
            WHERE curp IS NULL AND nombre_busqueda = sidp.normalizar(v_nombres || ' ' || v_primer || ' ' || v_segundo)
            ORDER BY id LIMIT 1;
        END IF;
        IF v_alumno IS NULL THEN
            INSERT INTO sidp.alumno (curp, nombres, primer_apellido, segundo_apellido, sexo, fecha_nacimiento)
            VALUES (v_curp, v_nombres, v_primer, v_segundo, nullif(fila->>'sexo', ''), nullif(fila->>'fecha_nacimiento', '')::date)
            RETURNING id INTO v_alumno;
            nuevos := nuevos + 1;
        ELSE
            UPDATE sidp.alumno SET curp = coalesce(curp, v_curp), nombres = v_nombres, primer_apellido = v_primer,
                                   segundo_apellido = v_segundo
            WHERE id = v_alumno;
            IF FOUND THEN
                actualizados := actualizados + 1;
            END IF;
        END IF;
        vistos := vistos || v_alumno;
        IF fila->>'grado' IS NOT NULL AND fila->>'letra' IS NOT NULL THEN
            v_grupo := sidp.asegurar_grupo(nombre_ciclo, (fila->>'grado')::integer, fila->>'letra');
            SELECT id, grupo_id INTO v_inscripcion FROM sidp.inscripcion
            WHERE alumno_id = v_alumno AND ciclo = nombre_ciclo AND estado <> 'cancelada';
            IF NOT FOUND THEN
                INSERT INTO sidp.inscripcion (alumno_id, ciclo, grupo_id, tipo, origen)
                VALUES (v_alumno, nombre_ciclo, v_grupo,
                        CASE WHEN (fila->>'grado')::integer = 1 THEN 'nuevo_ingreso' ELSE 'reinscripcion' END, origen_carga);
                inscritos := inscritos + 1;
            ELSIF v_inscripcion.grupo_id <> v_grupo THEN
                UPDATE sidp.inscripcion SET grupo_id = v_grupo WHERE id = v_inscripcion.id;
                cambios_grupo := cambios_grupo + 1;
            END IF;
        END IF;
    END LOOP;
    RETURN jsonb_build_object(
        'leidos', numero, 'nuevos', nuevos, 'actualizados', actualizados, 'inscritos', inscritos,
        'cambios_de_grupo', cambios_grupo, 'rechazados', rechazados,
        'no_vinieron', (SELECT count(*) FROM sidp.inscripcion
                        WHERE ciclo = nombre_ciclo AND estado IN ('incompleta', 'completa') AND NOT (alumno_id = ANY (vistos))));
END $$;

-- Importa un archivo (por ejemplo, la lista oficial) una sola vez: el mismo archivo otra vez no hace nada.
CREATE OR REPLACE FUNCTION sidp.importar(huella text, tipo_importacion text, datos jsonb, nombre_ciclo text, origen_carga text,
                                          actor text DEFAULT 'sistema')
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    anterior jsonb;
    resultado jsonb;
BEGIN
    SELECT resumen INTO anterior FROM sidp.importacion WHERE sha256 = lower(huella);
    IF FOUND THEN
        RETURN anterior || jsonb_build_object('ya_importado', true);
    END IF;
    resultado := sidp.cargar_alumnos(datos, nombre_ciclo, origen_carga, actor);
    INSERT INTO sidp.importacion (sha256, tipo, filas_leidas, resumen, actor)
    VALUES (lower(huella), tipo_importacion, jsonb_array_length(datos), resultado, actor);
    RETURN resultado || jsonb_build_object('ya_importado', false);
END $$;

-- Los alumnos cuya CURP está a pocas letras de la que se leyó, la más cercana primero.
CREATE OR REPLACE FUNCTION sidp.curp_cercana(leida text, maximo integer DEFAULT 2)
RETURNS TABLE (alumno_id bigint, curp text, distancia integer, primer_apellido text, segundo_apellido text, nombres text,
               grado smallint, letra text)
LANGUAGE sql STABLE AS $$
    SELECT a.id, a.curp, levenshtein(a.curp, upper(leida)), a.primer_apellido, a.segundo_apellido, a.nombres, a.grado, a.letra
    FROM sidp.v_alumnos a
    WHERE a.estado = 'activo' AND a.curp IS NOT NULL AND levenshtein(a.curp, upper(leida)) <= maximo
    ORDER BY 3, 2
    LIMIT 3
$$;

-- Los alumnos cuyo nombre aparece en el texto, aunque esté mal escrito o en otro orden.
CREATE OR REPLACE FUNCTION sidp.nombre_cercano(texto text, minimo real DEFAULT 0.6)
RETURNS TABLE (alumno_id bigint, curp text, parecido real, primer_apellido text, segundo_apellido text, nombres text,
               grado smallint, letra text)
LANGUAGE sql STABLE AS $$
    SELECT a.id, a.curp, word_similarity(a.nombre_busqueda, sidp.normalizar(texto)), a.primer_apellido, a.segundo_apellido,
           a.nombres, a.grado, a.letra
    FROM sidp.v_alumnos a
    WHERE a.estado = 'activo' AND word_similarity(a.nombre_busqueda, sidp.normalizar(texto)) >= minimo
    ORDER BY 3 DESC, 1
    LIMIT 5
$$;

-- Búsqueda para el panel: una CURP (completa o con errores) o un nombre.
CREATE OR REPLACE FUNCTION sidp.buscar(texto text)
RETURNS TABLE (alumno_id bigint, curp text, primer_apellido text, segundo_apellido text, nombres text, grado smallint,
               letra text, por text, cercania real)
LANGUAGE sql STABLE AS $$
    SELECT c.alumno_id, c.curp, c.primer_apellido, c.segundo_apellido, c.nombres, c.grado, c.letra, 'curp', 1 - c.distancia / 18.0
    FROM sidp.curp_cercana(sidp.normalizar(texto), 3) c
    WHERE length(replace(sidp.normalizar(texto), ' ', '')) = 18
    UNION ALL
    SELECT n.alumno_id, n.curp, n.primer_apellido, n.segundo_apellido, n.nombres, n.grado, n.letra, 'nombre', n.parecido
    FROM sidp.nombre_cercano(texto, 0.5) n
    WHERE length(replace(sidp.normalizar(texto), ' ', '')) <> 18
$$;

CREATE OR REPLACE FUNCTION sidp.registrar_lectura(metodo_lectura text, caracteres_leidos integer, tipo text, curp text,
                                                   alumno bigint, letras integer, cercania real)
RETURNS bigint
LANGUAGE sql AS $$
    INSERT INTO sidp.lectura (metodo, caracteres, tipo_detectado, curp_leida, alumno_id, distancia, parecido)
    VALUES (metodo_lectura, caracteres_leidos, tipo, curp, alumno, letras, cercania)
    RETURNING id
$$;

-- Un documento nuevo en el expediente. Si ya había uno del mismo tipo, el anterior queda "reemplazado".
CREATE OR REPLACE FUNCTION sidp.registrar_documento(alumno bigint, tipo_documento text, huella text, origen_documento text,
                                                     hojas integer DEFAULT NULL, fecha date DEFAULT NULL, tutor bigint DEFAULT NULL,
                                                     actor text DEFAULT 'sistema')
RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE
    anterior bigint;
    nuevo bigint;
BEGIN
    PERFORM set_config('sidp.actor', actor, true);
    SELECT id INTO anterior FROM sidp.documento
    WHERE alumno_id = alumno AND tipo = tipo_documento AND estado <> 'reemplazado'
    ORDER BY id DESC LIMIT 1;
    INSERT INTO sidp.documento (alumno_id, tutor_id, tipo, sha256, paginas, origen, fecha_documento, reemplaza_a)
    VALUES (alumno, tutor, tipo_documento, lower(huella), hojas, origen_documento, fecha, anterior)
    RETURNING id INTO nuevo;
    IF anterior IS NOT NULL THEN
        UPDATE sidp.documento SET estado = 'reemplazado' WHERE id = anterior;
    END IF;
    RETURN nuevo;
END $$;

-- Una persona valida o rechaza un documento (rechazar pide motivo).
CREATE OR REPLACE FUNCTION sidp.revisar_documento(id_documento bigint, resultado_revision text, persona text, motivo_revision text DEFAULT NULL)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('sidp.actor', persona, true);
    INSERT INTO sidp.revision_documento (documento_id, resultado, motivo, reviso)
    VALUES (id_documento, resultado_revision, motivo_revision, persona);
    UPDATE sidp.documento SET estado = resultado_revision,
                              motivo_rechazo = CASE WHEN resultado_revision = 'rechazado' THEN motivo_revision END
    WHERE id = id_documento;
END $$;

-- Marca como vencidos los documentos con vigencia (comprobante de domicilio) más viejos que su plazo.
CREATE OR REPLACE FUNCTION sidp.vencer_documentos(hoy date DEFAULT current_date) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    vencidos integer;
BEGIN
    PERFORM set_config('sidp.actor', 'vencimiento', true);
    UPDATE sidp.documento d SET estado = 'vencido'
    FROM sidp.tipo_documento t
    WHERE t.clave = d.tipo AND t.vigencia_meses IS NOT NULL AND d.estado IN ('recibido', 'validado')
      AND d.fecha_documento IS NOT NULL AND d.fecha_documento + make_interval(months => t.vigencia_meses) < hoy;
    GET DIAGNOSTICS vencidos = ROW_COUNT;
    RETURN vencidos;
END $$;

-- Lo que dijo RENAPO de una CURP (la consulta la hace una persona por el captcha).
CREATE OR REPLACE FUNCTION sidp.marcar_renapo(curp_alumno text, resultado text, persona text) RETURNS boolean
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('sidp.actor', persona, true);
    UPDATE sidp.alumno SET curp_renapo = resultado WHERE curp = upper(curp_alumno);
    RETURN FOUND;
END $$;

CREATE OR REPLACE FUNCTION sidp.cambiar_grupo(alumno bigint, nombre_ciclo text, grado_nuevo integer, letra_nueva text, persona text)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('sidp.actor', persona, true);
    UPDATE sidp.inscripcion SET grupo_id = sidp.asegurar_grupo(nombre_ciclo, grado_nuevo, letra_nueva)
    WHERE alumno_id = alumno AND ciclo = nombre_ciclo AND estado IN ('incompleta', 'completa');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El alumno % no está inscrito en %', alumno, nombre_ciclo;
    END IF;
END $$;

CREATE OR REPLACE FUNCTION sidp.dar_baja(alumno bigint, nombre_ciclo text, motivo text, persona text, fecha date DEFAULT current_date)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF coalesce(btrim(motivo), '') = '' THEN
        RAISE EXCEPTION 'La baja necesita un motivo';
    END IF;
    PERFORM set_config('sidp.actor', persona, true);
    UPDATE sidp.inscripcion SET estado = 'baja', baja = fecha, motivo_baja = motivo
    WHERE alumno_id = alumno AND ciclo = nombre_ciclo AND estado IN ('incompleta', 'completa');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El alumno % no está inscrito en %', alumno, nombre_ciclo;
    END IF;
END $$;

-- Todo de un vistazo, solo con números (se puede copiar a un informe sin datos personales).
CREATE OR REPLACE FUNCTION sidp.resumen() RETURNS jsonb
LANGUAGE sql STABLE AS $$
    SELECT jsonb_build_object(
        'motor', 'PostgreSQL ' || split_part(current_setting('server_version'), ' ', 1),
        'esquema', (SELECT valor FROM sidp.meta WHERE clave = 'version'),
        'alumnos', (SELECT count(*) FROM sidp.v_inscritos),
        'grupos', (SELECT coalesce(jsonb_agg(jsonb_build_object('grupo', grado || '° ' || letra, 'alumnos', alumnos, 'hombres', hombres,
                                                                'mujeres', mujeres, 'extraedad', extraedad)
                                             ORDER BY grado, letra), '[]')
                   FROM sidp.v_resumen_grupo WHERE ciclo = (SELECT max(ciclo) FROM sidp.v_inscritos)),
        'documentos', (SELECT count(*) FROM sidp.documento WHERE estado <> 'reemplazado'),
        'expedientes_completos', (SELECT count(*) FROM sidp.v_inscritos a
                                  WHERE NOT EXISTS (SELECT 1 FROM sidp.v_faltantes f WHERE f.alumno_id = a.id)),
        'lecturas', (SELECT count(*) FROM sidp.lectura),
        'alertas', (SELECT coalesce(jsonb_object_agg(tipo, n), '{}') FROM (SELECT tipo, count(*) AS n FROM sidp.v_alertas GROUP BY tipo) x),
        'bitacora', (SELECT count(*) FROM sidp.bitacora))
$$;

-- ============================================================ Versión 1 → versión 2

DO $$
DECLARE
    resultado jsonb;
BEGIN
    IF to_regclass('public.padron_alumno') IS NOT NULL THEN
        resultado := sidp.cargar_alumnos(
            coalesce((SELECT jsonb_agg(jsonb_build_object('curp', curp, 'primer_apellido', primer_apellido,
                                                          'segundo_apellido', segundo_apellido, 'nombres', nombres,
                                                          'grado', grado, 'letra', letra))
                      FROM public.padron_alumno WHERE activo AND grado IS NOT NULL), '[]'),
            coalesce((SELECT max(ciclo) FROM public.padron_alumno), sidp.ciclo_de(current_date)), 'validador', 'paso a la versión 2');
        ALTER TABLE public.padron_alumno RENAME TO padron_alumno_v1;
        RAISE NOTICE 'Padrón de la versión 1 pasado a la 2: %', resultado;
    END IF;
    IF to_regclass('public.lectura') IS NOT NULL THEN
        ALTER TABLE public.lectura RENAME TO lectura_v1;
    END IF;
END $$;
DROP FUNCTION IF EXISTS public.sidp_cargar_padron(jsonb, text);
DROP FUNCTION IF EXISTS public.sidp_curp_cercana(text, integer);
DROP FUNCTION IF EXISTS public.sidp_nombre_cercano(text, real);

-- ============================================================ Inventario de la escuela

-- Cada pieza (una mesa, una computadora) tiene su propio código de barras. Las piezas iguales que se dan de
-- alta juntas forman un lote con sus características (por ejemplo, 4 computadoras con el mismo procesador).
CREATE TABLE IF NOT EXISTS sidp.inventario_categoria (
    clave    text PRIMARY KEY,
    nombre   text NOT NULL,
    prefijo  text NOT NULL UNIQUE CHECK (prefijo ~ '^[A-Z]{3}$'),
    orden    integer NOT NULL DEFAULT 0
);
INSERT INTO sidp.inventario_categoria (clave, nombre, prefijo, orden) VALUES
    ('mobiliario', 'Mobiliario (mesas, sillas, pizarrones, estantes)', 'MOB', 1),
    ('computo',    'Cómputo (computadoras, impresoras, proyectores)',  'COM', 2),
    ('material',   'Material didáctico y deportivo',                   'MAT', 3),
    ('otro',       'Otro',                                             'OTR', 4)
ON CONFLICT (clave) DO NOTHING;

CREATE SEQUENCE IF NOT EXISTS sidp.inventario_folio;

CREATE TABLE IF NOT EXISTS sidp.inventario_lote (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria        text NOT NULL REFERENCES sidp.inventario_categoria (clave),
    nombre           text NOT NULL CHECK (btrim(nombre) <> ''),
    caracteristicas  jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(caracteristicas) = 'object'),
    cantidad         integer NOT NULL CHECK (cantidad BETWEEN 1 AND 500),
    ubicacion        text,
    creado           timestamptz NOT NULL DEFAULT now(),
    actor            text NOT NULL
);

CREATE TABLE IF NOT EXISTS sidp.inventario_pieza (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo        text NOT NULL UNIQUE CHECK (codigo ~ '^[A-Z]{3}-[0-9]{6}$'),
    lote_id       bigint NOT NULL REFERENCES sidp.inventario_lote (id),
    numero_serie  text,
    ubicacion     text,
    estado        text NOT NULL DEFAULT 'bueno' CHECK (estado IN ('bueno', 'regular', 'malo', 'baja')),
    notas         text,
    version       integer NOT NULL DEFAULT 1,
    creado        timestamptz NOT NULL DEFAULT now(),
    actualizado   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inventario_pieza_lote ON sidp.inventario_pieza (lote_id);
CREATE INDEX IF NOT EXISTS inventario_lote_nombre ON sidp.inventario_lote USING gin (sidp.normalizar(nombre) gin_trgm_ops);

DO $$
DECLARE
    tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['inventario_categoria', 'inventario_lote', 'inventario_pieza'] LOOP
        EXECUTE format('CREATE OR REPLACE TRIGGER no_borrar BEFORE DELETE ON sidp.%I FOR EACH ROW EXECUTE FUNCTION sidp.no_borrar()', tabla);
        EXECUTE format('CREATE OR REPLACE TRIGGER no_vaciar BEFORE TRUNCATE ON sidp.%I FOR EACH STATEMENT EXECUTE FUNCTION sidp.no_borrar()', tabla);
    END LOOP;
    FOREACH tabla IN ARRAY ARRAY['inventario_lote', 'inventario_pieza'] LOOP
        EXECUTE format('CREATE OR REPLACE TRIGGER anotar_cambio AFTER INSERT OR UPDATE ON sidp.%I FOR EACH ROW EXECUTE FUNCTION sidp.anotar_cambio()', tabla);
    END LOOP;
END $$;
CREATE OR REPLACE TRIGGER subir_version BEFORE UPDATE ON sidp.inventario_pieza FOR EACH ROW EXECUTE FUNCTION sidp.subir_version();

-- Da de alta N piezas iguales: un lote y un código por pieza (MOB-000001, MOB-000002...).
CREATE OR REPLACE FUNCTION sidp.inventario_alta(clave_categoria text, nombre_lote text, datos jsonb, cuantas integer,
                                                donde text, series text[], quien text)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_prefijo text;
    v_lote bigint;
    codigos text[] := '{}';
    v_codigo text;
BEGIN
    IF quien IS NULL OR btrim(quien) = '' THEN
        RAISE EXCEPTION 'Falta quién da de alta';
    END IF;
    SELECT prefijo INTO v_prefijo FROM sidp.inventario_categoria WHERE clave = clave_categoria;
    IF v_prefijo IS NULL THEN
        RAISE EXCEPTION 'No existe la categoría %', clave_categoria;
    END IF;
    PERFORM set_config('sidp.actor', quien, true);
    INSERT INTO sidp.inventario_lote (categoria, nombre, caracteristicas, cantidad, ubicacion, actor)
    VALUES (clave_categoria, upper(btrim(nombre_lote)), coalesce(datos, '{}'), cuantas, nullif(btrim(donde), ''), quien)
    RETURNING id INTO v_lote;
    FOR i IN 1..cuantas LOOP
        v_codigo := v_prefijo || '-' || lpad(nextval('sidp.inventario_folio')::text, 6, '0');
        INSERT INTO sidp.inventario_pieza (codigo, lote_id, numero_serie, ubicacion)
        VALUES (v_codigo, v_lote, nullif(btrim(coalesce(series[i], '')), ''), nullif(btrim(donde), ''));
        codigos := codigos || v_codigo;
    END LOOP;
    RETURN jsonb_build_object('lote', v_lote, 'codigos', to_jsonb(codigos));
END $$;

-- Cambia el estado, el lugar o las notas de una pieza; una baja pide motivo.
CREATE OR REPLACE FUNCTION sidp.inventario_cambiar(codigo_pieza text, nuevo_estado text, nueva_ubicacion text, nuevas_notas text, quien text)
RETURNS jsonb
LANGUAGE plpgsql AS $$
BEGIN
    IF quien IS NULL OR btrim(quien) = '' THEN
        RAISE EXCEPTION 'Falta quién hace el cambio';
    END IF;
    IF nuevo_estado = 'baja' AND coalesce(btrim(nuevas_notas), '') = '' THEN
        RAISE EXCEPTION 'Para dar de baja una pieza escribe el motivo en las notas';
    END IF;
    PERFORM set_config('sidp.actor', quien, true);
    UPDATE sidp.inventario_pieza
    SET estado = coalesce(nullif(nuevo_estado, ''), estado),
        ubicacion = coalesce(nullif(btrim(nueva_ubicacion), ''), ubicacion),
        notas = coalesce(nullif(btrim(nuevas_notas), ''), notas)
    WHERE codigo = upper(btrim(codigo_pieza));
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe la pieza %', codigo_pieza;
    END IF;
    RETURN (SELECT to_jsonb(p) FROM sidp.inventario_pieza p WHERE codigo = upper(btrim(codigo_pieza)));
END $$;

CREATE OR REPLACE VIEW sidp.v_inventario AS
SELECT p.codigo, p.estado, coalesce(p.ubicacion, l.ubicacion) AS ubicacion, p.numero_serie, p.notas, p.version,
       p.actualizado, l.id AS lote, l.categoria, c.nombre AS categoria_nombre, l.nombre, l.caracteristicas, l.creado
FROM sidp.inventario_pieza p
JOIN sidp.inventario_lote l ON l.id = p.lote_id
JOIN sidp.inventario_categoria c ON c.clave = l.categoria;


-- ============================================================ Datos sacados de los documentos (versión 3)
--
-- Los documentos traen datos muy variables: un certificado médico trae 3 campos o 20, un domicilio viene
-- completo o a medias, y un alumno tiene uno o cinco teléfonos. Por eso cada dato es un renglón (alumno,
-- categoría, campo, valor) y no una columna fija: una plantilla nueva puede traer campos nuevos sin cambiar
-- la base. Lo que tiene partes (un domicilio, de quién es un teléfono) va en "detalle".
-- Confianza: confirmado (lo vio una persona), alta (lo dio un proceso fijo: QR, CURP con dígito correcto, o
-- coincide con otro documento), media (lo leyó el modelo y pasa las reglas) y baja (dudoso: por confirmar).

CREATE TABLE IF NOT EXISTS sidp.trabajo (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alumno_id    bigint NOT NULL REFERENCES sidp.alumno(id) ON DELETE RESTRICT,
    expediente   text,                        -- El número del expediente en el servidor.
    documentos   jsonb NOT NULL,              -- [{archivo, tipo, nombre, campos}]
    estado       text NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'trabajando', 'hecho', 'error')),
    intentos     integer NOT NULL DEFAULT 0,
    problema     text,
    resumen      jsonb,                       -- Cuántos campos se llenaron y con qué confianza (solo números).
    creado       timestamptz NOT NULL DEFAULT now(),
    terminado    timestamptz
);
CREATE INDEX IF NOT EXISTS trabajo_estado ON sidp.trabajo (estado, id);

CREATE TABLE IF NOT EXISTS sidp.dato (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alumno_id   bigint NOT NULL REFERENCES sidp.alumno(id) ON DELETE RESTRICT,
    categoria   text NOT NULL CHECK (categoria IN ('alumno', 'salud', 'contacto', 'domicilio', 'madre', 'padre', 'tutor', 'escolar', 'otro')),
    campo       text NOT NULL CHECK (campo ~ '^[a-z0-9_]{1,40}$'),
    valor       text NOT NULL CHECK (btrim(valor) <> ''),
    detalle     jsonb NOT NULL DEFAULT '{}',
    confianza   text NOT NULL CHECK (confianza IN ('confirmado', 'alta', 'media', 'baja')),
    metodo      text NOT NULL,               -- qr, texto, ocr, vision, padron, persona
    documento   text,                        -- De qué documento o plantilla salió.
    trabajo_id  bigint REFERENCES sidp.trabajo(id) ON DELETE RESTRICT,
    estado      text NOT NULL DEFAULT 'vigente' CHECK (estado IN ('vigente', 'por_confirmar', 'reemplazado', 'descartado')),
    quien       text NOT NULL DEFAULT 'sistema',
    creado      timestamptz NOT NULL DEFAULT now(),
    actualizado timestamptz NOT NULL DEFAULT now(),
    version     integer NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS dato_alumno ON sidp.dato (alumno_id, categoria, campo) WHERE estado IN ('vigente', 'por_confirmar');
CREATE INDEX IF NOT EXISTS dato_por_confirmar ON sidp.dato (estado) WHERE estado = 'por_confirmar';

DO $$
DECLARE
    tabla text;
BEGIN
    FOREACH tabla IN ARRAY ARRAY['trabajo', 'dato'] LOOP
        EXECUTE format('CREATE OR REPLACE TRIGGER no_borrar BEFORE DELETE ON sidp.%I FOR EACH ROW EXECUTE FUNCTION sidp.no_borrar()', tabla);
        EXECUTE format('CREATE OR REPLACE TRIGGER no_vaciar BEFORE TRUNCATE ON sidp.%I FOR EACH STATEMENT EXECUTE FUNCTION sidp.no_borrar()', tabla);
    END LOOP;
END $$;
CREATE OR REPLACE TRIGGER subir_version BEFORE UPDATE ON sidp.dato FOR EACH ROW EXECUTE FUNCTION sidp.subir_version();
CREATE OR REPLACE TRIGGER anotar_cambio AFTER INSERT OR UPDATE ON sidp.dato FOR EACH ROW EXECUTE FUNCTION sidp.anotar_cambio();

-- Guarda un dato sin perder lo anterior. Un campo de un solo valor (tipo de sangre) reemplaza al anterior si es
-- distinto; uno de varios valores (teléfono) se agrega si no estaba. Un dato confirmado por una persona no lo
-- reemplaza una lectura: la lectura nueva queda por confirmar. Devuelve el id del dato vigente o por confirmar.
CREATE OR REPLACE FUNCTION sidp.guardar_dato(alumno bigint, cat text, nombre_campo text, nuevo_valor text, nuevo_detalle jsonb,
                                             nivel text, metodo_dato text, de_documento text, trabajo bigint, persona text,
                                             varios boolean DEFAULT false)
RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE
    igual   sidp.dato;
    actual  sidp.dato;
    nuevo   bigint;
    estado_nuevo text := CASE WHEN nivel = 'baja' THEN 'por_confirmar' ELSE 'vigente' END;
BEGIN
    nuevo_valor := btrim(nuevo_valor);
    IF coalesce(nuevo_valor, '') = '' THEN
        RETURN NULL;
    END IF;
    PERFORM set_config('sidp.actor', persona, true);
    SELECT * INTO igual FROM sidp.dato
    WHERE alumno_id = alumno AND categoria = cat AND campo = nombre_campo AND estado IN ('vigente', 'por_confirmar')
      AND sidp.normalizar(valor) = sidp.normalizar(nuevo_valor)
    ORDER BY id DESC LIMIT 1;
    IF FOUND THEN  -- Ya estaba: si ahora es más seguro, se sube su confianza.
        IF array_position(ARRAY['baja', 'media', 'alta', 'confirmado'], nivel) > array_position(ARRAY['baja', 'media', 'alta', 'confirmado'], igual.confianza) THEN
            UPDATE sidp.dato SET confianza = nivel, estado = 'vigente', metodo = metodo_dato, quien = persona WHERE id = igual.id;
        END IF;
        RETURN igual.id;
    END IF;
    IF nivel <> 'confirmado' AND EXISTS (SELECT 1 FROM sidp.dato WHERE alumno_id = alumno AND categoria = cat AND campo = nombre_campo
                                         AND estado = 'descartado' AND sidp.normalizar(valor) = sidp.normalizar(nuevo_valor)) THEN
        RETURN NULL;  -- Una persona ya vio esa lectura y la corrigió o la descartó: no se le vuelve a preguntar.
    END IF;
    IF NOT varios THEN
        SELECT * INTO actual FROM sidp.dato
        WHERE alumno_id = alumno AND categoria = cat AND campo = nombre_campo AND estado = 'vigente' ORDER BY id DESC LIMIT 1;
        IF FOUND AND actual.confianza = 'confirmado' AND nivel <> 'confirmado' THEN
            estado_nuevo := 'por_confirmar';
        ELSIF FOUND AND estado_nuevo = 'vigente' THEN
            UPDATE sidp.dato SET estado = 'reemplazado' WHERE id = actual.id;
        END IF;
    END IF;
    INSERT INTO sidp.dato (alumno_id, categoria, campo, valor, detalle, confianza, metodo, documento, trabajo_id, estado, quien)
    VALUES (alumno, cat, nombre_campo, nuevo_valor, coalesce(nuevo_detalle, '{}'), nivel, metodo_dato, de_documento, trabajo,
            estado_nuevo, persona)
    RETURNING id INTO nuevo;
    RETURN nuevo;
END $$;

-- Una persona confirma (o corrige) un dato dudoso; o lo descarta si no sirve.
CREATE OR REPLACE FUNCTION sidp.confirmar_dato(id_dato bigint, valor_correcto text, persona text, descartar boolean DEFAULT false)
RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE
    d sidp.dato;
    nuevo bigint;
BEGIN
    SELECT * INTO d FROM sidp.dato WHERE id = id_dato;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe el dato %', id_dato;
    END IF;
    PERFORM set_config('sidp.actor', persona, true);
    UPDATE sidp.dato SET estado = 'descartado', quien = persona WHERE id = id_dato;
    IF descartar THEN
        RETURN NULL;
    END IF;
    nuevo := sidp.guardar_dato(d.alumno_id, d.categoria, d.campo, coalesce(nullif(btrim(valor_correcto), ''), d.valor), d.detalle,
                               'confirmado', 'persona', d.documento, d.trabajo_id, persona,
                               d.campo IN ('telefono', 'correo', 'alergia', 'padecimiento', 'medicamento', 'discapacidad', 'cirugia',
                                           'otro_dato') OR d.campo ~ '^materia(_[1-6])?$');
    RETURN nuevo;
END $$;

-- Un administrador borra a un alumno (por ejemplo, se cargó por error). Se quita de todas las tablas; la
-- bitácora guarda qué se borró, quién y por qué. Para un alumno que se va de la escuela se usa dar_baja.
CREATE OR REPLACE FUNCTION sidp.borrar_alumno(id_alumno bigint, persona text, motivo text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    registro sidp.alumno;
    doc bigint;
BEGIN
    IF coalesce(btrim(motivo), '') = '' THEN
        RAISE EXCEPTION 'Borrar a un alumno necesita un motivo';
    END IF;
    SELECT * INTO registro FROM sidp.alumno WHERE id = id_alumno;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe el alumno %', id_alumno;
    END IF;
    PERFORM set_config('sidp.actor', persona, true);
    PERFORM set_config('sidp.borrando', 'si', true);
    INSERT INTO sidp.bitacora (actor, accion, tabla, registro, antes, despues)
    VALUES (persona, 'borrar', 'alumno', id_alumno::text, to_jsonb(registro), jsonb_build_object('motivo', motivo));
    DELETE FROM sidp.dato WHERE alumno_id = id_alumno;
    DELETE FROM sidp.trabajo WHERE alumno_id = id_alumno;
    UPDATE sidp.lectura SET alumno_id = NULL WHERE alumno_id = id_alumno;
    DELETE FROM sidp.revision_documento WHERE documento_id IN (SELECT id FROM sidp.documento WHERE alumno_id = id_alumno);
    FOR doc IN SELECT id FROM sidp.documento WHERE alumno_id = id_alumno ORDER BY id DESC LOOP
        DELETE FROM sidp.documento WHERE id = doc;  -- Del más nuevo al más viejo (uno reemplaza al anterior).
    END LOOP;
    DELETE FROM sidp.inscripcion WHERE alumno_id = id_alumno;
    DELETE FROM sidp.alumno_tutor WHERE alumno_id = id_alumno;
    DELETE FROM sidp.alumno WHERE id = id_alumno;
    PERFORM set_config('sidp.borrando', '', true);
END $$;

-- Todo lo del alumno vigente, por categoría: lo que muestra el expediente.
CREATE OR REPLACE VIEW sidp.v_datos AS
    SELECT d.alumno_id, d.categoria, d.campo, d.valor, d.detalle, d.confianza, d.metodo, d.documento, d.estado, d.id, d.creado
    FROM sidp.dato d WHERE d.estado IN ('vigente', 'por_confirmar');

-- ============================================================ Velocidad

CREATE INDEX IF NOT EXISTS inscripcion_ciclo_estado ON sidp.inscripcion (ciclo, estado);
CREATE INDEX IF NOT EXISTS documento_alumno_tipo ON sidp.documento (alumno_id, tipo, estado);
CREATE INDEX IF NOT EXISTS lectura_recibida ON sidp.lectura (recibida);

INSERT INTO sidp.meta (clave, valor) VALUES ('version', '3') ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor;
