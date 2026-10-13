"""Plan mínimo de un paso, reiniciable usando la misma clave."""
import argparse
import json
import hashlib
import time
import httpx
from comun import configuracion, red, rutas
from comun.politicas import espera_reintento
from cerebro.observador import Observador
from contratos.v1 import NuevaTarea


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='sidp cerebro', description="Crear un plan técnico SIDP de un paso")
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--clave", help="Reutilizar al reanudar el mismo plan")
    modo.add_argument("--servicio", action='store_true', help='Observar eventos propios con cursor durable')
    args = parser.parse_args(argumentos)
    paquete = configuracion.cargar_paquete()
    url, token = red.resolver('cerebro', paquete)
    with red.cliente(url, token, paquete) as cliente:
        if args.servicio:
            directorio = rutas.hogar() / 'cerebro'
            directorio.mkdir(parents=True, exist_ok=True)
            # Separar instalaciones e identidades sin guardar credenciales en el diario.
            flujo = hashlib.sha256(((paquete.instalacion if paquete else url) + ':' + token).encode()).hexdigest()
            observador = Observador(directorio / 'eventos.db', flujo)
            fallos = 0
            while True:
                try:
                    cantidad = observador.ciclo(cliente)
                    fallos = 0
                    time.sleep(0.5 if cantidad == 100 else 5)
                except httpx.HTTPStatusError as error:
                    if error.response.status_code in (401, 403):
                        raise SystemExit(3) from error
                    fallos += 1
                    time.sleep(espera_reintento(fallos))
                except httpx.TransportError:
                    fallos += 1
                    time.sleep(espera_reintento(fallos))
        respuesta = cliente.post('/api/v1/tareas', json=NuevaTarea(clave=args.clave).model_dump(exclude_none=True))
        respuesta.raise_for_status()
        print(json.dumps(respuesta.json(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

