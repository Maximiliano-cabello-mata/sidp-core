// Motor de las pantallas de validación. Las mismas pantallas funcionan de dos formas:
// - "local": dentro de SIDP-Validador.exe; las llamadas van a su servidor.
// - "demo": en GitHub Pages; el código de Python del repositorio corre en el navegador (Pyodide)
//   sobre expedientes inventados y nada sale del navegador.
const SIDP = window.SIDP || { modo: 'local' };

function crearMotor() {
  return SIDP.modo === 'demo' ? motorDemo() : motorLocal();
}

function motorLocal() {
  async function api(ruta, cuerpo) {
    const opciones = { headers: { 'X-SIDP-Token': SIDP.token || '' } };
    if (cuerpo instanceof FormData) Object.assign(opciones, { method: 'POST', body: cuerpo });
    else if (cuerpo !== undefined) {
      opciones.method = 'POST';
      opciones.headers['Content-Type'] = 'application/json';
      opciones.body = JSON.stringify(cuerpo);
    }
    const respuesta = await fetch(ruta, opciones);
    const datos = await respuesta.json();
    if (!respuesta.ok || datos.error) throw new Error(datos.error || respuesta.statusText);
    return datos;
  }
  return {
    listo: Promise.resolve(),
    estado: () => api('/api/estado'),
    revisarTodo: () => api('/api/revisar_todo', {}),
    detalle: (id) => api('/api/expediente?id=' + encodeURIComponent(id)),
    decidir: (id, decision, motivo) => api('/api/decidir', { id, decision, motivo }),
    reescribir: null,
    archivoUrl: (id, nombre) => `/api/archivo?id=${encodeURIComponent(id)}&nombre=${encodeURIComponent(nombre)}&t=${encodeURIComponent(SIDP.token || '')}`,
    configuracion: () => api('/api/configuracion'),
    guardarConfiguracion: (datos) => api('/api/configuracion', datos),
    base: () => api('/api/base'),
    enviar: (formulario) => api('/api/padres/enviar', formulario),
    curps: () => api('/api/curps'),
    constancia: async (archivo) => {
      const respuesta = await fetch('/api/renapo/constancia', { method: 'POST', body: archivo,
        headers: { 'X-SIDP-Token': SIDP.token || '', 'Content-Type': 'application/pdf', 'X-SIDP-Nombre': encodeURIComponent(archivo.name) } });
      const datos = await respuesta.json();
      if (!respuesta.ok || datos.error) throw new Error(datos.error || respuesta.statusText);
      return datos;
    },
    renapoNoEncontrada: (alumno) => api('/api/renapo/no_encontrada', { alumno }),
    escaneoLeer: (archivos) => {
      const formulario = new FormData();
      for (const archivo of archivos) formulario.append('archivo', archivo, archivo.name);
      return api('/api/escaneo/leer', formulario);
    },
    escaneoGuardar: (lote, datos) => api('/api/escaneo/guardar', { lote, ...datos }),
    escaneoDescartar: (lote) => api('/api/escaneo/descartar', { lote }),
    paginaUrl: (lote, archivo) => `/api/escaneo/pagina?lote=${encodeURIComponent(lote)}&archivo=${encodeURIComponent(archivo)}&t=${encodeURIComponent(SIDP.token || '')}`,
    documentosPadres: () => api('/api/padres/documentos').then((r) => r.documentos),
    plantillas: () => api('/api/plantillas'),
    plantillaLeer: (archivos) => {
      const formulario = new FormData();
      for (const archivo of archivos) formulario.append('archivo', archivo, archivo.name);
      return api('/api/plantillas/leer', formulario);
    },
    plantillaGuardar: (datos, archivos = []) => {
      const formulario = new FormData();
      formulario.append('captura', JSON.stringify(datos));
      for (const archivo of archivos) formulario.append('muestra', archivo, archivo.name);
      return api('/api/plantillas/guardar', formulario);
    },
    plantillaActiva: (clave, activa) => api('/api/plantillas/activa', { clave, activa }),
    grupos: () => api('/api/grupos'),
    grupo: (id) => api('/api/grupo?id=' + encodeURIComponent(id)),
    buscarAlumno: (nombre, curp = '') => api(`/api/buscar_alumno?nombre=${encodeURIComponent(nombre)}&curp=${encodeURIComponent(curp)}`),
    listaLeer: (archivos, texto, apellidosPrimero) => {
      const formulario = new FormData();
      formulario.append('captura', JSON.stringify({ texto, apellidos_primero: apellidosPrimero }));
      for (const archivo of archivos) formulario.append('archivo', archivo, archivo.name);
      return api('/api/listas/leer', formulario);
    },
    listaGuardar: (datos) => api('/api/listas/guardar', datos),
    listaTraer: () => api('/api/listas/traer', {}),
    grupoCrear: (grado, letra) => api('/api/grupos/crear', { grado, letra }),
    ubicar: (alumnoId, grupoId, mismoQue) => api('/api/grupos/ubicar', { alumno_id: alumnoId, grupo_id: grupoId, mismo_que: mismoQue }),
    analisis: () => api('/api/analisis'),
    descargar: async (que, formato) => {
      const enlace = document.createElement('a');
      enlace.href = `/api/exportar?que=${encodeURIComponent(que)}&formato=${encodeURIComponent(formato)}&t=${encodeURIComponent(SIDP.token || '')}`;
      enlace.download = '';
      document.body.appendChild(enlace); enlace.click(); enlace.remove();
    },
    muestraUrl: (clave, archivo) => `/api/plantillas/muestra?clave=${encodeURIComponent(clave)}&archivo=${encodeURIComponent(archivo)}&t=${encodeURIComponent(SIDP.token || '')}`,
    // Lo que vive en la PC 4: inventario, análisis con pandas y respaldo.
    inventario: () => api('/api/inventario'),
    inventarioAlta: (datos) => api('/api/inventario/alta', datos),
    inventarioCambiar: (datos) => api('/api/inventario/cambiar', datos),
    etiquetasUrl: (codigos) => `/api/etiquetas?codigos=${encodeURIComponent(codigos.join(','))}&t=${encodeURIComponent(SIDP.token || '')}`,
    analisisPC4: (conIA) => api('/api/analisis_pc4' + (conIA ? '?ia=1' : '')),
    respaldar: () => api('/api/respaldo', {}),
  };
}

function motorDemo() {
  let py = null;
  const GLUE = `
import base64, datetime, json, sys
sys.path.insert(0, '/sidp')
from validacion.registro import Registro
from validacion.servicio import Bandeja, ErrorBandeja
bandeja = Bandeja('/demo', hoy=datetime.date(2026, 10, 14), usar_modelo=False, base=':memory:', editable=True,
                  registro=Registro(':memory:'))
# Dos listas de grupo inventadas, con los mismos niños de los expedientes de ejemplo y algunos sin expediente.
for _grado, _letra, _nombres in ((3, 'A', ['HERNANDEZ RAMOS LUIS', 'CASTRO NAVA DIEGO', 'LOPEZ GIL MATEO', 'SOTO REYES EMILIO',
                                           'PRADO LUNA JULIAN', 'GOMEZ VARGAS ANDREA', 'NUÑEZ ORTIZ SANTIAGO']),
                                 (2, 'B', ['BRAVO LEON ANA SOFIA', 'RUIZ PAZ SOFIA', 'MORA DIAZ VALERIA', 'TORRES ARIAS REGINA',
                                           'HERRERA DIAZ PAULA', 'MENDEZ CRUZ CAMILA'])):
    bandeja.lista_guardar({'grado': _grado, 'letra': _letra, 'filas': [
        dict(zip(('primer_apellido', 'segundo_apellido', 'nombres'), _n.split(' ', 2))) for _n in _nombres]})
def llamar(nombre, argumentos):
    try:
        return json.dumps({'ok': getattr(bandeja, nombre)(*json.loads(argumentos))}, ensure_ascii=False, default=str)
    except ErrorBandeja as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
def constancia(nombre, contenido):
    try:
        return json.dumps({'ok': bandeja.constancia_renapo(nombre, base64.b64decode(contenido))}, ensure_ascii=False, default=str)
    except ErrorBandeja as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
def escaneo(archivos):
    lista = [(a['nombre'], base64.b64decode(a['contenido'])) for a in json.loads(archivos)]
    try:
        return json.dumps({'ok': bandeja.escaneo_leer(lista)}, ensure_ascii=False, default=str)
    except ErrorBandeja as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
def plantilla(nombre, datos, archivos):
    lista = [(a['nombre'], base64.b64decode(a['contenido'])) for a in json.loads(archivos)]
    try:
        salida = bandeja.plantilla_leer(lista) if nombre == 'leer' else bandeja.plantilla_guardar(json.loads(datos), lista, 'administrador (demostración)')
        return json.dumps({'ok': salida}, ensure_ascii=False, default=str)
    except ErrorBandeja as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
def lista(archivos, texto, apellidos_primero):
    lista = [(a['nombre'], base64.b64decode(a['contenido'])) for a in json.loads(archivos)]
    try:
        return json.dumps({'ok': bandeja.lista_leer(lista, texto, apellidos_primero)}, ensure_ascii=False, default=str)
    except ErrorBandeja as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
def exportar(que, formato):
    try:
        nombre, contenido, tipo = bandeja.exportar(que, formato)
        return json.dumps({'ok': {'nombre': nombre, 'contenido': base64.b64encode(contenido).decode(), 'tipo': tipo}})
    except ErrorBandeja as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
def recibir(captura, archivos):
    lista = [(a['espacio'], a['nombre'], base64.b64decode(a['contenido'])) for a in json.loads(archivos)]
    try:
        return json.dumps({'ok': bandeja.recibir(json.loads(captura), lista)}, ensure_ascii=False, default=str)
    except ErrorBandeja as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
`;
  async function cargarScript(url) {
    await new Promise((listo, falla) => {
      const s = document.createElement('script');
      s.src = url; s.onload = listo; s.onerror = () => falla(new Error('No se pudo cargar ' + url));
      document.head.appendChild(s);
    });
  }
  async function escribir(raiz, archivos) {
    for (const [ruta, contenido] of Object.entries(archivos)) {
      const completa = raiz + '/' + ruta;
      py.FS.mkdirTree(completa.slice(0, completa.lastIndexOf('/')));
      py.FS.writeFile(completa, contenido);
    }
  }
  const listo = (async () => {
    await cargarScript(SIDP.pyodide + 'pyodide.js');
    py = await loadPyodide({ indexURL: SIDP.pyodide });
    await py.loadPackage(['sqlite3', 'micropip']);
    try { await py.pyimport('micropip').install('pypdf'); } catch (e) { console.warn('Sin pypdf: los PDF no se leerán', e); }
    const [codigo, ejemplo] = await Promise.all(['codigo.json', 'ejemplo.json'].map((a) => fetch(a).then((r) => r.json())));
    await escribir('/sidp', codigo);
    await escribir('/demo', ejemplo);
    py.runPython(GLUE);
  })();
  async function llamar(nombre, ...argumentos) {
    await listo;
    const datos = JSON.parse(py.globals.get('llamar')(nombre, JSON.stringify(argumentos)));
    if (datos.error) throw new Error(datos.error);
    return datos.ok;
  }
  function base64(buffer) {
    let binario = '';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.length; i += 0x8000) binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(binario);
  }
  async function plantillaDemo(nombre, datos, archivos) {
    await listo;
    const lista = [];
    for (const archivo of archivos) lista.push({ nombre: archivo.name, contenido: base64(await archivo.arrayBuffer()) });
    const r = JSON.parse(py.globals.get('plantilla')(nombre, JSON.stringify(datos), JSON.stringify(lista)));
    if (r.error) throw new Error(r.error);
    return r.ok;
  }
  return {
    listo,
    estado: () => llamar('estado'),
    revisarTodo: () => llamar('revisar_todo'),
    detalle: (id) => llamar('detalle', id),
    decidir: (id, decision, motivo) => llamar('decidir', id, decision, motivo, 'administrador (demostración)'),
    reescribir: (id, captura, textos) => llamar('reescribir', id, captura, textos),
    archivoUrl: null,
    configuracion: null,
    inventario: null,
    analisisPC4: null,
    respaldar: null,
    guardarConfiguracion: null,
    base: () => llamar('base'),
    curps: () => llamar('curps'),
    constancia: async (archivo) => {
      await listo;
      const datos = JSON.parse(py.globals.get('constancia')(archivo.name, base64(await archivo.arrayBuffer())));
      if (datos.error) throw new Error(datos.error);
      return datos.ok;
    },
    renapoNoEncontrada: (alumno) => llamar('renapo_no_encontrada', alumno),
    escaneoLeer: async (archivos) => {
      await listo;
      const lista = [];
      for (const archivo of archivos) lista.push({ nombre: archivo.name, contenido: base64(await archivo.arrayBuffer()) });
      const datos = JSON.parse(py.globals.get('escaneo')(JSON.stringify(lista)));
      if (datos.error) throw new Error(datos.error);
      return datos.ok;
    },
    escaneoGuardar: (lote, datos) => llamar('escaneo_guardar', lote, datos, 'administrador (demostración)'),
    escaneoDescartar: (lote) => llamar('escaneo_descartar', lote),
    paginaUrl: null,
    documentosPadres: () => llamar('documentos_padres'),
    plantillas: () => llamar('lista_plantillas'),
    plantillaLeer: (archivos) => plantillaDemo('leer', null, archivos),
    plantillaGuardar: (datos, archivos = []) => plantillaDemo('guardar', datos, archivos),
    plantillaActiva: (clave, activa) => llamar('plantilla_activa', clave, activa, 'administrador (demostración)'),
    grupos: () => llamar('grupos_lista'),
    grupo: (id) => llamar('grupo_alumnos', id),
    buscarAlumno: (nombre, curp = '') => llamar('buscar_alumno', nombre, curp),
    listaLeer: async (archivos, texto, apellidosPrimero) => {
      await listo;
      const lista = [];
      for (const archivo of archivos) lista.push({ nombre: archivo.name, contenido: base64(await archivo.arrayBuffer()) });
      const r = JSON.parse(py.globals.get('lista')(JSON.stringify(lista), texto, apellidosPrimero));
      if (r.error) throw new Error(r.error);
      return r.ok;
    },
    listaGuardar: (datos) => llamar('lista_guardar', datos),
    listaTraer: async () => { throw new Error('En la demostración no hay PC 4: esto funciona en el .exe de la escuela.'); },
    grupoCrear: (grado, letra) => llamar('grupo_crear', grado, letra),
    ubicar: (alumnoId, grupoId, mismoQue) => llamar('ubicar_alumno', alumnoId, grupoId, mismoQue),
    analisis: () => llamar('analisis'),
    descargar: async (que, formato) => {
      await listo;
      const r = JSON.parse(py.globals.get('exportar')(que, formato));
      if (r.error) throw new Error(r.error);
      const bytes = Uint8Array.from(atob(r.ok.contenido), (c) => c.charCodeAt(0));
      const enlace = document.createElement('a');
      enlace.href = URL.createObjectURL(new Blob([bytes], { type: r.ok.tipo }));
      enlace.download = r.ok.nombre;
      document.body.appendChild(enlace); enlace.click(); enlace.remove();
    },
    muestraUrl: null,
    enviar: async (formulario) => {
      await listo;
      const archivos = [];
      for (const [campo, valor] of formulario.entries()) {
        if (valor instanceof File && valor.size) archivos.push({ espacio: campo, nombre: valor.name, contenido: base64(await valor.arrayBuffer()) });
      }
      const datos = JSON.parse(py.globals.get('recibir')(formulario.get('captura'), JSON.stringify(archivos)));
      if (datos.error) throw new Error(datos.error);
      return datos.ok;
    },
  };
}

function esc(texto) {
  return String(texto ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
