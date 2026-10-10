import httpx
import re

# ==========================================
# CONECTOR: VALIDACIÓN DE CURP (RENAPO)
# ==========================================

async def validar_curp_formato(curp: str) -> bool:
    """Valida mediante expresión regular que la CURP tenga la estructura oficial de 18 caracteres."""
    patron = r'^[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d$'
    return bool(re.match(patron, curp.upper()))

async def consultar_datos_renapo(curp: str) -> dict:
    """
    Se comunica con el servicio oficial para extraer datos.
    Sigue la regla: Un servicio caído produce "no disponible", no "documento falso".
    """
    curp = curp.upper()
    
    if not await validar_curp_formato(curp):
        return {"estado": "invalido", "mensaje": "El formato de la CURP es incorrecto."}

    # TODO: Aquí irá la petición real a la API gubernamental con httpx.
    # Por ahora simulamos el comportamiento para construir el flujo del sistema.
    
    # Simulación temporal para pruebas
    if curp.startswith("ERROR"):
        return {"estado": "no_disponible", "mensaje": "Servicio de RENAPO no responde."}
    
    # Simulación de un registro exitoso
    return {
        "estado": "exito",
        "datos": {
            "curp": curp,
            "nombre": "JUAN",
            "apellido_paterno": "PEREZ",
            "apellido_materno": "GARCIA",
            "sexo": "H",
            "fecha_nacimiento": "2010-05-15",
            "entidad_nacimiento": "DF"
        }
    }