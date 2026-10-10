# Operación y recuperación

## Instalación inicial

Servidor de plataforma, agente por equipo, cerebro CLI opcional. Arrancar desde raíz. Loopback por defecto; antes de habilitar LAN preparar HTTPS/proxy y restricciones. No transmitir tokens por HTTP fuera del laboratorio local.

/api/salud heredada solo indica que API responde; no certifica base/disco/integridad. Diagnóstico real pendiente.

## Datos

- Escolar: backend/sidp_nodo_local.db por defecto.
- Cola: datos/orquestacion.db, migración 001 y user_version=1.
- Agente: datos-agente/pendientes.db.
- SIDP_DATA_DIR reubica ambas bases de plataforma, pero no migra archivos.

Para cambiar ruta: detener procesos, respaldar, copiar ambas bases conservando nombres, configurar ruta, verificar conteos. Directorio vacío sin copia mostrará instalación vacía. No borrar original antes de comprobar.

## Copia y restauración manual

1. Detener cerebro, agentes y plataforma para copia coherente.
2. Copiar las bases y pendientes a medio externo restringido; registrar versión de aplicación. Conservar configuración de identidades separada y protegida.
3. Verificar lectura de copias y registrar fecha. Archivos escolares futuros necesitarán manifiesto coherente.
4. Restaurar en carpeta distinta, probar con credenciales de prueba y comparar conteos y tareas. No conectar agentes productivos a esa copia.
5. Mantener una sola plataforma escritora al recuperar, evitando servidor antiguo y restaurado simultáneos.

Copia automática, cifrado administrado, rotación y ejercicio periódico pendientes. Sin RPO/RTO medidos.

## Actualizaciones

Respaldar antes de migrar. Cola tiene migración aditiva; esquema más nuevo que código se rechaza. create_all escolar es legado y no reemplaza migraciones de producción. Actualizar procesos separados preservando contratos; probar primero un agente. Futura actualización verificará firma/hash, compatibilidad, salud y reversión. No migrar irreversiblemente sin restauración prevista.

## Observabilidad pendiente

Métricas de cola, pendientes, fallos por capacidad, disco y latidos. Límites/retención de eventos; listado actual máximo 100, sin paginación. Alertas para personal y escalamiento técnico. Agente reintenta errores de transporte; errores HTTP de autorización detienen el proceso para corregir configuración.
