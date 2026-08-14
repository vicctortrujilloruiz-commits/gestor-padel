import json
import streamlit as st
import stripe
from supabase import create_client, Client

STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def _codigo_ya_usado(codigo: str) -> bool:
    """Comprueba si un código de PASE INDIVIDUAL (2,99€) ya se usó."""
    supabase = get_supabase_client()
    try:
        resultado = (
            supabase.table("codigos_usados")
            .select("codigo")
            .eq("codigo", codigo)
            .execute()
        )
        return len(resultado.data) > 0
    except Exception:
        return False

def _verificar_licencia_pro(codigo: str, email_usuario: str) -> bool:
    """
    Lógica de la Licencia PRO (11,99€) contra la tabla `licencias_pro`.
    - Si el código NO existe: se registra {codigo, email} y se concede acceso.
    - Si YA existe: se concede acceso solo si el email coincide.
    """
    supabase = get_supabase_client()
    try:
        resultado = (
            supabase.table("licencias_pro")
            .select("*")
            .eq("codigo", codigo)
            .execute()
        )
        if not resultado.data:
            supabase.table("licencias_pro").insert({
                "codigo": codigo,
                "email": email_usuario
            }).execute()
            return True
        email_guardado = (resultado.data[0].get("email") or "").strip().lower()
        if email_guardado == email_usuario:
            return True
        st.sidebar.error("❌ Este código PRO pertenece a otro correo electrónico.")
        return False
    except Exception as e:
        st.sidebar.error(f"❌ Error en base de datos: {e}")
        return False

def es_pago_valido(codigo_pago: str, email_usuario: str = "") -> bool:
    """
    Verifica un código de Stripe:
    - 2,99 €: pi_/ch_ válido y no usado antes (tabla codigos_usados).
    - 11,99 €: pi_/ch_ válido; la propiedad del código la decide la tabla licencias_pro.
    """
    codigo_pago = codigo_pago.strip()
    email_usuario = email_usuario.strip().lower()
    if not codigo_pago:
        return False
    if not (codigo_pago.startswith("pi_") or codigo_pago.startswith("ch_")):
        st.sidebar.error("⚠️ Formato de código incorrecto. Debe empezar por 'pi_' o 'ch_'.")
        return False
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            estado = intent.status
            monto = intent.amount
        else:
            charge = stripe.Charge.retrieve(codigo_pago)
            estado = charge.status
            monto = charge.amount

        if estado != "succeeded":
            st.sidebar.error(f"⚠️ El pago figura en Stripe como: '{estado}'.")
            return False

        # --- PASE INDIVIDUAL: 2,99 € ---
        if monto in (299, 300):
            if _codigo_ya_usado(codigo_pago):
                st.sidebar.error("❌ Este código de pase ya ha sido utilizado.")
                return False
            return True

        # --- LICENCIA PRO: 11,99 € ---
        elif monto in (1199, 1200):
            if not email_usuario:
                st.sidebar.warning(
                    "📧 Las licencias PRO requieren introducir el correo "
                    "electrónico de la compra."
                )
                return False
            return _verificar_licencia_pro(codigo_pago, email_usuario)
        else:
            st.sidebar.error(f"⚠️ El importe ({monto / 100:.2f} €) no coincide con ningún plan.")
            return False
    except stripe.error.StripeError as e:
        st.sidebar.error(f"❌ Error de Stripe: {e.user_message or str(e)}")
        return False
    except Exception as e:
        st.sidebar.error(f"❌ Error al consultar Stripe/Supabase: {str(e)}")
        return False

def marcar_como_usado(codigo_pago: str):
    """
    Quema el código de PASE INDIVIDUAL (2,99€) justo después de generar el torneo.
    """
    try:
        supabase = get_supabase_client()
        supabase.table("codigos_usados").upsert({"codigo": codigo_pago}).execute()
    except Exception as e:
        st.sidebar.warning(f"⚠️ No se pudo registrar el código como usado: {e}")