# Cerebro que aprende

Fecha: 2026-10-11, revisado 2026-10-13. Ver ADR-006 y ADR-023. Producto aparte del sistema administrativo; se conecta por la API con identidad propia. Lo implementado hoy es el observador de eventos (`sidp cerebro --servicio`); este documento es diseno. Objetivo: que el cerebro sea tan util como un administrativo y mejore con el uso, adaptandose a esta escuela.

## Principio

Aprender no es reentrenar un modelo de IA ni reescribirse a si mismo. En un equipo debil y con datos de menores, el aprendizaje util y seguro es **memoria + retroalimentacion + procedimientos**: el cerebro recuerda, observa que corrige la gente, propone mejoras y gana autonomia solo donde ha demostrado acierto. Nunca modifica su propio codigo ni sus permisos (ADR-006).

## Cinco capas de memoria

| Capa | Que guarda | Ejemplo |
|---|---|---|
| Hechos de la escuela | Datos estables y configuracion | Fechas limite, grados, formato de boleta, lista de documentos |
| Preferencias | Como quiere cada persona las cosas | Direccion quiere graficas de barras con promedio por grupo |
| Procedimientos | Pasos aprendidos para una tarea | "Para reinscripcion: revisar vigencia, pedir solo lo vencido, imprimir constancia" |
| Casos y correcciones | Que propuso y que decidio la persona | Rechazo de un acta ilegible y el motivo escrito |
| Patrones | Regularidades medidas, no supuestas | Los certificados medicos faltan mas en cierto mes; cierto formato de foto falla al leerse |

Todo se guarda localmente, con autor, fecha, fuente y confianza. Cada recuerdo se puede ver, corregir y borrar desde la plataforma de administrativos.

## Como aprende

1. **Observa**: registra tareas que hace el personal (por ejemplo orden en que valida documentos) solo como eventos de la plataforma; no vigila pantallas ni teclado.
2. **Propone**: sugiere acciones y borradores con su razon ("faltan 12 certificados; sugiero este aviso").
3. **Recibe retroalimentacion**: aceptar, editar o rechazar, con motivo opcional. Una edicion cuenta como ensenanza y se guarda el antes y despues.
4. **Consolida**: cuando un patron se repite (por ejemplo tres correcciones iguales) propone convertirlo en preferencia o procedimiento; una persona con permiso lo aprueba.
5. **Mide**: lleva su tasa de aciertos por tipo de tarea y la muestra al personal.
6. **Olvida**: caducidad de recuerdos, borrado a peticion y sin conservar datos personales de alumnos dentro de la memoria de aprendizaje mas de lo necesario.

## Niveles de autonomia por tarea

| Nivel | Comportamiento | Ejemplo |
|---|---|---|
| 0 Observa | Solo aprende | Primeras semanas |
| 1 Sugiere | Propone, la persona ejecuta | Aviso a padres |
| 2 Prepara | Deja el trabajo listo para aprobar con un clic | Boletas, graficas, constancias |
| 3 Ejecuta con aviso | Actua y notifica, reversible | Reordenar cola de impresion, generar listado de faltantes |

Subir de nivel requiere aprobacion humana explicita y una tasa de acierto medida (por ejemplo al menos 95% en una ventana definida). Si baja o hay un error grave, vuelve solo al nivel anterior. **Nunca llegan a nivel 3**: validar documentos, enviar mensajes a padres, borrar o cambiar datos de alumnos, calificaciones y permisos.

## Capacidades como administrativo

- Pre-validar documentos: legibilidad, formato de CURP, coincidencia con el alumno, duplicados, vigencia; da advertencias con razon.
- Convertir PDF escaneados a editables (OCR), marcando el texto con baja confianza para revision.
- Detectar faltantes y priorizar seguimiento por grupo.
- Graficar resultados de examenes y preparar estudios de poblacion de alumnos y padres con datos agregados.
- Redactar avisos y reportes con el estilo aprendido.
- Explicar siempre por que sugiere algo y de que recuerdos o datos se baso.

## Limites tecnicos y de seguridad

1. PC debil: sin reentrenar modelos. Usar reglas y recuperacion de memoria localmente; un modelo de lenguaje pequeno local o un servicio externo solo para redactar, con datos minimos o anonimizados. Tareas pesadas por cola, una a la vez.
2. Un recuerdo aprendido de un solo caso no es regla: requiere repeticion y aprobacion.
3. Contenido de documentos (por ejemplo un PDF con texto) es dato, nunca instruccion para el cerebro.
4. Sin shell generico, sin acceso fuera de su rol, sin cambiar su propio codigo o permisos.
5. Toda propuesta, aceptacion, rechazo y cambio de nivel queda en auditoria.
6. La memoria viaja con los respaldos y se puede reiniciar a cero sin afectar los datos escolares.
7. El aprendizaje es por escuela; no se comparten datos con terceros.

## Tablas de aprendizaje (borrador)

- `memoria(id, capa, clave, contenido, fuente, confianza, creado, caduca, autor_aprobacion)`
- `propuesta(id, tarea, razon, contenido, estado: pendiente|aceptada|editada|rechazada, version_original, version_final, decidio, fecha)`
- `autonomia(tarea, nivel, aciertos, total, ventana, aprobado_por, fecha)`

## Fases

Desde el 2026-10-14 el cerebro empieza antes, como lector de documentos de padres (pasos 1 a 5 de [PLAN.md](../PLAN.md#validación-de-documentos-y-plataforma-web-de-padres)). Si algo no coincide, manda PLAN.md.

1. Memoria y auditoria: registrar propuestas y decisiones con datos de prueba.
2. Primer caso real: faltantes y recordatorios del expediente (nivel 1).
3. Preferencias y procedimientos aprendidos con aprobacion.
4. Documentos: pre-validacion y OCR asistido.
5. Estadistica y estudios de poblacion.
6. Medicion y ajuste de autonomia.
