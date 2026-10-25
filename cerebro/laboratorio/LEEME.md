# Laboratorio del cerebro

Aquí se prueba, con datos inventados, cómo el cerebro de la PC 4 ayuda a validar documentos de inscripción. Es una prueba: todavía no se conecta a la plataforma ni ve documentos reales.

## Cómo se valida

1. **Procesos fijos, sin IA** ([`validacion/comparador.py`](../../validacion/comparador.py)). Comparan los datos que los lectores (QR, texto del PDF, OCR) sacaron de cada documento:
   - la CURP: formato, dígito verificador, fecha y sexo contra el acta;
   - el tutor: debe aparecer como padre o madre en el acta y coincidir con su INE;
   - el comprobante: tener 3 meses o menos y el mismo domicilio;
   - textos que parecen órdenes escondidas.

   Antes de comparar, quitan acentos y signos y expanden abreviaturas (Ma., Av., Col.). Un número de casa distinto siempre es otro domicilio.
2. **Zona gris.** Cuando dos nombres o domicilios se parecen pero no son iguales, el proceso no decide. Si en un nombre falta o sobra una palabra, las palabras están en otro orden o una cambia más de una letra, queda en "duda" sin preguntar al modelo: en la tarea 002 el modelo se equivocó justo en esos casos.
3. **El modelo opina solo sobre el resto de la zona gris** ([`validacion/modelo.py`](../../validacion/modelo.py)). Recibe dos textos y dice "si", "no" o "duda", sin ver el documento ni la ficha completa. Si no responde, la respuesta es "duda".
4. **Decide una persona.** Lo que tenga un hallazgo o una zona gris pasa a revisión manual. Lo demás queda "listo para autorizar" y el administrador lo aprueba. El modelo nunca quita una alerta.

La primera prueba (2026-10-14) mostró que `llama3.1` revisando la ficha completa inventa diferencias. Por eso aquí solo opina sobre dos textos y se mide si acierta.

## Archivos

| Archivo | Qué es |
|---|---|
| [`validacion/comparador.py`](../../validacion/comparador.py) | Los procesos fijos (los mismos que usa el validador) |
| [`validacion/modelo.py`](../../validacion/modelo.py) | La llamada a Ollama en `127.0.0.1:11434`; usa `sidp-revisor-2` |
| `Modelfile` | Crea el modelo `sidp-revisor` a partir de `llama3.1:latest`, sin descargar nada |
| `Modelfile.2` | Crea `sidp-revisor-2`: las mismas reglas, más precisas y con ejemplos |
| `fichas.json` | Fichas inventadas con el resultado esperado |
| `pares.json` | 30 pares de nombres y domicilios en zona gris, con la respuesta aceptable; del 19 al 30 son nuevos y no se usaron para ajustar |
| `correr.py` | Corre las fichas y guarda el informe en `resultados/` |
| `BUZON.md` | Tareas de Claude para el agente de la PC 4 |
| `resultados/` | Lo que el agente sube |

## Cómo se comunican Claude y el agente de la PC 4

El canal es este repositorio, en la rama `claude/project-thread-vp6ab8`:

1. Claude escribe una tarea nueva en `BUZON.md` y la sube.
2. El agente actualiza la rama, hace la tarea y deja el informe en `resultados/`.
3. El agente sube solo ese informe y le avisa a Maximiliano.
4. Maximiliano le escribe a Claude en el hilo de SIDP ("ya subió") y Claude lee el informe de la rama.

La primera vez que el agente sube desde una PC, configura su nombre y correo de Git solo para este repositorio (`git config user.name` y `git config user.email`).

Reglas para el agente:

1. Solo agrega archivos en `cerebro/laboratorio/resultados/`. No cambia ningún otro archivo.
2. Usa solo los datos de `fichas.json`. Nunca datos ni documentos reales, ni la clave de la escuela. Un Excel "de ejemplo" copiado de un archivo de la escuela sigue trayendo filas reales: los ejemplos se hacen desde cero con datos inventados. Antes de subir, revisa que no haya ninguna CURP, teléfono, domicilio ni la clave de la escuela (tampoco en el mensaje del commit). El repositorio es público.
3. Ollama sigue solo en `127.0.0.1`.
4. No descarga modelos ni instala programas sin permiso de Maximiliano.
5. Antes de subir, hace `git pull --rebase`. Si algo falla, lo anota en el informe y avisa a Maximiliano.
