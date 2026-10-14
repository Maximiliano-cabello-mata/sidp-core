# Diseño de Interfaz de Usuario: Portal de Padres y Tutores — SIDP

Fecha: 2026-10-14  
Estado: Aprobado para diseño y maquetación de frontend  
Rol del Sistema: `Padre` / `Tutor`  
Documento rector del portal de autoservicio de inscripción e integración documental del Sistema Integral Delfino Pando (SIDP).  
Relacionado con: [modulo_expediente.md](modulo_expediente.md), [validacion_documental.md](validacion_documental.md) y [bocetos/padres.txt](bocetos/padres.txt).

---

## 1. Alcance y Filosofía de Diseño

El portal de padres y tutores está concebido como una herramienta web/móvil sencilla y accesible que permite a las familias completar el proceso de inscripción y carga documental oficial sin necesidad de filas presenciales tempranas.

### Principios de diseño para el tutor:
1. **Instrucciones claras y directas:** Lenguaje sin tecnicismos; se indica con precisión qué documento fotografiar o escanear y cómo debe presentarse.
2. **Semáforo de avance en tiempo real:** Cada documento muestra claramente si está pendiente (`[ ⬆️ Subir ]`) o si ya fue recibido correctamente (`[ ✅ SUBIDO ]`).
3. **Mecanismo de candado en el envío:** Para evitar expedientes incompletos que saturen a la secretaría, el botón de envío final permanece bloqueado hasta que el 100% de los requisitos estén cargados.
4. **Separación por secciones lógicas:** Distinción nítida entre requisitos del estudiante, requisitos especiales por grado y documentación del tutor.

---

## 2. Estructura de Navegación

* **Encabezado Superior:**
  * Identificación del plantel: `[ 🏫 Nombre de tu Escuela ]`
  * Nombre del Padre/Tutor autenticado: `👤 Padre/Tutor: Juan Pérez`
  * Botón de cierre de sesión seguro: `[ Salir ]`
* **Cuerpo Principal:** Formulario guiado de carga documental por secciones.

---

## 3. Especificación de Pantallas y Wireframes

### 3.1. Pantalla de Inscripción Digital y Carga de Expediente

#### Componentes:
* **Ficha del Trámite:** Alumno aspirante, grado de ingreso y estado del trámite (`⚠️ Estado: Incompleto. Debes subir TODOS los documentos para finalizar`).
* **Sección 1: Documentos del Alumno (Obligatorios):**
  * Hoja de registro
  * Carta compromiso
  * Acta de nacimiento (con enlace `👁️ Ver` para confirmar el archivo subido)
  * CURP del alumno
  * Boleta de grados anteriores
  * Comprobante de domicilio (vigencia máxima de 3 meses)
  * Certificado médico escolar
* **Requisitos Especiales (Solo para Nuevo Ingreso / 1er Grado):**
  * Formato SAID (Comprobante oficial de asignación del Estado)
  * Certificado de 3º de Preescolar / Kínder
* **Sección 2: Documentos del Padre o Tutor (Obligatorios):**
  * Acta de nacimiento del tutor
  * CURP del tutor
  * Credencial de elector INE (ampliada al 200%, frente y reverso)
* **Acción Final Protegida:**
  * Botón `[ 📤 ENVIAR EXPEDIENTE PARA REVISIÓN ]` inhabilitado visualmente (`🔒 en gris`) hasta que todos los requisitos tengan el estado `✅ SUBIDO`.

#### Wireframe:
```text
================================================================================
[ 🏫 Nombre de tu Escuela ] | 👤 Padre/Tutor: Juan Pérez | [ Salir ]
================================================================================
 
  INSCRIPCIÓN DE: Carlos Gómez Pérez (Ingreso a 1er Grado)
  ⚠️ Estado: Incompleto. Debes subir TODOS los documentos para finalizar.
  
  Instrucciones: Escanea o toma una foto clara de cada documento y súbelo
  en su sección correspondiente.

  =========================================================================
  📁 SECCIÓN 1: DOCUMENTOS DEL ALUMNO (Obligatorios)
  =========================================================================
  [ ⬆️ Subir ] Hoja de registro 
  [ ⬆️ Subir ] Carta compromiso 
  [ ✅ SUBIDO ] Acta de nacimiento (carlos_acta.pdf) 👁️ Ver
  [ ⬆️ Subir ] CURP del alumno
  [ ⬆️ Subir ] Boleta de grados anteriores
  [ ⬆️ Subir ] Comprobante de domicilio (No mayor a 3 meses)
  [ ⬆️ Subir ] Certificado Médico
  
  -------------------------------------------------------------------------
  🌟 REQUISITOS ESPECIALES (Solo para Nuevo Ingreso / 1er Grado)
  -------------------------------------------------------------------------
  [ ⬆️ Subir ] Formato SAID (Asignación oficial)
  [ ⬆️ Subir ] Certificado de 3º de Kinder
  
  =========================================================================
  📁 SECCIÓN 2: DOCUMENTOS DEL PADRE O TUTOR (Obligatorios)
  =========================================================================
  [ ⬆️ Subir ] Acta de nacimiento del Tutor
  [ ⬆️ Subir ] CURP del Tutor
  [ ⬆️ Subir ] Credencial INE (Ampliada al 200%, frente y reverso)

  =========================================================================
                            [ 📤 ENVIAR EXPEDIENTE PARA REVISIÓN ]
         (El botón está en gris 🔒 hasta que todos los documentos digan ✅ SUBIDO)
================================================================================
```

---

## 4. Reglas de Validación y Conexión con el Sistema Central

1. **Recepción en Outbox:** Cuando el tutor envía el expediente completo, los archivos se integran al almacén local seguro y se genera una notificación para la Secretaría.
2. **Formatos aceptados:** Archivos PDF e imágenes legibles (`JPG`, `PNG`) con límite de peso optimizado para conexiones escolares modestas.
3. **Revisión por Secretaría:** La secretaría revisa la legibilidad y validez de cada archivo cargado, pudiendo aprobar o devolver con observaciones específicas al tutor.
