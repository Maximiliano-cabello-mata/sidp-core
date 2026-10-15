# Resultados del laboratorio: zona gris

- Fecha: 2026-10-14 18:12
- Equipo: DESKTOP-8RJIA6B
- Sistema: Windows-11-10.0.22000-SP0
- Procesador: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD
- Python: 3.15.0
- Modelo: sidp-revisor-2
- Ollama: 0.40.4

## Resumen

- Pares en zona gris según los procesos: 18 de 18.
- Opiniones acertadas: 42 de 54; 12 dijeron "si" cuando era "no".
- Tiempo por opinión: promedio 5.2 s, máximo 17.0 s.

## Pares

| Par | Tipo | Texto A | Texto B | Esperado | Opiniones |
|---|---|---|---|---|---|
| 1 | nombre | JOSE LUIS PERES ORTEGA | JOSE LUIS PEREZ ORTEGA | si | si, si, si |
| 2 | nombre | MARIA DE LOURDES SANCHEZ RUIZ | Ma. de Lourdes Sanches Ruiz | si | si, si, si |
| 3 | nombre | JUAN CARLOS LOPEZ | JUAN CARLOS LOPEZ HERNANDEZ | no/duda | si, si, si |
| 4 | nombre | LUIS FERNANDO DIAZ CRUZ | LUIS FERNANDO DIAS CRUZ | si | si, si, si |
| 5 | nombre | ROBERTO MENDOZA ROJAS | ROBERTA MENDOZA ROJAS | no/duda | no, no, no |
| 6 | nombre | DANIEL TORRES ARIAS | DANIELA TORRES ARIAS | no/duda | no, no, no |
| 7 | nombre | CARMEN VELAZQUEZ PAZ | CARMEN VELASQUEZ PAZ | si | si, si, si |
| 8 | nombre | PEDRO SOTO REYES | PEDRO SOTO REYNA | no/duda | si, si, si |
| 9 | nombre | JESUS ALEJANDRO NUÑEZ | JESUS ALEJANDRO NUNES | si | si, si, si |
| 10 | nombre | MARIA JOSE CASTILLO | JOSE MARIA CASTILLO | no/duda | si, si, si |
| 11 | nombre | GERARDO IBARRA SOLIS | GERARDO YBARRA SOLIS | si/duda | si, si, si |
| 12 | nombre | ALEJANDRA RIOS | ALEJANDRA RIOS VARGAS | no/duda | si, si, si |
| 13 | domicilio | Calle Fresno 9, Col. Las Flores, Zinacantepec | CALLE FRESNO 9 FRACC LAS FLORES ZINACANTEPEC | si/duda | si, si, si |
| 14 | domicilio | Calle Roble 22, Col. Centro, Toluca | CALLE ROBLE 22 COL CENTRO METEPEC | no/duda | no, no, no |
| 15 | domicilio | Privada Juárez 3, Barrio Santa Cruz, Lerma | PRIV JUAREZ 3 STA CRUZ LERMA | si | si, si, si |
| 16 | domicilio | Calle Sauce 30, San Mateo Atenco | CALLE SAUCE 30 SAN PEDRO ATENCO | no/duda | no, no, no |
| 17 | domicilio | Calle Cedro 11, Col. La Joya, Toluca | CALLE CEDRO 11 COL LA LOMA TOLUCA | no/duda | no, no, no |
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
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 17.0
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.5
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.6
   }
  ],
  "aciertos": 3,
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
    "motivo": "solo cambia una letra en el apellido y se usa abreviatura",
    "segundos": 6.7
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido y se usa abreviatura",
    "segundos": 5.9
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido y se usa abreviatura",
    "segundos": 6.0
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
    "misma": "si",
    "motivo": "solo cambia un apellido",
    "segundos": 4.6
   },
   {
    "misma": "si",
    "motivo": "solo cambia un apellido",
    "segundos": 4.0
   },
   {
    "misma": "si",
    "motivo": "solo cambia un apellido",
    "segundos": 4.0
   }
  ],
  "aciertos": 0,
  "peligrosas": 3
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
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 5.2
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.5
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.5
   }
  ],
  "aciertos": 3,
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
    "motivo": "el nombre de pila es distinto",
    "segundos": 5.1
   },
   {
    "misma": "no",
    "motivo": "el nombre de pila es distinto",
    "segundos": 4.3
   },
   {
    "misma": "no",
    "motivo": "el nombre de pila es distinto",
    "segundos": 4.4
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
    "motivo": "Daniel y Daniela son nombres distintos",
    "segundos": 5.0
   },
   {
    "misma": "no",
    "motivo": "Daniel y Daniela son nombres distintos",
    "segundos": 4.6
   },
   {
    "misma": "no",
    "motivo": "Daniel y Daniela son nombres distintos",
    "segundos": 4.4
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
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 5.3
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.7
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.6
   }
  ],
  "aciertos": 3,
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
    "misma": "si",
    "motivo": "solo cambia una letra en el segundo apellido",
    "segundos": 5.5
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el segundo apellido",
    "segundos": 4.9
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el segundo apellido",
    "segundos": 4.9
   }
  ],
  "aciertos": 0,
  "peligrosas": 3
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
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 5.3
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.6
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el apellido",
    "segundos": 4.6
   }
  ],
  "aciertos": 3,
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
    "motivo": "solo cambia el orden de los nombres de pila",
    "segundos": 5.8
   },
   {
    "misma": "si",
    "motivo": "solo cambia el orden de los nombres de pila",
    "segundos": 5.2
   },
   {
    "misma": "si",
    "motivo": "solo cambia el orden de los nombres de pila",
    "segundos": 5.2
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
    "misma": "si",
    "motivo": "solo cambia una letra en el primer apellido",
    "segundos": 5.5
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el primer apellido",
    "segundos": 4.8
   },
   {
    "misma": "si",
    "motivo": "solo cambia una letra en el primer apellido",
    "segundos": 4.8
   }
  ],
  "aciertos": 3,
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
    "misma": "si",
    "motivo": "solo falta el segundo apellido",
    "segundos": 4.6
   },
   {
    "misma": "si",
    "motivo": "solo falta el segundo apellido",
    "segundos": 4.0
   },
   {
    "misma": "si",
    "motivo": "solo falta el segundo apellido",
    "segundos": 4.0
   }
  ],
  "aciertos": 0,
  "peligrosas": 3
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
    "motivo": "misma calle, número, colonia y pueblo",
    "segundos": 6.1
   },
   {
    "misma": "si",
    "motivo": "misma calle, número, colonia y pueblo",
    "segundos": 4.8
   },
   {
    "misma": "si",
    "motivo": "misma calle, número, colonia y pueblo",
    "segundos": 4.8
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
    "misma": "no",
    "motivo": "el municipio es distinto",
    "segundos": 4.9
   },
   {
    "misma": "no",
    "motivo": "el municipio es distinto",
    "segundos": 4.1
   },
   {
    "misma": "no",
    "motivo": "el municipio es distinto",
    "segundos": 4.0
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
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
    "motivo": "misma calle, número, colonia y pueblo",
    "segundos": 5.7
   },
   {
    "misma": "si",
    "motivo": "misma calle, número, colonia y pueblo",
    "segundos": 4.8
   },
   {
    "misma": "si",
    "motivo": "misma calle, número, colonia y pueblo",
    "segundos": 4.8
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
    "misma": "no",
    "motivo": "el pueblo o municipio es distinto",
    "segundos": 5.2
   },
   {
    "misma": "no",
    "motivo": "el pueblo o municipio es distinto",
    "segundos": 4.4
   },
   {
    "misma": "no",
    "motivo": "el pueblo o municipio es distinto",
    "segundos": 4.4
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
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
    "misma": "no",
    "motivo": "la colonia es distinta",
    "segundos": 4.9
   },
   {
    "misma": "no",
    "motivo": "la colonia es distinta",
    "segundos": 4.0
   },
   {
    "misma": "no",
    "motivo": "la colonia es distinta",
    "segundos": 4.0
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
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
    "motivo": "misma calle, número y colonia; Toluca de Lerdo es Toluca",
    "segundos": 7.9
   },
   {
    "misma": "si",
    "motivo": "misma calle, número y colonia; Toluca de Lerdo es Toluca",
    "segundos": 6.6
   },
   {
    "misma": "si",
    "motivo": "misma calle, número y colonia; Toluca de Lerdo es Toluca",
    "segundos": 6.6
   }
  ],
  "aciertos": 3,
  "peligrosas": 0
 }
]
```

## Notas del agente

- **RAM libre:** 10.0 GB antes de correr (el modelo anterior seguía cargado) y 10.2 GB después. La RAM total es de 23.3 GB.
- **Duración:** unos 5 minutos para 54 opiniones (18 pares × 3 vueltas).
- **¿Se puso lenta la PC?** No se midió el uso de CPU ni hubo observación directa de lentitud. Ollama corre solo en CPU, así que es esperable que la PC estuviera cargada mientras corría.
- **Modelo:** `sidp-revisor-2`, creado desde `Modelfile.2` y `llama3.1:latest`. Ollama 0.40.4, solo en `127.0.0.1:11434`. No se descargó nada.
- **Comprobación previa sin modelo:** procesos "11 de 11" fichas y "18 de 18" pares en zona gris.
- **Peligrosas (dijo "si" cuando era "no/duda"):** 12 de 54, repartidas en 4 pares, 3 vueltas cada una: par 3 (falta el segundo apellido), par 8 (Reyes / Reyna), par 10 (María José / José María) y par 12 (falta el segundo apellido). Ninguna era de domicilio.
- **Aciertos:** 42 de 54 (14 pares completos). Mejoró en los pares de errores de una letra (1, 4, 7, 9 y 11 en "si") y en los domicilios con otra colonia o pueblo (14, 16 y 17 en "no"). Falló en apellidos distintos (par 8) o que faltan (pares 3 y 12) y en el orden María José / José María (par 10), que contestó "si" las 3 veces.
- **Comparación con `sidp-revisor`:** subió de 27 a 42 aciertos de 54. Las peligrosas se mantuvieron en 12, pero ahora están en nombres y no en domicilios.
- **Errores:** ninguno. Las 54 opiniones respondieron en el formato correcto.
