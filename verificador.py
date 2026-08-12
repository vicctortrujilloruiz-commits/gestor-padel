import streamlit as st
import stripe

# Lee la clave de forma segura desde los Secretos de Streamlit
STRIPE_SECRET_KEY = st.secrets["STRIPE_SECRET_KEY"]

PAGOS_USADOS = set()

def es_pago_valido(codigo_pago: str) -> bool:
    codigo_pago = codigo_pago.strip()
    
    if codigo_pago in PAGOS_USADOS:
        return False

    if not (codigo_pago.startswith("pi_") or codigo_pago.startswith("ch_")):
        return False

    try:
        stripe.api_key = STRIPE_SECRET_KEY
        
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            
            if intent.status == "succeeded":
                monto = intent.amount  # Precio en céntimos (299 o 1199)
                
                # Licencia PRO Ilimitada (11.99€)
                if monto == 1199:
                    return True
                
                # Pase 1 Torneo (2.99€)
                elif monto == 299:
                    return True
                    
    except stripe.error.StripeError:
        return False

    return False

def marcar_como_usado(codigo_pago: str):
    codigo_pago = codigo_pago.strip()
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            if intent.amount == 299:
                PAGOS_USADOS.add(codigo_pago)
    except Exception:
        pass