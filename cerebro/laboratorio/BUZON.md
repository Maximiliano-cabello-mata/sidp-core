# Buzón: tareas de Claude para el agente de la PC 4

Una tarea está hecha cuando su informe está en `resultados/`. Las reglas están en [LEEME.md](LEEME.md#cómo-se-comunican-claude-y-el-agente-de-la-pc-4).

## Tarea 001: crear el modelo y correr las fichas (2026-10-14)

1. En la carpeta del repositorio `sidp-core`, actualiza y cambia a la rama de trabajo:
   ```
   git fetch origin
   git checkout claude/project-thread-vp6ab8
   git pull
   ```
2. Crea el modelo con el Modelfile. `ollama` no está en el PATH, así que usa la ruta completa del ejecutable:
   ```
   & "<ruta>\ollama.exe" create sidp-revisor -f cerebro\laboratorio\Modelfile
   ```
   Comprueba que `sidp-revisor` aparece en `ollama list`.
3. Corre solo los procesos. Debe decir "11 de 11":
   ```
   python -m cerebro.laboratorio.correr --sin-modelo
   ```
4. Anota la RAM libre y corre con el modelo:
   ```
   python -m cerebro.laboratorio.correr
   ```
5. Al final del informe que quedó en `cerebro/laboratorio/resultados/`, agrega una sección "## Notas del agente" con:
   - la RAM libre antes y después;
   - si la PC se puso lenta;
   - cualquier error, completo.
6. Sube solo ese informe:
   ```
   git add cerebro/laboratorio/resultados/
   git commit -m "laboratorio: resultado de la tarea 001"
   git pull --rebase
   git push
   ```
7. Avísale a Maximiliano que ya se subió.
