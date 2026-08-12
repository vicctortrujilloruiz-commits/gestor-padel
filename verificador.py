import os

ARCHIVO_USADOS = "pagos_usados.txt"

def es_pago_valido(pago_id):
    if not pago_id or len(pago_id) < 10:
        return False
    
    # Si el archivo no existe, lo creamos ahora mismo para evitar errores
    if not os.path.exists(ARCHIVO_USADOS):
        with open(ARCHIVO_USADOS, "w") as f:
            pass
        return True # El primer pago siempre será válido
        
    with open(ARCHIVO_USADOS, "r") as f:
        usados = f.read().splitlines()
    
    return pago_id not in usados

def marcar_como_usado(pago_id):
    with open(ARCHIVO_USADOS, "a") as f:
        f.write(pago_id.strip() + "\n")