import streamlit as st
import stripe

# Cargar la clave secreta desde los Secrets de Streamlit
STRIPE_SECRET_KEY = st.secrets["STRIPE_SECRET_KEY"]

def inicializar_estado():
    """Asegura que el conjunto de pagos usados exista en el session_state."""
    if "PAGOS_USADOS" not in st.session_state:
        st.session_state.PAGOS_USADOS = set()

def es_pago_valido(codigo_pago: str) -> bool:
    """
    Verifica si un ID de pago de Stripe es válido y no ha sido reutilizado.
    Soporta formatos pi_... y ch_...
    """
    inicializar_estado()
    
    # 1. Limpieza del código introducido
    codigo_pago = codigo_pago.strip()

    if not codigo_pago:
        return False

    # 2. Comprobar si ya se ha usado
    if codigo_pago in st.session_state.PAGOS_USADOS:
        st.sidebar.error("❌ Este código de solo 1 uso (2,99 €) ya ha sido consumido.")
        return False

    # 3. Validar el prefijo oficial de Stripe
    if not (codigo_pago.startswith("pi_") or codigo_pago.startswith("ch_")):
        st.sidebar.error("⚠️ Formato de código incorrecto. Debe empezar por 'pi_' o 'ch_'.")
        return False

    try:
        stripe.api_key = STRIPE_SECRET_KEY

        # 4. Consulta a la API de Stripe
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            estado = intent.status
            monto = intent.amount

            if estado == "succeeded":
                if monto in [299, 300, 1199, 1200]:
                    return True
                else:
                    st.sidebar.error(f"⚠️ El importe cobrado en Stripe ({monto / 100:.2f} €) no coincide con 2,99 € o 11,99 €.")
                    return False
            else:
                st.sidebar.error(f"⚠️ El pago figura en Stripe con estado: '{estado}'.")
                return False

        elif codigo_pago.startswith("ch_"):
            charge = stripe.Charge.retrieve(codigo_pago)
            if charge.status == "succeeded":
                if charge.amount in [299, 300, 1199, 1200]:
                    return True
                else:
                    st.sidebar.error(f"⚠️ El importe del cargo ({charge.amount / 100:.2f} €) no es válido.")
                    return False
            else:
                st.sidebar.error(f"⚠️ El cargo figura como: '{charge.status}'.")
                return False

    except stripe.error.StripeError as e:
        st.sidebar.error(f"❌ Error de Stripe: {e.user_message or str(e)}")
        return False
    except Exception as e:
        st.sidebar.error(f"❌ Error interno de verificación: {str(e)}")
        return False

    return False

def marcar_como_usado(codigo_pago: str):
    """
    Marca un código de 2,99 € como consumido para evitar que se vuelva a usar.
    """
    inicializar_estado()
    codigo_pago = codigo_pago.strip()
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            if intent.amount in [299, 300]:
                st.session_state.PAGOS_USADOS.add(codigo_pago)
        elif codigo_pago.startswith("ch_"):
            charge = stripe.Charge.retrieve(codigo_pago)
            if charge.amount in [299, 300]:
                st.session_state.PAGOS_USADOS.add(codigo_pago)
    except Exception:
        pass