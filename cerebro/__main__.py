"""Plan mínimo de un paso, reiniciable usando la misma clave."""
import argparse
import json
from comun import configuracion, red
from contratos.v1 import NuevaTarea


def main(argumentos=None):
    parser = argparse.ArgumentParser(prog='sidp cerebro', description="Crear un plan técnico SIDP de un paso")
    parser.add_argument("--clave", required=True, help="Reutilizar al reanudar el mismo plan")
    args = parser.parse_args(argumentos)
    paquete = configuracion.cargar_paquete()
    url, token = red.resolver('cerebro', paquete)
    with red.cliente(url, token, paquete) as cliente:
        respuesta = cliente.post('/api/v1/tareas', json=NuevaTarea(clave=args.clave).model_dump())
        respuesta.raise_for_status()
        print(json.dumps(respuesta.json(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
