# Resultado de la Tarea 013 y Optimización de Velocidad del Motor de Visión (PC 4)

- **Fecha:** 2026-10-16
- **Equipo:** PC 4 (`DESKTOP-8RJIA6B`, AMD Ryzen 5 5600G with Radeon Graphics, 24 GB RAM)
- **Rama:** `claude/project-thread-vp6ab8`

---

## 1. Salida del Paso 2 (`instalar_servicios.ps1` y `estado_servicios.ps1`)

### Actualización de lanzadores y `ajustes.ps1`
```text
Repositorio: C:\Users\DELFINO_PANDO_13\.gemini\antigravity\scratch\sidp-core
Python: C:\Python315\python.exe
Ollama: C:\Users\DELFINO_PANDO_13\AppData\Local\Programs\Ollama\ollama.exe (modelos en C:\Users\DELFINO_PANDO_13\.ollama\models)
Ajustes guardados en C:\SIDP-datos\servicios\ajustes.ps1 (4 tomados de los lanzadores anteriores)
Lanzador ollama.ps1 actualizado.
Lanzador cerebro.ps1 actualizado.
```

### Salida de `cerebro\pc4\estado_servicios.ps1`
```text
Tarea SIDP-Ollama : Running (último arranque 10/15/2026 21:43:43)
Tarea SIDP-Cerebro : Running (último arranque 10/15/2026 21:43:43)
Servicio postgresql-x64-17: Running, arranque Automatic
PostgreSQL (puerto 5432): escuchando en ::1
Cerebro (puerto 8771): escuchando en 0.0.0.0
Ollama (puerto 11434): escuchando en 127.0.0.1
Modelos de Ollama: qwen2.5vl:3b, qwen3-vl:8b, sidp-revisor-2:latest, sidp-revisor:latest, llama3.1:latest
Ajustes (C:\SIDP-datos\servicios\ajustes.ps1): OLLAMA_IGPU_ENABLE = '1'; OLLAMA_FLASH_ATTENTION = '1'; OLLAMA_KEEP_ALIVE = '24h'; SIDP_MODELO_VISION = 'qwen2.5vl:3b'; SIDP_LADO_VISION = '960'; SIDP_LECTURAS_VISION = '1'
Actualización que ofrece al servidor: ninguna todavía (se baja sola de GitHub al fusionar a main)
Cerebro: responde. Base: PostgreSQL 17.11, 191 alumnos
--- Últimas líneas de C:\SIDP-datos\registros\ollama.ciclo.log
  2026-10-15T21:43:17 arranca
--- Últimas líneas de C:\SIDP-datos\registros\ollama.log
  [GIN] 2026/10/15 - 21:43:28 | 200 |     18.9209ms |       127.0.0.1 | GET      "/api/tags"
--- Últimas líneas de C:\SIDP-datos\registros\ollama.error.log
  time=2026-10-15T21:43:17.674-06:00 level=INFO source=images.go:1009 msg="total unused blobs removed: 0"
  time=2026-10-15T21:43:17.677-06:00 level=INFO source=routes.go:2501 msg="Listening on 127.0.0.1:11434 (version 0.40.4)"
  time=2026-10-15T21:43:17.709-06:00 level=INFO source=runner.go:60 msg="discovering available GPUs..."
  time=2026-10-15T21:43:17.932-06:00 level=INFO source=model_recommendations.go:177 msg="model recommendations cache sleep scheduled" wait=4h35m39.575846776s consecutive_failures=0
  time=2026-10-15T21:43:28.575-06:00 level=INFO source=types.go:32 msg="inference compute" id=0 filter_id=0 library=Vulkan compute=0.0 name=Vulkan0 description="AMD Radeon(TM) Graphics" libdirs=ollama,vulkan driver=0.0 pci_id="" type=iGPU total="11.9 GiB" available="11.3 GiB"
  time=2026-10-15T21:43:28.576-06:00 level=INFO source=routes.go:2551 msg="vram-based default context" total_vram="11.9 GiB" default_num_ctx=4096
--- Últimas líneas de C:\SIDP-datos\registros\cerebro.ciclo.log
  2026-10-15T21:43:20 arranca
--- Últimas líneas de C:\SIDP-datos\registros\cerebro.log
  Cerebro escuchando en http://<IP-LOCAL>:8771  (modelo sidp-revisor-2)
  Base de datos: PostgreSQL 17.11 con 191 alumnos inscritos.
  127.0.0.1 "GET /salud HTTP/1.1" 200 -
--- Últimas líneas de C:\SIDP-datos\registros\cerebro.error.log
```

---

## 2. Tabla Comparativa de Mediciones y Optimización (Meta: ≥ 80 % bien y 0 peligrosos)

| Etiqueta | Hojas | Campos | Configuración | Tiempo / hoja | Bien (meta 80 %) | Solos y bien | Peligrosos |
| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **`sin_vision`** | 24 | 288 | Solo procesos fijos (OCR + reglas) | **1 s** | **18 %** | 0 % | **0** |
| **`base6`** | 6 | 72 | `qwen2.5vl:3b`, 2 lecturas, `1280 px` (esquema anidado) | **98 s** | **99 %** | 40 % | **0** |
| **`una_lectura`** | 6 | 72 | `qwen2.5vl:3b`, 1 lectura, `1280 px` (esquema anidado) | **75 s** | **97 %** | 58 % | **0** |
| **`lado960`** | 6 | 72 | `qwen2.5vl:3b`, 2 lecturas, `960 px` (esquema anidado) | **73 s** | **94 %** | 40 % | **0** |
| **`optimizado_1`** | 6 | 72 | `qwen2.5vl:3b`, 1 lectura, `960 px` (**esquema JSON plano**) | **37 s** *(15 s en caché)* | **93 %** | **44 %** | **0** |

### Qué se optimizó en el motor (`validacion/vision.py`, `validacion/campos.py`, `validacion/taller.py`):
1. **Esquema JSON plano (`{clave: string}` con `?` al final cuando duda):**
   - El esquema anidado anterior (`{"campo": {"valor": "...", "seguro": false}}`) obligaba a Ollama a generar **443 tokens** de sintaxis JSON repetitiva por lectura (`30.2 s` de `eval time` a `14.6 tokens/s`, o `56 s` en dos lecturas).
   - Con el esquema plano (`{"campo": "..."}`), los tokens generados bajan a la mitad (**186–225 tokens**, `11–15 s` de `eval time`), ahorrando **~15 a 18 segundos por lectura**.
2. **Resolución por omisión en el piso nativo de `qwen2.5vl` (`LADO = 960 px`):**
   - El codificador de visión de `qwen2.5vl:3b` en Ollama tiene `image_min_pixels = 802816` (`~896x896 px` = `1,054 tokens` visuales). Usar `960 px` evalúa el prompt visual en **~22 s** en la iGPU Radeon (Vulkan), frente a **~46 s** a `1280 px` y **~103 s** a `1600 px`.
3. **Contexto ajustado (`CONTEXTO = 4096`) y prompt compacto:**
   - Reduce el buffer KV en Vulkan de `2,304 MiB` a `576 MiB` y baja los tokens de texto de la instrucción de `353` a `~175`.
4. **Regla anti-peligrosos en 1 lectura (`LECTURAS = 1`):**
   - En modo de 1 lectura, los campos estructurados (`fecha`, `sangre`, `si_no`, `numero`), las listas vacías (`"Ninguna"`) y cualquier dato que coincida con el OCR o con la lista oficial quedan marcados con confianza segura (`44 %` solos y bien), mientras que nombres, correos, teléfonos, domicilios y alergias escritas a mano quedan por confirmar con 1 clic, manteniendo **0 peligrosos** y bajando el tiempo en frío por hoja de **98 s a 37 s (2.65x más rápido)**.

---

## 3. Resúmenes Completos por Etiqueta

### Etiqueta: `optimizado_1` (`resumen_lectura_optimizado_1.md`)

- **Tiempo en primera corrida sin caché de imagen:** `37 s` en promedio por hoja (`01_certificado_medico.jpg: 38 s`, `01_ficha_inscripcion.jpg: 40 s`, `02_certificado_medico.jpg: 32 s`, `02_ficha_inscripcion.jpg: 39 s`, `03_certificado_medico.jpg: 32 s`, `03_ficha_inscripcion.jpg: 42 s`).
- **Tiempo en segunda corrida (reutilizando caché de imagen en iGPU):** `15 s` en promedio por hoja.

# Medición de la lectura por campo (2026-10-15)

- Hojas: 6 · campos medidos: 72 · modelo que ve: qwen2.5vl:3b, 1 lectura(s) por hoja, imagen de 960 px
- Tiempo por hoja: 37 s en promedio sin caché / 15 s con caché
- **Bien (solo o con un clic): 93 %** · se llenaron solos y bien: 44 % · peligrosos: 0

#### Por tipo de hoja

| tipo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| certificado_medico | 27 | 17 | 10 | 0 | 0 | 0 | 100 % |
| ficha_inscripcion | 45 | 15 | 25 | 5 | 0 | 0 | 89 % |

#### Por tipo de campo

| tipo_campo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| correo | 3 | 0 | 1 | 2 | 0 | 0 | 33 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| fecha | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |
| lista | 9 | 7 | 1 | 1 | 0 | 0 | 89 % |
| nombre | 15 | 0 | 15 | 0 | 0 | 0 | 100 % |
| numero | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |
| sangre | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |
| si_no | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| telefono | 9 | 3 | 5 | 1 | 0 | 0 | 89 % |
| texto | 6 | 0 | 6 | 0 | 0 | 0 | 100 % |

#### Por letra

| letra | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| clara (Inkfree.ttf) | 24 | 10 | 14 | 0 | 0 | 0 | 100 % |
| clara (comic.ttf) | 24 | 9 | 11 | 4 | 0 | 0 | 83 % |
| clara (segoepr.ttf) | 24 | 13 | 10 | 1 | 0 | 0 | 96 % |

#### Por cómo se tomó la foto

| variante | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| derecha | 15 | 4 | 11 | 0 | 0 | 0 | 100 % |
| girada | 24 | 10 | 10 | 4 | 0 | 0 | 83 % |
| perspectiva | 24 | 13 | 10 | 1 | 0 | 0 | 96 % |
| sombra | 9 | 5 | 4 | 0 | 0 | 0 | 100 % |

#### Por campo

| clave | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| alergias | 6 | 4 | 1 | 1 | 0 | 0 | 83 % |
| apto | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| cedula | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| contacto_emergencia | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| correo | 3 | 0 | 1 | 2 | 0 | 0 | 33 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| enfermedades | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| fecha_certificado | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| fecha_nacimiento | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| medico | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_alumno | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_madre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_padre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| observaciones | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| peso | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| talla | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| telefono_emergencia | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_madre | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_padre | 3 | 1 | 1 | 1 | 0 | 0 | 67 % |
| tipo_sangre | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |

---

### Etiqueta: `sin_vision` (`resumen_lectura_sin_vision.md`)

# Medición de la lectura por campo (2026-10-15)

- Hojas: 24 · campos medidos: 288 · modelo que ve: ninguno (solo procesos)
- Tiempo por hoja: 1 s en promedio (modelo: 0 s)
- **Bien (solo o con un clic): 18 %** · se llenaron solos y bien: 0 % · peligrosos: 0

#### Por tipo de hoja

| tipo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| certificado_medico | 108 | 0 | 19 | 2 | 87 | 0 | 18 % |
| ficha_inscripcion | 180 | 0 | 32 | 6 | 142 | 0 | 18 % |

#### Por tipo de campo

| tipo_campo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| correo | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| cp | 12 | 0 | 4 | 2 | 6 | 0 | 33 % |
| curp | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| domicilio | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| fecha | 24 | 0 | 13 | 1 | 10 | 0 | 54 % |
| lista | 36 | 0 | 0 | 0 | 36 | 0 | 0 % |
| nombre | 60 | 0 | 0 | 0 | 60 | 0 | 0 % |
| numero | 24 | 0 | 0 | 0 | 24 | 0 | 0 % |
| sangre | 24 | 0 | 8 | 1 | 15 | 0 | 33 % |
| si_no | 12 | 0 | 11 | 1 | 0 | 0 | 92 % |
| telefono | 36 | 0 | 15 | 3 | 18 | 0 | 42 % |
| texto | 24 | 0 | 0 | 0 | 24 | 0 | 0 % |

#### Por letra

| letra | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| clara (Inkfree.ttf) | 48 | 0 | 6 | 2 | 40 | 0 | 12 % |
| clara (comic.ttf) | 48 | 0 | 12 | 0 | 36 | 0 | 25 % |
| clara (segoepr.ttf) | 48 | 0 | 13 | 1 | 34 | 0 | 27 % |
| fea (BRADHITC.TTF) | 48 | 0 | 5 | 1 | 42 | 0 | 10 % |
| fea (ITCKRIST.TTF) | 48 | 0 | 10 | 1 | 37 | 0 | 21 % |
| fea (segoesc.ttf) | 48 | 0 | 5 | 3 | 40 | 0 | 10 % |

#### Por cómo se tomó la foto

| variante | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| chica | 48 | 0 | 10 | 0 | 38 | 0 | 21 % |
| derecha | 48 | 0 | 6 | 2 | 40 | 0 | 12 % |
| escaneo | 48 | 0 | 5 | 1 | 42 | 0 | 10 % |
| girada | 48 | 0 | 13 | 0 | 35 | 0 | 27 % |
| perspectiva | 48 | 0 | 12 | 2 | 34 | 0 | 25 % |
| sombra | 48 | 0 | 5 | 3 | 40 | 0 | 10 % |

#### Por campo

| clave | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| alergias | 24 | 0 | 0 | 0 | 24 | 0 | 0 % |
| apto | 12 | 0 | 11 | 1 | 0 | 0 | 92 % |
| cedula | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| contacto_emergencia | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| correo | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| cp | 12 | 0 | 4 | 2 | 6 | 0 | 33 % |
| curp | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| domicilio | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| enfermedades | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| fecha_certificado | 12 | 0 | 8 | 1 | 3 | 0 | 67 % |
| fecha_nacimiento | 12 | 0 | 5 | 0 | 7 | 0 | 42 % |
| medico | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| nombre_alumno | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| nombre_madre | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| nombre_padre | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| observaciones | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| peso | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| talla | 12 | 0 | 0 | 0 | 12 | 0 | 0 % |
| telefono_emergencia | 12 | 0 | 7 | 2 | 3 | 0 | 58 % |
| telefono_madre | 12 | 0 | 4 | 1 | 7 | 0 | 33 % |
| telefono_padre | 12 | 0 | 4 | 0 | 8 | 0 | 33 % |
| tipo_sangre | 24 | 0 | 8 | 1 | 15 | 0 | 33 % |

---

### Etiqueta: `base6` (`resumen_lectura_base6.md`)

# Medición de la lectura por campo (2026-10-15)

- Hojas: 6 · campos medidos: 72 · modelo que ve: qwen2.5vl:3b, 2 lectura(s) por hoja, imagen de 1280 px
- Tiempo por hoja: 98 s en promedio (modelo: 97 s)
- **Bien (solo o con un clic): 99 %** · se llenaron solos y bien: 40 % · peligrosos: 0

#### Por tipo de hoja

| tipo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| certificado_medico | 27 | 13 | 14 | 0 | 0 | 0 | 100 % |
| ficha_inscripcion | 45 | 16 | 28 | 1 | 0 | 0 | 98 % |

#### Por tipo de campo

| tipo_campo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| correo | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| fecha | 6 | 5 | 1 | 0 | 0 | 0 | 100 % |
| lista | 9 | 7 | 2 | 0 | 0 | 0 | 100 % |
| nombre | 15 | 1 | 14 | 0 | 0 | 0 | 100 % |
| numero | 6 | 2 | 4 | 0 | 0 | 0 | 100 % |
| sangre | 6 | 4 | 2 | 0 | 0 | 0 | 100 % |
| si_no | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| telefono | 9 | 4 | 5 | 0 | 0 | 0 | 100 % |
| texto | 6 | 2 | 4 | 0 | 0 | 0 | 100 % |

#### Por letra

| letra | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| clara (Inkfree.ttf) | 24 | 13 | 11 | 0 | 0 | 0 | 100 % |
| clara (comic.ttf) | 24 | 6 | 18 | 0 | 0 | 0 | 100 % |
| clara (segoepr.ttf) | 24 | 10 | 13 | 1 | 0 | 0 | 96 % |

#### Por cómo se tomó la foto

| variante | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| derecha | 15 | 4 | 11 | 0 | 0 | 0 | 100 % |
| girada | 24 | 8 | 16 | 0 | 0 | 0 | 100 % |
| perspectiva | 24 | 16 | 7 | 1 | 0 | 0 | 96 % |
| sombra | 9 | 1 | 8 | 0 | 0 | 0 | 100 % |

#### Por campo

| clave | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| alergias | 6 | 4 | 2 | 0 | 0 | 0 | 100 % |
| apto | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| cedula | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| contacto_emergencia | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| correo | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| enfermedades | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| fecha_certificado | 3 | 2 | 1 | 0 | 0 | 0 | 100 % |
| fecha_nacimiento | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| medico | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| nombre_alumno | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_madre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_padre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| observaciones | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| peso | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| talla | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_emergencia | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_madre | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_padre | 3 | 2 | 1 | 0 | 0 | 0 | 100 % |
| tipo_sangre | 6 | 4 | 2 | 0 | 0 | 0 | 100 % |

---

### Etiqueta: `una_lectura` (`resumen_lectura_una_lectura.md`)

# Medición de la lectura por campo (2026-10-15)

- Hojas: 6 · campos medidos: 72 · modelo que ve: qwen2.5vl:3b, 1 lectura(s) por hoja, imagen de 1280 px
- Tiempo por hoja: 75 s en promedio (modelo: 74 s)
- **Bien (solo o con un clic): 97 %** · se llenaron solos y bien: 58 % · peligrosos: 0

#### Por tipo de hoja

| tipo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| certificado_medico | 27 | 26 | 0 | 0 | 1 | 0 | 96 % |
| ficha_inscripcion | 45 | 16 | 28 | 1 | 0 | 0 | 98 % |

#### Por tipo de campo

| tipo_campo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| correo | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| fecha | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |
| lista | 9 | 8 | 1 | 0 | 0 | 0 | 100 % |
| nombre | 15 | 3 | 12 | 0 | 0 | 0 | 100 % |
| numero | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |
| sangre | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |
| si_no | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| telefono | 9 | 4 | 5 | 0 | 0 | 0 | 100 % |
| texto | 6 | 5 | 0 | 0 | 1 | 0 | 83 % |

---

### Etiqueta: `lado960` (`resumen_lectura_lado960.md`)

# Medición de la lectura por campo (2026-10-15)

- Hojas: 6 · campos medidos: 72 · modelo que ve: qwen2.5vl:3b, 2 lectura(s) por hoja, imagen de 960 px
- Tiempo por hoja: 73 s en promedio (modelo: 72 s)
- **Bien (solo o con un clic): 94 %** · se llenaron solos y bien: 40 % · peligrosos: 0

#### Por tipo de hoja

| tipo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| certificado_medico | 27 | 13 | 13 | 1 | 0 | 0 | 96 % |
| ficha_inscripcion | 45 | 16 | 26 | 3 | 0 | 0 | 93 % |
