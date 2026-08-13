import streamlit as st
import stripe
from supabase import create_client, Client

STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def get_supabase_client() -> Client:
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

def es_codigo_usado(codigo: str) -> bool:
    """Consulta en Supabase si el código de 2,99 € ya fue registrado."""
    supabase = get_supabase_client()
    if not supabase:
        return False
    try:
        res = supabase.table("codigos_usados").select("codigo").eq("codigo", codigo).execute()
        return len(res.data) > 0
    except Exception:
        return False

def registrar_codigo_consumido(codigo: str):
    """Guarda inmediatamente el código consumido en Supabase."""
    supabase = get_supabase_client()
    if not supabase:
        return
    try:
        supabase.table("codigos_usados").insert({"codigo": codigo}).execute()
    except Exception:
        pass

def es_pago_valido(codigo_pago: str) -> bool:
    """
    Verifica si un ID de pago de Stripe es válido y no ha sido utilizado.
    Si es de 2,99 € y es válido, lo consume inmediatamente en la base de datos.
    """
    codigo_pago = codigo_pago.strip()

    if not codigo_pago:
        return False

    # 1. Comprobar si ya fue registrado previamente en Supabase
    if es_codigo_usado(codigo_pago):
        st.sidebar.error("❌ Este código de 2,99 € ya ha sido utilizado.")
        return False

    # 2. Validar formato de Stripe
    if not (codigo_pago.startswith("pi_") or codigo_pago.startswith("ch_")):
        st.sidebar.error("⚠️ Formato de código incorrecto. Debe empezar por 'pi_' o 'ch_'.")
        return False

    try:
        stripe.api_key = STRIPE_SECRET_KEY

        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            estado = intent.status
            monto = intent.amount

            if estado == "succeeded":
                # Si es pase individual de 2,99 € / 3,00 €
                if monto in [299, 300]:
                    registrar_codigo_consumido(codigo_pago)
                    return True
                # Si es pase ilimitado/Pro de 11,99 €
                elif monto in [1199, 1200]:
                    return True
                else:
                    st.sidebar.error(f"⚠️ El importe ({monto / 100:.2f} €) no coincide con 2,99 € ni 11,99 €.")
                    return False
            else:
                st.sidebar.error(f"⚠️ El pago figura en Stripe con estado: '{estado}'.")
                return False

        elif codigo_pago.startswith("ch_"):
            charge = stripe.Charge.retrieve(codigo_pago)
            if charge.status == "succeeded":
                if charge.amount in [299, 300]:
                    registrar_codigo_consumido(codigo_pago)
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
        st.sidebar.error(f"❌ Error al consultar Stripe: {str(e)}")
        return False

    return False

def marcar_como_usado(codigo_pago: str):
    """Función de compatibilidad por si se invoca desde app.py."""
    pass