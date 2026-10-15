# Resultados del laboratorio: zona gris

- Fecha: 2026-10-14 18:07
- Equipo: DESKTOP-8RJIA6B
- Sistema: Windows-11-10.0.22000-SP0
- Procesador: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD
- Python: 3.15.0
- Modelo: sidp-revisor
- Ollama: 0.40.4

## Resumen

- Pares en zona gris según los procesos: 18 de 18.
- Opiniones acertadas: 27 de 54; 12 dijeron "si" cuando era "no".
- Tiempo por opinión: promedio 6.0 s, máximo 15.4 s.

## Pares

| Par | Tipo | Texto A | Texto B | Esperado | Opiniones |
|---|---|---|---|---|---|
| 1 | nombre | JOSE LUIS PERES ORTEGA | JOSE LUIS PEREZ ORTEGA | si | no, no, no |
| 2 | nombre | MARIA DE LOURDES SANCHEZ RUIZ | Ma. de Lourdes Sanches Ruiz | si | si, si, si |
| 3 | nombre | JUAN CARLOS LOPEZ | JUAN CARLOS LOPEZ HERNANDEZ | no/duda | no, no, no |
| 4 | nombre | LUIS FERNANDO DIAZ CRUZ | LUIS FERNANDO DIAS CRUZ | si | no, no, no |
| 5 | nombre | ROBERTO MENDOZA ROJAS | ROBERTA MENDOZA ROJAS | no/duda | no, no, no |
| 6 | nombre | DANIEL TORRES ARIAS | DANIELA TORRES ARIAS | no/duda | no, no, no |
| 7 | nombre | CARMEN VELAZQUEZ PAZ | CARMEN VELASQUEZ PAZ | si | no, no, no |
| 8 | nombre | PEDRO SOTO REYES | PEDRO SOTO REYNA | no/duda | no, no, no |
| 9 | nombre | JESUS ALEJANDRO NUÑEZ | JESUS ALEJANDRO NUNES | si | no, no, no |
| 10 | nombre | MARIA JOSE CASTILLO | JOSE MARIA CASTILLO | no/duda | si, si, si |
| 11 | nombre | GERARDO IBARRA SOLIS | GERARDO YBARRA SOLIS | si/duda | no, no, no |
| 12 | nombre | ALEJANDRA RIOS | ALEJANDRA RIOS VARGAS | no/duda | no, no, no |
| 13 | domicilio | Calle Fresno 9, Col. Las Flores, Zinacantepec | CALLE FRESNO 9 FRACC LAS FLORES ZINACANTEPEC | si/duda | si, si, si |
| 14 | domicilio | Calle Roble 22, Col. Centro, Toluca | CALLE ROBLE 22 COL CENTRO METEPEC | no/duda | si, si, si |
| 15 | domicilio | Privada Juárez 3, Barrio Santa Cruz, Lerma | PRIV JUAREZ 3 STA CRUZ LERMA | si | si, si, si |
| 16 | domicilio | Calle Sauce 30, San Mateo Atenco | CALLE SAUCE 30 SAN PEDRO ATENCO | no/duda | si, si, si |
| 17 | domicilio | Calle Cedro 11, Col. La Joya, Toluca | CALLE CEDRO 11 COL LA LOMA TOLUCA | no/duda | si, si, si |
| 18 | domicilio | Calle Pino 5, Col. Centro, Toluca | C. PINO NO. 5 CENTRO TOLUCA DE LERDO | si | si, si, si |

## Detalle

```json
[
 {
  "id": 1,
  "tipo": "nombre",
  "a": "JOSE LUIS PERES ORTEGA",
  "b": "JOSE LUIS PEREZ ORTEGA",
  "esperado": [
   "si"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 15.4
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 4.6
   }
  ],
  "aciertos": 0,
  "peligrosas": 0
 },
 {
  "id": 2,
  "tipo": "nombre",
  "a": "MARIA DE LOURDES SANCHEZ RUIZ",
  "b": "Ma. de Lourdes Sanches Ruiz",
  "esperado": [
   "si"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Acentos y mayúsculas no son distintos",
    "segundos": 6.4
   },
   {
    "misma": "si",
    "motivo": "Acentos y mayúsculas no son distintos",
    "segundos": 5.7
   },
   {
    "misma": "si",
    "motivo": "Acentos y mayúsculas no son distintos",
    "segundos": 5.8
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 3,
  "tipo": "nombre",
  "a": "JUAN CARLOS LOPEZ",
  "b": "JUAN CARLOS LOPEZ HERNANDEZ",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Apellido adicional",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Apellido adicional",
    "segundos": 4.0
   },
   {
    "misma": "no",
    "motivo": "Apellido adicional",
    "segundos": 4.1
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 4,
  "tipo": "nombre",
  "a": "LUIS FERNANDO DIAZ CRUZ",
  "b": "LUIS FERNANDO DIAS CRUZ",
  "esperado": [
   "si"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 5.2
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un solo apellido",
    "segundos": 4.8
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un solo apellido",
    "segundos": 4.8
   }
  ],
  "aciertos": 0,
  "peligrosas": 0
 },
 {
  "id": 5,
  "tipo": "nombre",
  "a": "ROBERTO MENDOZA ROJAS",
  "b": "ROBERTA MENDOZA ROJAS",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en el nombre",
    "segundos": 5.2
   },
   {
    "misma": "no",
    "motivo": "Diferencia en el nombre",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Diferencia en el nombre",
    "segundos": 4.6
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 6,
  "tipo": "nombre",
  "a": "DANIEL TORRES ARIAS",
  "b": "DANIELA TORRES ARIAS",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en el nombre",
    "segundos": 5.1
   },
   {
    "misma": "no",
    "motivo": "Diferencia en el nombre",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Diferencia en el nombre",
    "segundos": 4.6
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 7,
  "tipo": "nombre",
  "a": "CARMEN VELAZQUEZ PAZ",
  "b": "CARMEN VELASQUEZ PAZ",
  "esperado": [
   "si"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 5.2
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 4.6
   }
  ],
  "aciertos": 0,
  "peligrosas": 0
 },
 {
  "id": 8,
  "tipo": "nombre",
  "a": "PEDRO SOTO REYES",
  "b": "PEDRO SOTO REYNA",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en el apellido",
    "segundos": 5.0
   },
   {
    "misma": "no",
    "motivo": "Diferencia en el apellido",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Diferencia en el apellido",
    "segundos": 4.6
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 9,
  "tipo": "nombre",
  "a": "JESUS ALEJANDRO NUÑEZ",
  "b": "JESUS ALEJANDRO NUNES",
  "esperado": [
   "si"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 5.3
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un apellido",
    "segundos": 4.6
   }
  ],
  "aciertos": 0,
  "peligrosas": 0
 },
 {
  "id": 10,
  "tipo": "nombre",
  "a": "MARIA JOSE CASTILLO",
  "b": "JOSE MARIA CASTILLO",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Los apellidos están en el mismo orden y solo hay un cambio en la posición de los nombres",
    "segundos": 7.5
   },
   {
    "misma": "si",
    "motivo": "Los apellidos están en el mismo orden, solo la posición de los nombres es diferente",
    "segundos": 6.7
   },
   {
    "misma": "si",
    "motivo": "Los apellidos están en el mismo orden, solo la posición de los nombres es diferente",
    "segundos": 6.7
   }
  ],
  "aciertos": 0,
  "peligrosas": 3
 },
 {
  "id": 11,
  "tipo": "nombre",
  "a": "GERARDO IBARRA SOLIS",
  "b": "GERARDO YBARRA SOLIS",
  "esperado": [
   "si",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Diferencia en un solo apellido",
    "segundos": 5.4
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un solo apellido",
    "segundos": 4.8
   },
   {
    "misma": "no",
    "motivo": "Diferencia en un solo apellido",
    "segundos": 4.8
   }
  ],
  "aciertos": 0,
  "peligrosas": 0
 },
 {
  "id": 12,
  "tipo": "nombre",
  "a": "ALEJANDRA RIOS",
  "b": "ALEJANDRA RIOS VARGAS",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "no",
    "motivo": "Apellido adicional",
    "segundos": 4.5
   },
   {
    "misma": "no",
    "motivo": "Apellido adicional",
    "segundos": 4.0
   },
   {
    "misma": "no",
    "motivo": "Apellido adicional",
    "segundos": 4.0
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 13,
  "tipo": "domicilio",
  "a": "Calle Fresno 9, Col. Las Flores, Zinacantepec",
  "b": "CALLE FRESNO 9 FRACC LAS FLORES ZINACANTEPEC",
  "esperado": [
   "si",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 7.3
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 6.3
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 6.3
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 14,
  "tipo": "domicilio",
  "a": "Calle Roble 22, Col. Centro, Toluca",
  "b": "CALLE ROBLE 22 COL CENTRO METEPEC",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 7.0
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 6.3
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 6.3
   }
  ],
  "aciertos": 0,
  "peligrosas": 3
 },
 {
  "id": 15,
  "tipo": "domicilio",
  "a": "Privada Juárez 3, Barrio Santa Cruz, Lerma",
  "b": "PRIV JUAREZ 3 STA CRUZ LERMA",
  "esperado": [
   "si"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 7.1
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 6.3
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y abreviaturas comunes",
    "segundos": 6.6
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 },
 {
  "id": 16,
  "tipo": "domicilio",
  "a": "Calle Sauce 30, San Mateo Atenco",
  "b": "CALLE SAUCE 30 SAN PEDRO ATENCO",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y acentos, pero son idénticos en contenido",
    "segundos": 8.4
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y acentos, pero son idénticos en contenido",
    "segundos": 7.4
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y acentos, pero son idénticos en contenido",
    "segundos": 7.5
   }
  ],
  "aciertos": 0,
  "peligrosas": 3
 },
 {
  "id": 17,
  "tipo": "domicilio",
  "a": "Calle Cedro 11, Col. La Joya, Toluca",
  "b": "CALLE CEDRO 11 COL LA LOMA TOLUCA",
  "esperado": [
   "no",
   "duda"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y acentos, pero son idénticos en contenido",
    "segundos": 8.2
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y acentos, pero son idénticos en contenido",
    "segundos": 7.6
   },
   {
    "misma": "si",
    "motivo": "Diferencia en mayúsculas y acentos, pero son idénticos en contenido",
    "segundos": 7.8
   }
  ],
  "aciertos": 0,
  "peligrosas": 3
 },
 {
  "id": 18,
  "tipo": "domicilio",
  "a": "Calle Pino 5, Col. Centro, Toluca",
  "b": "C. PINO NO. 5 CENTRO TOLUCA DE LERDO",
  "esperado": [
   "si"
  ],
  "proceso": "gris",
  "opiniones": [
   {
    "misma": "si",
    "motivo": "Acentos y abreviaturas comunes no hacen distintos a dos textos",
    "segundos": 7.9
   },
   {
    "misma": "si",
    "motivo": "Los apellidos y números de casa son los mismos, y solo hay un error de letra en la calle y un error de acento en el nombre de la ciudad.",
    "segundos": 10.3
   },
   {
    "misma": "si",
    "motivo": "Los apellidos y números de casa son los mismos, y solo hay un error de letra en la calle y un error de acento en el nombre de la ciudad.",
    "segundos": 10.1
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 }
]
```

## Notas del agente

- **RAM libre:** 15.1 GB antes de correr y 10.0 GB después (el modelo queda cargado en memoria). La RAM total es de 23.3 GB.
- **Duración:** unos 5 minutos para 54 opiniones (18 pares × 3 vueltas).
- **¿Se puso lenta la PC?** No se midió el uso de CPU ni hubo observación directa de lentitud. Ollama corre solo en CPU, así que es esperable que la PC estuviera cargada mientras corría.
- **Modelo:** `sidp-revisor`, creado en la tarea 001 desde `llama3.1:latest`. Ollama 0.40.4, solo en `127.0.0.1:11434`. No se descargó nada.
- **Comprobación previa sin modelo:** procesos "11 de 11" fichas y "18 de 18" pares en zona gris.
- **Peligrosas (dijo "si" cuando era "no/duda"):** 12 de 54, repartidas en 4 pares, 3 vueltas cada una: par 10 (María José / José María), par 14 (Toluca / Metepec), par 16 (San Mateo / San Pedro Atenco) y par 17 (La Joya / La Loma).
- **Aciertos:** 27 de 54 (9 pares completos). Respondió "no" a 10 de los 12 pares de nombre (todos menos los pares 2 y 10), incluidos los que debían ser "si" (pares 1, 4, 7, 9 y 11), y "si" a los 6 pares de domicilio, incluidos los 4 que debían ser "no/duda".
- **Errores:** ninguno. Las 54 opiniones respondieron en el formato correcto.
