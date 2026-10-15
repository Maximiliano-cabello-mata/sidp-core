-- Base de datos del cerebro (PC 4), en PostgreSQL.
--
-- Guarda el padrón de alumnos (lo manda SIDP-Validador.exe al guardar las listas de grupo) y una
-- anotación de cada lectura. Sirve para que el cerebro compare lo que lee contra los nombres y CURP
-- reales: una CURP con una o dos letras mal leídas, o un apellido con faltas de ortografía, se
-- reconocen. Todo lo que sale de aquí es una propuesta; la persona decide.
--
-- Se puede correr las veces que sea: no borra nada. Las dos extensiones vienen con PostgreSQL y el
-- dueño de la base las puede crear sin ser superusuario.

CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- parecido entre textos (trigramas)
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;  -- levenshtein: cuántas letras cambian

CREATE TABLE IF NOT EXISTS padron_alumno (
    curp              char(18) PRIMARY KEY,
    primer_apellido   text NOT NULL,
    segundo_apellido  text NOT NULL DEFAULT '',
    nombres           text NOT NULL,
    nombre_completo   text NOT NULL,  -- Nombres y apellidos en mayúsculas, sin acentos: así se compara.
    grado             smallint,
    letra             text,
    ciclo             text NOT NULL,
    activo            boolean NOT NULL DEFAULT true,  -- Un alumno que sale de la lista se apaga; no se borra.
    actualizado       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS padron_alumno_nombre ON padron_alumno USING gin (nombre_completo gin_trgm_ops);

CREATE TABLE IF NOT EXISTS lectura (
    id           bigserial PRIMARY KEY,
    recibida     timestamptz NOT NULL DEFAULT now(),
    metodo       text,        -- pdf, ocr, qr...
    caracteres   integer,     -- Cuánto texto salió (0 = no se pudo leer).
    curp_leida   text,        -- La CURP tal como se leyó, si se leyó una.
    curp_padron  char(18),    -- La del padrón que más se le parece.
    distancia    smallint,    -- Letras distintas entre las dos (0 = idéntica).
    parecido     real         -- Si se reconoció por el nombre: qué tanto se parece (1 = idéntico).
);

-- Carga el padrón de un ciclo: agrega o actualiza a cada alumno y apaga a los que ya no vienen.
CREATE OR REPLACE FUNCTION sidp_cargar_padron(datos jsonb, ciclo_actual text) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    cargados integer;
BEGIN
    INSERT INTO padron_alumno AS p (curp, primer_apellido, segundo_apellido, nombres, nombre_completo, grado, letra, ciclo)
    SELECT upper(a->>'curp'), a->>'primer_apellido', coalesce(a->>'segundo_apellido', ''), a->>'nombres',
           a->>'nombre_completo', (a->>'grado')::smallint, a->>'letra', ciclo_actual
    FROM jsonb_array_elements(datos) AS a
    WHERE length(a->>'curp') = 18
    ON CONFLICT (curp) DO UPDATE SET
        primer_apellido = excluded.primer_apellido, segundo_apellido = excluded.segundo_apellido,
        nombres = excluded.nombres, nombre_completo = excluded.nombre_completo, grado = excluded.grado,
        letra = excluded.letra, ciclo = excluded.ciclo, activo = true, actualizado = now();
    GET DIAGNOSTICS cargados = ROW_COUNT;
    UPDATE padron_alumno SET activo = false, actualizado = now()
    WHERE ciclo = ciclo_actual AND activo
      AND curp NOT IN (SELECT upper(a->>'curp') FROM jsonb_array_elements(datos) AS a);
    RETURN cargados;
END $$;

-- Las CURP del padrón a dos letras o menos de la que se leyó, la más cercana primero.
CREATE OR REPLACE FUNCTION sidp_curp_cercana(leida text, maximo integer DEFAULT 2)
RETURNS TABLE (curp char(18), distancia integer, primer_apellido text, segundo_apellido text, nombres text,
               grado smallint, letra text)
LANGUAGE sql STABLE AS $$
    SELECT p.curp, levenshtein(p.curp, upper(leida)), p.primer_apellido, p.segundo_apellido, p.nombres, p.grado, p.letra
    FROM padron_alumno p
    WHERE p.activo AND levenshtein(p.curp, upper(leida)) <= maximo
    ORDER BY 2, 1
    LIMIT 3
$$;

-- Los alumnos del padrón cuyo nombre aparece en el texto, aunque esté mal escrito o en otro orden.
CREATE OR REPLACE FUNCTION sidp_nombre_cercano(texto text, minimo real DEFAULT 0.6)
RETURNS TABLE (curp char(18), parecido real, primer_apellido text, segundo_apellido text, nombres text,
               grado smallint, letra text)
LANGUAGE sql STABLE AS $$
    SELECT p.curp, word_similarity(p.nombre_completo, texto), p.primer_apellido, p.segundo_apellido, p.nombres,
           p.grado, p.letra
    FROM padron_alumno p
    WHERE p.activo AND word_similarity(p.nombre_completo, texto) >= minimo
    ORDER BY 2 DESC, 1
    LIMIT 5
$$;
