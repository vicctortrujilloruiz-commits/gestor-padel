import stripe

# 🔑 Reemplaza esto con tu Clave Secreta de Stripe
# La encuentras en Stripe -> Desarrolladores -> Claves de API -> Clave secreta (comienza por sk_test_ o sk_live_)
STRIPE_SECRET_KEY = "sk_test_tu_clave_secreta_aqui" 

# Lista en memoria para los códigos de 2.99€ que ya se han usado
PAGOS_USADOS = set()

def es_pago_valido(codigo_pago: str) -> bool:
    """
    Se conecta a Stripe y comprueba si el código 'pi_...' existe y fue pagado.
    """
    codigo_pago = codigo_pago.strip()
    
    # 1. Si el código ya se usó anteriormente en esta sesión, lo rechaza
    if codigo_pago in PAGOS_USADOS:
        return False

    # 2. Si ni siquiera empieza por 'pi_' o 'ch_', es falso directamente
    if not (codigo_pago.startswith("pi_") or codigo_pago.startswith("ch_")):
        return False

    try:
        stripe.api_key = STRIPE_SECRET_KEY
        
        # 3. Consultar directamente a la API de Stripe
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            # Retorna True SOLO si el pago se completó con éxito
            return intent.status == "succeeded"
            
    except stripe.error.StripeError:
        # Si el código inventado no existe en Stripe, saltará esta excepción
        return False

    return False

def marcar_como_usado(codigo_pago: str):
    """
    Registra el código como consumido.
    """
    codigo_pago = codigo_pago.strip()
    PAGOS_USADOS.add(codigo_pago)