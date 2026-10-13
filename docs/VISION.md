# Visión de SIDP

Fecha: 2026-10-13. Resume las ideas acordadas con el dueño del proyecto. **El alcance queda cerrado aquí:** cualquier idea nueva espera a que termine el piloto. El orden de construcción está en [PLAN.md](PLAN.md).

## La idea

SIDP es el sistema escolar completo de la primaria, alojado en las computadoras que la escuela ya tiene. Administrativos, profesores y padres trabajan sobre una sola plataforma, y una IA en una computadora aparte quita trabajo manual al personal.

El problema que resuelve: el personal pierde horas capturando, buscando, llenando formatos y revisando documentos a mano, y la escuela no tiene presupuesto ni técnico. Los expedientes de toda la escuela caben en un disco normal (unos 75 GB en el peor caso con 500 alumnos, unos 5 GB comprimiendo al subir), así que el reto no es el espacio sino que los datos no se pierdan y el sistema no se caiga.

## Las piezas

| Pieza | Qué es | Dónde corre |
|---|---|---|
| Servidor | La única plataforma: base de datos, archivos y páginas | Una PC de la escuela, siempre encendida en horario escolar, por cable al módem, con no-break y disco externo. Puede seguir usándose para trabajo administrativo |
| Demás PCs | Se unen solas con `sidp.exe` y la clave de escuela; guardan una copia y ayudan con tareas pesadas (PDF, compresión) | Cualquier PC de la red escolar |
| Cerebro (IA) | Ayudante: valida documentos, redacta borradores, propone campos de formatos, analiza datos | PC 4 dedicada (Ryzen 5, 24 GB, disco mecánico de 128 GB solo para temporales). No aloja la plataforma |
| Buzón de padres | Página en internet donde los padres suben documentos | Hosting en la nube. El servidor descarga lo nuevo; no se abre el módem |

Principios:

1. **Una sola plataforma, un solo servidor** (ADR-019, ADR-027). Las demás PCs protegen los datos con copias; no guardan pedazos de ellos.
2. **Crecer solo con el `.exe`** (ADR-025). Una PC nueva copia `sidp.exe`, escribe la clave y queda unida, con copia y como ayudante. Nadie tiene que ir a configurarla.
3. **Todo funciona sin el cerebro** (ADR-023). La IA prepara; una persona decide. Nunca aprueba, firma ni envía nada por sí sola.
4. **Los padres no entran a la red de la escuela.** Solo tocan el buzón (ADR-028).

## Quién la usa

| Usuario | Entra desde | Hace |
|---|---|---|
| Administrativos | Navegador en la red escolar | Expedientes, formatos, documentos, inventario, asistencia de profesores, revisar lo que preparó la IA, reportes |
| Profesores | Navegador o celular en la red escolar | Pase de lista, calificaciones, exámenes diagnósticos, consultas de sus grupos |
| Padres | Buzón en internet | Subir documentos de sus hijos, ver qué falta y qué se aceptó, actualizar contacto, leer avisos |

## Qué hace (alcance cerrado)

| Módulo | Qué se hace, a mano y sin IA |
|---|---|
| Expediente del alumno | Datos, grupo, historial, documentos, fotos y PDF en una pantalla |
| Expediente del tutor | Contacto, identificación, domicilio, hijos ligados |
| Búsqueda | Por nombre, CURP, grupo o tipo de documento |
| Inscripción y grupos | Alta, baja, cambio de grupo, ciclos escolares |
| Calificaciones y boletas | Captura por profesor, consulta, boletas |
| Asistencia | De alumnos (diaria) y de profesores (entrada, salida, permisos) |
| Exámenes diagnósticos | Resultados por alumno y grupo |
| Inventario | Mobiliario, cómputo y material, con ubicación y estado |
| Catálogo de formatos | Llenar con un clic cualquier formato de la escuela o del Gobierno del Estado de México con sus datos |
| Documentos PDF | Ver, unir, separar, rotar y llenar |
| Escaneo | El escáner guarda en una carpeta y la plataforma lo lleva al expediente |
| Impresión | Mandar a imprimir a la impresora de cualquier PC unida |
| Avisos | Mensajes a padres y profesores |

Además, indispensables para operar: **carga inicial desde Excel**, **bitácora de cambios** (quién cambió qué y cuándo), **exportar todo** (carpetas y Excel), **prueba mensual del respaldo**, **cierre de ciclo** sin borrar historial y **pantalla de salud** (servidor, última copia, espacio libre).

### Catálogo de formatos

Es la pieza que más tiempo ahorra y funciona sin IA.

1. Se sube el original una vez (Word, Excel o PDF).
2. Se marcan sus campos: nombre, CURP, grupo, fecha, director. Con el cerebro, la IA los propone y una persona confirma.
3. Se llena para un alumno, un grupo o toda la escuela; el resultado se puede editar antes de imprimir o archivar.
4. Si el gobierno cambia el formato, se sube la versión nueva; las anteriores se conservan.

Un PDF oficial cerrado solo se llena encima de sus espacios; los de Word y Excel se modifican libremente. Primer paso, sin código: reunir una copia de cada formato que manejan los administrativos.

### Cerebro

Valida documentos de padres (datos que no coinciden, fotos ilegibles, hojas faltantes), redacta borradores con plantillas, llena formatos, propone campos y analiza faltas y promedios. No se reentrena: mejora con plantillas, ejemplos y las correcciones del personal. En la PC 4, sin tarjeta gráfica, trabaja en segundo plano (por ejemplo, revisar de noche lo que subieron los padres), no al instante. Opción recomendada, por confirmar: mixta (lo privado y sencillo local, lo difícil en la nube sin datos personales). Detalle en [cerebro_aprendizaje.md](arquitectura/cerebro_aprendizaje.md).

### Buzón de padres

| Hace | No hace |
|---|---|
| Cuenta con el folio que da la escuela y la CURP del alumno | No muestra datos de otras familias |
| Lista de documentos que faltan | No guarda documentos para siempre: se borran al confirmar que la escuela los tiene |
| Recibe fotos y PDF desde el celular | No decide si un documento se acepta |
| Estado de cada documento: recibido, aceptado o rechazado con motivo | No cambia calificaciones, asistencia ni datos escolares |
| Actualizar teléfono, correo y domicilio | No se conecta al cerebro ni a la red escolar |
| Avisos de la escuela | No cobra pagos |

Mostrar calificaciones a los padres se decide después del piloto.

## Qué no hace

- Juntar varias PCs como una sola computadora (descartado: frágil y sin necesidad).
- Comprobar que un documento es auténtico; eso lo decide una persona.
- Enviar a los sistemas de la SEP por sí solo; solo exporta en el formato que pidan.
- Ser otro Word: para redactar libremente se abre el archivo en Word y se vuelve a subir.
- Administrar impresoras (colas, tinta, controladores) o escáneres.
- Guardar video.

## Riesgos conocidos

| Riesgo | Respuesta |
|---|---|
| Demasiados módulos para terminar | Alcance cerrado y fases que sirven solas |
| El servidor se apaga o falla | No-break, copias en otra PC y disco externo; en el futuro otra PC toma su lugar |
| Windows avisa "Windows protegió su PC" (exe sin firma) | "Más información" y "Ejecutar de todas formas"; quitarlo requiere certificado de pago |
| Antivirus bloquea el `.exe` | Permitirlo una vez en cada PC |
| Alguien que sabe la clave deja la escuela | Cambio de clave (pendiente, antes de datos reales) |
| Wi-Fi escolar aísla a las PCs | Prueba en la escuela primero; unir por IP si hace falta |
| Datos personales de menores | Cuentas por persona, aviso de privacidad antes del buzón, HTTPS, respaldo |
| El proyecto depende de una persona | Documentación suficiente para que otro lo mantenga |

## Decisiones pendientes

1. IA local, en la nube o mixta (recomendada: mixta).
2. Confirmar el buzón de padres en un hosting y quién paga la mensualidad.
3. Número de alumnos y de PCs, y disco libre de cada una.
