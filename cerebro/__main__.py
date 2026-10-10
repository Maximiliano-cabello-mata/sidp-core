"""Plan mínimo de un paso, reiniciable usando la misma clave."""
import argparse
import os
import httpx
from contratos.v1 import NuevaTarea


def main():
    parser = argparse.ArgumentParser(description="Crear un plan técnico SIDP de un paso")
    parser.add_argument("--clave", required=True, help="Reutilizar al reanudar el mismo plan")
    args = parser.parse_args()
    with httpx.Client(base_url=os.environ.get("SIDP_URL", "http://127.0.0.1:8000"),
                      headers={"Authorization": "Bearer " + os.environ['SIDP_TOKEN']}, timeout=10) as cliente:
        respuesta = cliente.post('/api/v1/tareas', json=NuevaTarea(clave=args.clave).model_dump())
        respuesta.raise_for_status()
        print(respuesta.json())


if __name__ == '__main__':
    main()
