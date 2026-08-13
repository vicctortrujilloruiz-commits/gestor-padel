import streamlit as st
import stripe

# Cargar la clave secreta desde los Secrets de Streamlit
STRIPE_SECRET_KEY = st.secrets["STRIPE_SECRET_KEY"]

def _inicializar_memoria():
    """Asegura que el conjunto de pagos usados exista en session_state."""
    if "PAGOS_USADOS" not in st.session_state:
        st.session_state.PAGOS_USADOS = set()

def es_pago_valido(codigo_pago: str) -> bool:
    """
    Verifica si un ID de pago de Stripe es válido y no ha sido reutilizado.
    Soporta formatos pi_... y ch_...
    """
    _inicializar_memoria()
    codigo_pago = codigo_pago.strip()

    if not codigo_pago:
        return False

    # 1. Comprobar si ya se ha usado en esta sesión
    if codigo_pago in st.session_state.PAGOS_USADOS:
        st.sidebar.error("❌ Este código de 2,99 € ya ha sido utilizado.")
        return False

    # 2. Validar el formato
    if not (codigo_pago.startswith("pi_") or codigo_pago.startswith("ch_")):
        st.sidebar.error("⚠️ Formato de código incorrecto. Debe empezar por 'pi_' o 'ch_'.")
        return False

    try:
        stripe.api_key = STRIPE_SECRET_KEY

        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            estado = intent.status
            monto = intent.amount  # Importe en céntimos

            if estado == "succeeded":
                if monto in [299, 300, 1199, 1200]:
                    return True
                else:
                    st.sidebar.error(f"⚠️ El importe del pago ({monto / 100:.2f} €) no coincide con 2,99 € ni 11,99 €.")
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
        st.sidebar.error(f"❌ Error al consultar Stripe: {str(e)}")
        return False

    return False


def marcar_como_usado(codigo_pago: str):
    """
    Marca un código de 2,99 € como consumido durante la sesión.
    Los códigos de 11,99 € (PRO) no se marcan para uso ilimitado.
    """
    _inicializar_memoria()
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