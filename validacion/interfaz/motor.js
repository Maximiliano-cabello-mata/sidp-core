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
  return {
    listo,
    estado: () => llamar('estado'),
    revisarTodo: () => llamar('revisar_todo'),
    detalle: (id) => llamar('detalle', id),
    decidir: (id, decision, motivo) => llamar('decidir', id, decision, motivo, 'administrador (demostración)'),
    reescribir: (id, captura, textos) => llamar('reescribir', id, captura, textos),
    archivoUrl: null,
    configuracion: null,
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
