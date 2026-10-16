# Resultado de la Tarea 013: código nuevo del escaneo, modelo que ve más rápido y medición de la letra a mano (PC 4)

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
Ajustes (C:\SIDP-datos\servicios\ajustes.ps1): OLLAMA_IGPU_ENABLE = '1'; OLLAMA_FLASH_ATTENTION = '1'; OLLAMA_KEEP_ALIVE = '24h'; SIDP_MODELO_VISION = 'qwen2.5vl:3b'; SIDP_LADO_VISION = '1280'; SIDP_LECTURAS_VISION = '2'
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

- Al arrancar `SIDP-Cerebro`, la base migró automáticamente a **`esquema: 3`**, conservando íntegros los 191 alumnos.
- Al reiniciar `SIDP-Ollama` con `OLLAMA_IGPU_ENABLE = '1'` en `ajustes.ps1`, Ollama detectó y activó la **iGPU AMD Radeon(TM) Graphics por Vulkan (`11.9 GiB` VRAM total, `11.3 GiB` disponibles)**.

---

## 2. Tabla Comparativa Rápida de Mediciones

| Etiqueta | Hojas | Campos | Configuración | Tiempo / hoja | Bien (solo o 1 clic) | Solos y bien | Peligrosos |
| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **`sin_vision`** | 24 | 288 | Solo procesos fijos (OCR + reglas) | **1 s** | **18 %** | 0 % | **0** |
| **`base6`** | 6 | 72 | `qwen2.5vl:3b`, 2 lecturas, `1280 px` | **98 s** | **99 %** | 40 % | **0** |
| **`una_lectura`** | 6 | 72 | `qwen2.5vl:3b`, 1 lectura, `1280 px` | **75 s** | **97 %** | 58 % | **0** |
| **`lado960`** | 6 | 72 | `qwen2.5vl:3b`, 2 lecturas, `960 px` | **73 s** | **94 %** | 40 % | **0** |

---

## 3. Resúmenes Completos por Etiqueta

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

#### Por letra

| letra | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| clara (Inkfree.ttf) | 24 | 13 | 11 | 0 | 0 | 0 | 100 % |
| clara (comic.ttf) | 24 | 14 | 10 | 0 | 0 | 0 | 100 % |
| clara (segoepr.ttf) | 24 | 15 | 7 | 1 | 1 | 0 | 92 % |

#### Por cómo se tomó la foto

| variante | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| derecha | 15 | 4 | 11 | 0 | 0 | 0 | 100 % |
| girada | 24 | 13 | 10 | 0 | 1 | 0 | 96 % |
| perspectiva | 24 | 16 | 7 | 1 | 0 | 0 | 96 % |
| sombra | 9 | 9 | 0 | 0 | 0 | 0 | 100 % |

#### Por campo

| clave | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| alergias | 6 | 5 | 1 | 0 | 0 | 0 | 100 % |
| apto | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| cedula | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| contacto_emergencia | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| correo | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| enfermedades | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| fecha_certificado | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| fecha_nacimiento | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| medico | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| nombre_alumno | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_madre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_padre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| observaciones | 3 | 2 | 0 | 0 | 1 | 0 | 67 % |
| peso | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| talla | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| telefono_emergencia | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_madre | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_padre | 3 | 2 | 1 | 0 | 0 | 0 | 100 % |
| tipo_sangre | 6 | 6 | 0 | 0 | 0 | 0 | 100 % |

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

#### Por tipo de campo

| tipo_campo | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| correo | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| fecha | 6 | 5 | 1 | 0 | 0 | 0 | 100 % |
| lista | 9 | 7 | 1 | 1 | 0 | 0 | 89 % |
| nombre | 15 | 1 | 14 | 0 | 0 | 0 | 100 % |
| numero | 6 | 2 | 4 | 0 | 0 | 0 | 100 % |
| sangre | 6 | 4 | 2 | 0 | 0 | 0 | 100 % |
| si_no | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| telefono | 9 | 4 | 5 | 0 | 0 | 0 | 100 % |
| texto | 6 | 2 | 3 | 1 | 0 | 0 | 83 % |

#### Por letra

| letra | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| clara (Inkfree.ttf) | 24 | 13 | 11 | 0 | 0 | 0 | 100 % |
| clara (comic.ttf) | 24 | 6 | 16 | 2 | 0 | 0 | 92 % |
| clara (segoepr.ttf) | 24 | 10 | 12 | 2 | 0 | 0 | 92 % |

#### Por cómo se tomó la foto

| variante | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| derecha | 15 | 4 | 11 | 0 | 0 | 0 | 100 % |
| girada | 24 | 8 | 13 | 3 | 0 | 0 | 88 % |
| perspectiva | 24 | 16 | 7 | 1 | 0 | 0 | 96 % |
| sombra | 9 | 1 | 8 | 0 | 0 | 0 | 100 % |

#### Por campo

| clave | Campos | Bien y solo | Bien, un clic | Leído mal (por confirmar) | No se leyó | PELIGROSO: mal y marcado seguro | Bien (meta 80 %) |
|---|---|---|---|---|---|---|---|
| alergias | 6 | 4 | 1 | 1 | 0 | 0 | 83 % |
| apto | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| cedula | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| contacto_emergencia | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| correo | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| cp | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| curp | 3 | 0 | 2 | 1 | 0 | 0 | 67 % |
| domicilio | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| enfermedades | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| fecha_certificado | 3 | 2 | 1 | 0 | 0 | 0 | 100 % |
| fecha_nacimiento | 3 | 3 | 0 | 0 | 0 | 0 | 100 % |
| medico | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| nombre_alumno | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_madre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| nombre_padre | 3 | 0 | 3 | 0 | 0 | 0 | 100 % |
| observaciones | 3 | 1 | 1 | 1 | 0 | 0 | 67 % |
| peso | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| talla | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_emergencia | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_madre | 3 | 1 | 2 | 0 | 0 | 0 | 100 % |
| telefono_padre | 3 | 2 | 1 | 0 | 0 | 0 | 100 % |
| tipo_sangre | 6 | 4 | 2 | 0 | 0 | 0 | 100 % |

---

## 4. Hallazgos Técnicos y Notas para Claude

1. **Aceleración por iGPU Vulkan activa y reutilización de caché visual (LCP):**
   - Al cargar `OLLAMA_IGPU_ENABLE = '1'` desde `C:\SIDP-datos\servicios\ajustes.ps1`, Ollama 0.40.4 habilitó `Vulkan0 (AMD Radeon(TM) Graphics, 11.9 GiB)`.
   - La primera lectura de una hoja de `1280 px` (~1,940 tokens) tarda ~58 s (`prompt eval time = 39.2 s` + `eval time = 19.6 s` a `14.1 tokens/s`).
   - En la **segunda lectura** de la misma hoja (con el orden de campos invertido), Ollama detecta similitud LCP de `0.893 (1732/1940 tokens)` y **reutiliza el caché de la imagen**, evaluando el prompt en solo **2.67 segundos** (`2674 ms / 231 tokens`) más ~26 s de generación JSON (~29.4 s en total para la segunda lectura).
2. **Por qué `una_lectura` (`1280 px`, 1 lectura) y `base6` (`1280 px`, 2 lecturas) superan ampliamente la meta del 80 %:**
   - `base6` logró **99 % bien (71 de 72 campos)** con **0 peligrosos** en `98 s/hoja`.
   - `una_lectura` logró **97 % bien (70 de 72 campos)**, subiendo los campos "bien y solo" de `40 %` a **`58 %`** con **0 peligrosos** en `75 s/hoja`.
   - `lado960` logró **94 % bien (68 de 72 campos)** con **0 peligrosos** en `73 s/hoja` (pierde ligeramente precisión en `curp` y `alergias` cuando la hoja viene girada).
3. **Nota de implementación en `instalar_servicios.ps1`:**
   - Cuando `SIDP-Ollama` y `SIDP-Cerebro` corren como tareas programadas `S4U` (en `SessionId 0`), sus procesos hijos (`ollama.exe` y `python.exe` lanzados con `Start-Process`) siguen vivos si solo se ejecuta `Stop-ScheduledTask`. Para que `instalar_servicios.ps1` pueda reiniciarlos limpiamente sin dejar un `ollama.exe` anterior ocupando el puerto `11434`, conviene usar `taskkill /F /IM ollama.exe /T` o detener el árbol de procesos antes de `Start-ScheduledTask`.
4. **Comparaciones pendientes para corrida nocturna:**
   - Por la hora local (`22:32`), se suben de inmediato `sin_vision` (24 hojas) y las tres comparaciones clave de 6 hojas (`base6`, `una_lectura` y `lado960`), quedando pendientes para corrida extendida `taller` (las 18 hojas restantes de las 24), `lado1600` y `qwen3_8b`.
