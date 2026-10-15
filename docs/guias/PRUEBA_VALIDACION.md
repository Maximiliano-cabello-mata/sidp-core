# Prueba oficial del validador de expedientes

Mide qué tan bien el validador separa expedientes verdaderos de falsos, con documentos reales mezclados con documentos alterados. Corre completo en la PC 4, sin servidor y sin internet.

## Regla de privacidad

Los documentos reales son de menores y de sus familias:

1. Solo se usan documentos de personas que dieron permiso.
2. La carpeta de la prueba va **fuera** del repositorio, por ejemplo `C:\SIDP-prueba`. Si tiene PDF o fotos y está dentro de un repositorio, el validador se niega a correr.
3. `informe_local.html` y `resultados_local.json` tienen nombres y CURP: se quedan en la PC 4.
4. Al repositorio solo se sube `resumen_para_repo.md`, que trae números y claves de reglas, sin nombres, CURP, domicilios ni nombres de carpetas.

## Cómo se arma la carpeta

```
C:\SIDP-prueba\
  etiquetas.csv
  expedientes\
    001\
      captura.json
      acta_alumno.pdf
      certificado_medico.jpg
      boleta.pdf              (opcional)
      ine_tutor_frente.jpg
      ine_tutor_reverso.jpg
      acta_tutor.pdf          (opcional)
      comprobante.pdf
    002\
      ...
```

- Las carpetas se nombran con números (`001`, `002`...), nunca con el nombre del alumno.
- Cada archivo empieza con el tipo de documento. Un tipo puede tener varios archivos: frente y reverso.
- `captura.json` es lo que el padre escribiría en la plataforma:

```json
{
 "alumno": {"nombre": "LUIS HERNANDEZ RAMOS", "curp": "HERL180314HMCRMSA9"},
 "tutor": {"nombre": "MARIA ELENA RAMOS SOTO", "parentesco": "madre", "domicilio": "Calle Pino 5, Col. Centro, Toluca"}
}
```

El parentesco puede ser madre, padre, tutor_legal, abuelo u otro. El domicilio se escribe como viene en el comprobante (calle, número, colonia y municipio) y sin código postal.

## Cómo se hacen los falsos

Copia un expediente verdadero y cámbiale una sola cosa. Anótala en `etiquetas.csv`:

```
expediente,es_falso,trampa
001,no,
002,si,fecha
003,si,comprobante_viejo
```

Trampas que se pueden anotar: `nombre`, `curp`, `fecha`, `sexo`, `tutor`, `domicilio`, `comprobante_viejo`, `otro_documento`, `falta_documento`, `foto_mala`, `texto_oculto`, `otra`.

Ejemplos de trampas:

- Capturar la CURP con un dígito cambiado.
- Usar la INE de otra persona.
- Poner un comprobante de hace 5 meses.
- Escribir otro número de casa.
- Subir una boleta en el lugar del certificado médico.
- Tomar una foto borrosa.

Para que la medida sirva, que sean por lo menos 20 expedientes, la mitad falsos.

## Cómo se corre

Desde la carpeta del repositorio, en la PC 4:

1. Comprueba primero con el ejemplo inventado. Debe decir "Falsos que pasaron como listos (peligroso): 0 de 6":
   ```
   python -m validacion.prueba validacion\ejemplo --hoy 2026-10-14 --sin-modelo
   ```
2. Corre la prueba oficial, con el modelo `sidp-revisor-2` opinando en la zona gris:
   ```
   python -m validacion.prueba C:\SIDP-prueba
   ```
3. Abre `C:\SIDP-prueba\informe_local.html` en el navegador para ver cada expediente.
4. Copia `C:\SIDP-prueba\resumen_para_repo.md` a `cerebro\laboratorio\resultados\` con la fecha en el nombre (`2026-10-20_prueba_oficial.md`) y súbelo.

## Qué se mide

| Medida | Qué significa | Meta |
|---|---|---|
| Falsos que pasaron como listos | Un falso que el administrador podría autorizar sin ver la alerta | 0 |
| Falsos detectados | Falsos enviados a revisión manual | Todos |
| Falsas alarmas | Verdaderos enviados a revisión sin necesidad | Pocas: cada una es trabajo para el administrador |
| No se pudo leer | Documentos que el lector no leyó (foto mala, falta una herramienta) | Pocos |

El modelo nunca cambia el estado de un expediente; su opinión solo aparece en el informe. La prueba también cuenta cuántas veces dijo "si" en un expediente falso.

## Herramientas del lector

El validador lee `.pdf`, `.jpg`, `.png` y `.txt`. Para PDF y fotos necesita programas que se instalan **solo con permiso de Maximiliano** (`validacion/requisitos.txt`):

- `pypdf`: el texto de los PDF.
- `opencv-python-headless`: el QR y qué tan nítida está la foto.
- Tesseract con idioma español: el texto de las fotos. Se comprueba con `tesseract --list-langs`, que debe mostrar `spa`.

Si falta alguno, esos documentos quedan como "no se pudo leer" y el informe dice qué falta.
