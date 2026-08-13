import streamlit as st
import stripe

# Cargar la clave secreta desde los Secrets de Streamlit
STRIPE_SECRET_KEY = st.secrets["STRIPE_SECRET_KEY"]

def es_pago_valido(codigo_pago: str) -> bool:
    """
    Verifica si un ID de pago de Stripe es válido.
    Si es de 2,99 €, consulta en Stripe si ya fue marcado como 'usado'.
    """
    codigo_pago = codigo_pago.strip()

    if not codigo_pago:
        return False

    # Validar formato
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
                # Comprobar si el pase individual (2,99 € / 3,00 €) ya fue consumido en Stripe
                if monto in [299, 300]:
                    metadata = intent.metadata or {}
                    if metadata.get("usado") == "true":
                        st.sidebar.error("❌ Este pase de 2,99 € ya ha sido utilizado para crear un torneo.")
                        return False
                    return True

                # Pase PRO / Ilimitado (11,99 € / 12,00 €)
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
        st.sidebar.error(f"❌ Error interno de verificación: {str(e)}")
        return False

    return False


def marcar_como_usado(codigo_pago: str):
    """
    Escribe directamente en los metadatos del pago en Stripe 'usado = true'.
    Aplica únicamente a los pases de 2,99 €.
    """
    codigo_pago = codigo_pago.strip()
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            # Solo marcamos como usado si es el pase individual de 2,99 €
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
    except Exception as e:
        st.sidebar.warning(f"No se pudo actualizar el estado en Stripe: {str(e)}")