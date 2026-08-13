import streamlit as st
import stripe

# Cargar la clave secreta desde los Secrets de Streamlit
STRIPE_SECRET_KEY = st.secrets["STRIPE_SECRET_KEY"]

def es_pago_valido(codigo_pago: str) -> bool:
    """
    Verifica si un ID de pago de Stripe es válido.
    Para pases de 2,99 €, comprueba si Stripe ya lo tiene marcado como 'usado'.
    """
    codigo_pago = codigo_pago.strip()

    if not codigo_pago:
        return False

    # Validar prefijo oficial de Stripe
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
                # Comprobar pase individual de 2,99 €
                if monto in [299, 300]:
                    metadata = intent.metadata or {}
                    if metadata.get("usado") == "true":
                        st.sidebar.error("❌ Este pase de 2,99 € ya ha sido utilizado para crear un torneo.")
                        return False
                    return True

                # Pase PRO / Ilimitado de 11,99 € (siempre válido)
                elif monto in [1199, 1200]:
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
                if charge.amount in [299, 300]:
                    metadata = charge.metadata or {}
                    if metadata.get("usado") == "true":
                        st.sidebar.error("❌ Este pase de 2,99 € ya ha sido utilizado.")
                        return False
                    return True
                elif charge.amount in [1199, 1200]:
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
        st.sidebar.error(f"❌ Error al verificar pago: {str(e)}")
        return False

    return False


def marcar_como_usado(codigo_pago: str):
    """
    Guarda permanentemente en Stripe que el pase de 2,99 € ya fue consumido.
    Se debe llamar únicamente cuando el usuario genera/guarda con éxito su torneo.
    """
    codigo_pago = codigo_pago.strip()
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            if intent.amount in [299, 300]:
                stripe.PaymentIntent.modify(
                    codigo_pago,
                    metadata={"usado": "true"}
                )
        elif codigo_pago.startswith("ch_"):
            charge = stripe.Charge.retrieve(codigo_pago)
            if charge.amount in [299, 300]:
                stripe.Charge.modify(
                    codigo_pago,
                    metadata={"usado": "true"}
                )
    except Exception:
        # En caso de error de red secundario no bloqueamos al usuario
        pass