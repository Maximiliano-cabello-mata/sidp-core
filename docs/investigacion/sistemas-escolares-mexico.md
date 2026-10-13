# Sistemas escolares en México y su relación con SIDP

Fecha: 2026-10-13. **Aviso:** el entorno de investigación no pudo abrir las páginas de gob.mx, sep.gob.mx, edomex.gob.mx, edugem.gob.mx ni unam.mx. Salvo lo marcado como comprobado, todo viene de resúmenes de búsqueda y debe confirmarse con la supervisión escolar antes de construir. Versión con más detalle: documento "Sistemas escolares en México y cómo se conectan con SIDP" del proyecto.

## Conclusión

Una primaria del Estado de México trabaja con tres sistemas oficiales: el **MIGE** del estado (alumnos, evaluaciones, asistencia, boletas y certificados), el **SAID** (preinscripción) y la **Estadística 911** de la SEP. Ninguno ofrece API ni acepta carga de archivos: todo es captura manual del director o docente. SIDP no los sustituye ni se conecta a ellos: **los alimenta**. Guarda los datos completos y prepara lo que el director captura, con los mismos campos y en el mismo orden.

## Sistemas oficiales

| Sistema | Qué es | Quién lo usa | Intercambio | Integración |
|---|---|---|---|---|
| SIGED (SEP) | Plataforma nacional: alumnos por CURP, docentes, escuelas por CCT, boletas y certificados (acuerdo DOF 20/03/2018) | Nadie directo: el sistema estatal lo alimenta | Portal web; padres consultan boleta con CURP (PDF con QR) | Sin API pública |
| Estadística 911.3 | Cuestionario de inicio y fin de ciclo para primaria general | Director, con usuario estatal | Captura web en f911.sep.gob.mx; acuse impreso | Manual; SIDP calcula los totales |
| CURP (RENAPO) | Consulta pública individual | Secretaría | gob.mx/curp | Servicio automático solo para dependencias con convenio; SIDP valida formato y dígito |
| CCT | 10 caracteres: entidad, sostenimiento, nivel (PR), consecutivo, verificador | Todos | Llave de los sistemas SEP | Dato fijo de la escuela |
| MIGE (Edomex) | Inscripciones, bajas, evaluaciones, asistencia, cambios de grado, impresión por alumno | Directores; docentes descargan boletas | Web con usuario; boletas en PDF; certificados con QR uno por CURP o en ZIP | Manual; dirección exacta sin confirmar |
| SAID (Edomex) | Preinscripción a 1.º de primaria, preescolar y 1.º de secundaria | Padres en línea | Registro febrero-marzo; listados en la escuela en agosto | SIDP recibe el listado de asignados |
| SEIEM (escuelas 15D) | Control escolar del subsistema federalizado | Departamento de Control Escolar | Sin confirmar; una circular sugiere que usa el MIGE | Por confirmar |

**Evaluación en primaria** (Acuerdo 10/09/23, DOF 27/09/2023, Plan de Estudio 2022): por campo formativo, tres periodos más la final, observaciones por campo. Escala de 6 a 10 en 1.º y 2.º; de 5 a 10 de 3.º a 6.º con promedio a un decimal; 5 no aprueba.

**Datos personales:** la escuela pública forma parte de un sujeto obligado (Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados; nueva ley del 20/03/2025 según los resúmenes). Requiere aviso de privacidad simplificado e integral y derechos ARCO; normalmente lo publica la secretaría estatal.

## Qué hacer en SIDP

| Sistema | Qué hace SIDP | Dirección | Fase |
|---|---|---|---|
| CCT | Guarda la clave y deduce el subsistema (15E estatal, 15D SEIEM) | Dato fijo | 4 |
| CURP | Revisa formato y dígito al capturar; queda "pendiente de confirmar" hasta verificarla en gob.mx/curp | Interno | 6 |
| SAID | Carga el listado de asignados y abre su expediente con los documentos de la convocatoria | Entrada | 6 |
| MIGE: inscripciones, bajas y cambios | Hoja lista para capturar, mismos campos y orden | Salida | 6 |
| MIGE: evaluaciones | Calificaciones por campo formativo, tres periodos y escala oficial; reporte por grupo | Salida | 7 |
| MIGE: asistencia | Concentrado por grupo y periodo | Salida | 7 |
| Boletas y certificados MIGE | Guarda en el expediente el PDF oficial; reparte el ZIP de certificados por CURP | Entrada | 8 |
| Estadística 911.3 | Calcula los totales para copiarlos | Salida | 8 |
| Aviso de privacidad | Muestra el aviso estatal y registra el consentimiento del tutor | Interno | Buzón |

Reglas de diseño:

1. La boleta de SIDP es de consulta; la oficial sale del MIGE y SIDP lo indica.
2. Los campos siguen a la SEP y al MIGE: CURP, CCT, grado, grupo, campo formativo, escala oficial.
3. Lo que no está en línea (plantilla de personal, inventario, asistencia docente) se cubre con el catálogo de formatos.

## Qué copiar y qué no

Fuentes: UNAM (DGAE, SIAE), IPN (SAES), UAEMéx, SEP, Saeko, Phidias, y los proyectos libres Gibbon y openSIS (estos dos comprobados en GitHub).

**Copiar:**

- Lista de documentos por alumno con estados pendiente, recibido, validado o rechazado con motivo, y la opción de volver a subir (UNAM: "Documento guardado" y botón "Ver").
- Folio en cada trámite y documento emitido; constancias con QR que llevan a una página de verificación con datos mínimos (SEP, Sello Digital UNAM).
- Cambios de datos del tutor como solicitud que el personal aprueba, con historial (Gibbon, Data Updater).
- Cuenta familiar con varios hijos; CURP como identificador (SEP).
- Consentimiento explícito al subir documentos (UNAM).
- Comprobante descargable al terminar un trámite (IPN).
- Carga masiva desde archivo (openSIS).
- Marca visible de "oficial" o "solo consulta" en lo impreso.

**No copiar:** recuperar contraseña solo en ventanilla; sesiones que cierran en 5 minutos; portales que no sirven en celular; cancelar trámites sin aviso ni plazo; recibir documentos por correo (no deja registro); módulos de cobro que una primaria pública no necesita; activar muchos módulos a medias.

## Preguntas para la escuela

1. ¿La CCT empieza con 15E (estatal) o 15D (SEIEM)?
2. ¿Capturan en el MIGE? ¿Cuál es su dirección?
3. ¿El MIGE exporta listas de alumnos en Excel?
4. ¿Cómo y a quién entregan plantilla de personal, inventario y asistencia docente?
5. ¿Hay un aviso de privacidad de control escolar que deban usar?
6. Captura de pantalla de la sección de evaluaciones del MIGE.

## Fuentes

Comprobadas: [Gibbon](https://github.com/GibbonEdu/core), [openSIS Classic](https://github.com/OS4ED/openSIS-Classic).

Por confirmar (aparecieron en búsqueda, no se abrieron): [Acuerdo SIGED DOF 20/03/2018](https://sigedqa.sep.gob.mx/SIGED/archivos/DOF_200318.pdf), [Manual 911 2025-2026](https://f911.sep.gob.mx/2025-2026/Documento/Manuales/Manual_CT.pdf), [Acuerdo 10/09/23](https://dgair.sep.gob.mx/storage/recursos/CE/acuerdo_10092023.pdf), [Control escolar Edomex](http://subeducacionbasica.edomex.gob.mx/control-escolar), [Guía de boletas MIGE](https://edugem.gob.mx/mige/tutoriales/Guia_descargas_de_boletas.pdf), [Guía de certificados MIGE](https://edugem.gob.mx/mige/tutoriales/Guia_descarga_certificados.pdf), [Convocatoria SAID](https://edomex.gob.mx/sites/edomex.gob.mx/files/files/CONVOCATORIA%20SAID%20.pdf), [Certificados Edomex (DGAIR)](https://dgair.sep.gob.mx/storage/recursos/CE/cert_cert/2019_2020/mexico_estado.pdf), [Normas SEIEM (SINCREE)](http://www.sincree.sep.gob.mx/es/controlescolar/SEIEM), [Ingreso DGAE UNAM](https://www.dgae.unam.mx/Licenciatura2025/).
