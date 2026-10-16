SIDP: CÓMO INSTALAR Y QUÉ HACER SI ALGO FALLA
===============================================

INSTALAR EN EL SERVIDOR (una sola vez)
1. Baja SIDP-Instalador.exe (GitHub > Actions > la corrida más reciente > Artifacts > sidp-windows).
2. Doble clic en SIDP-Instalador.exe > Sí (permiso de administrador) > Siguiente > Instalar.
3. Se abre SIDP en su propia ventana. En Ajustes > Cerebro de la PC 4:
   - da clic en "Buscar la PC 4 en la red" (escribe sola la dirección);
   - escribe la clave del cerebro una sola vez y da clic en Conectar.
4. Listo. Desde ahora:
   - SIDP trabaja desde que alguien inicia sesión en el servidor, aunque la ventana esté cerrada;
   - el ícono "SIDP" del escritorio abre la ventana;
   - el ícono "Expedientes de alumnos" abre C:\SIDP\Expedientes: una carpeta por grupo y por alumno, con sus PDF;
   - desinstalar SIDP no borra C:\SIDP.

DÓNDE ESTÁ CADA COSA
- Servidor: C:\SIDP\Expedientes (los PDF que la escuela consulta) y C:\SIDP\sistema (lo interno del programa).
- PC 4: la base de datos con los datos de cada alumno, los modelos de IA y una copia de C:\SIDP\sistema
  (C:\SIDP-datos\respaldo), que se actualiza sola cada hora.

SI SIDP NO ENCUENTRA A LA PC 4
SIDP la revisa cada minuto y, si la red le cambió la IP, la busca sola. Si aun así no conecta:
1. Revisa que la PC 4 tenga la luz encendida y que las dos PC estén en la misma red (mismo módem o mismo Wi-Fi).
2. En Ajustes, da clic en "Buscar la PC 4 en la red". El mensaje dice qué pasa:
   - "Nadie contesta": la PC 4 está apagada, en otra red o arrancando. Espera 2 minutos y vuelve a buscar.
   - "contesta otro programa": esa IP es de otro equipo; busca de nuevo.
   - "la clave no coincide": escribe otra vez la clave del cerebro.
3. Reinicia la PC 4 con el botón de encendido. Sus servicios (base, IA y cerebro) arrancan solos en unos
   2 minutos, sin monitor y sin iniciar sesión.
4. Último recurso: conecta las dos PC al mismo módem con cable y escribe la dirección a mano
   (http://IP-de-la-PC-4:8771).

MIENTRAS LA PC 4 NO ESTÉ
- SIDP sigue funcionando en el servidor: se escanea, se guarda y los PDF quedan en C:\SIDP\Expedientes.
- El escaneo lee con las herramientas del servidor (más lento y sin el modelo que lee letra a mano).
- El respaldo, la lista de alumnos de la PC 4 y el análisis de datos se ponen al día solos cuando vuelva.

SI SE DESCOMPONE EL SERVIDOR
1. Instala SIDP en otra PC con SIDP-Instalador.exe.
2. Cierra SIDP en esa PC (menú Inicio > SIDP > Apagar SIDP).
3. Copia la carpeta C:\SIDP-datos\respaldo\actual de la PC 4 a C:\SIDP\sistema de la PC nueva.
4. Abre SIDP. Los PDF de C:\SIDP\Expedientes se vuelven a armar solos con lo que se autorizó.

SI SE DESCOMPONE LA PC 4
- El servidor sigue trabajando solo. La base de la PC 4 tiene una copia diaria en C:\SIDP-datos\respaldos
  (archivos .dump) que se restaura con pg_restore en la PC 4 nueva. Pídeselo al agente con la tarea de la PC 4.

ACTUALIZACIONES (solas)
- Cuando se fusiona algo a main, GitHub publica la versión nueva de SIDP (Releases, v1.0.N). La PC 4 la revisa
  cada hora, la baja a C:\SIDP-datos\actualizaciones y comprueba que llegó completa.
- El servidor le pregunta a la PC 4 cada hora. Si hay una versión nueva, la baja y la pone cuando nadie ha hecho
  cambios en SIDP en 10 minutos: SIDP se reinicia solo en unos segundos. El servidor no se conecta a GitHub.
- En Ajustes > Cerebro de la PC 4 se ve qué versión tiene SIDP y si ya hay otra lista.
- Si la versión nueva no arranca, SIDP regresa solo a la anterior y ya no la vuelve a intentar.

SI UNA ACTUALIZACIÓN SALE MAL
1. Menú Inicio > SIDP > Apagar SIDP.
2. Abre la carpeta C:\Program Files\SIDP. Ahí está SIDP.anterior.exe (la versión de antes).
3. Cambia el nombre de SIDP.exe a SIDP.malo.exe y el de SIDP.anterior.exe a SIDP.exe.
4. Abre SIDP con el ícono del escritorio.
5. Para que no se vuelva a poner la mala: en la PC 4 publica la anterior a mano
   (python -m validacion.actualizar publicar RUTA\SIDP.exe --version 1.0.N --forzar).
Sin PC 4 ni internet: instala otra vez con SIDP-Instalador.exe; no borra C:\SIDP.
