import streamlit as st
import stripe

STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")

def es_pago_valido(codigo_pago: str, email_usuario: str = "") -> bool:
    """
    Verifica un código de Stripe:
    - 2,99 €: Requiere código pi_... / ch_...
    - 11,99 €: Requiere código pi_... / ch_... Y que el email coincida con el pagador en Stripe.
    """
    codigo_pago = codigo_pago.strip()
    email_usuario = email_usuario.strip().lower()

    if not codigo_pago:
        return False

    # 1. Validar formato básico
    if not (codigo_pago.startswith("pi_") or codigo_pago.startswith("ch_")):
        st.sidebar.error("⚠️ Formato de código incorrecto. Debe empezar por 'pi_' o 'ch_'.")
        return False

    try:
        stripe.api_key = STRIPE_SECRET_KEY

        # --- PAYMENT INTENTS (pi_) ---
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            estado = intent.status
            monto = intent.amount

            if estado == "succeeded":
                # Pase Individual (2,99 €)
                if monto in [299, 300]:
                    return True

                # Licencia PRO (11,99 €)
                elif monto in [1199, 1200]:
                    if not email_usuario:
                        st.sidebar.warning("📧 Las licencias PRO requieren introducir el correo electrónico del comprador.")
                        return False

                    # Recuperar email de Stripe (customer o receipt_email)
                    email_stripe = ""
                    if intent.receipt_email:
                        email_stripe = intent.receipt_email.strip().lower()
                    elif intent.customer:
                        customer = stripe.Customer.retrieve(intent.customer)
                        email_stripe = (customer.email or "").strip().lower()

                    if email_stripe and email_stripe == email_usuario:
                        return True
                    else:
                        st.sidebar.error("❌ El correo introducido no coincide con el comprador de esta licencia PRO.")
                        return False
                else:
                    st.sidebar.error(f"⚠️ El importe ({monto / 100:.2f} €) no coincide con ningún plan.")
                    return False
            else:
                st.sidebar.error(f"⚠️ El pago figura en Stripe como: '{estado}'.")
                return False

        # --- CHARGES (ch_) ---
        elif codigo_pago.startswith("ch_"):
            charge = stripe.Charge.retrieve(codigo_pago)
            if charge.status == "succeeded":
                if charge.amount in [299, 300]:
                    return True
                elif charge.amount in [1199, 1200]:
                    if not email_usuario:
                        st.sidebar.warning("📧 Las licencias PRO requieren el correo del comprador.")
                        return False

                    email_stripe = (charge.billing_details.email or charge.receipt_email or "").strip().lower()
                    if email_stripe and email_stripe == email_usuario:
                        return True
                    else:
                        st.sidebar.error("❌ El correo introducido no coincide con el comprador de esta licencia PRO.")
                        return False
                else:
                    st.sidebar.error(f"⚠️ Importe del cargo ({charge.amount / 100:.2f} €) no válido.")
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
    pass