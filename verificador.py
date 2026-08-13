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

# --- FUNCIONES PARA PASE INDIVIDUAL (2,99 €) ---

def es_codigo_usado(codigo: str) -> bool:
    """Consulta en Supabase si el código de 2,99 € ya fue registrado/quemado."""
    supabase = get_supabase_client()
    if not supabase:
        return False
    try:
        res = supabase.table("codigos_usados").select("codigo").eq("codigo", codigo).execute()
        return len(res.data) > 0
    except Exception:
        return False

def registrar_codigo_consumido(codigo: str):
    """Guarda inmediatamente el código consumido de 2,99 € en Supabase."""
    supabase = get_supabase_client()
    if not supabase:
        return
    try:
        supabase.table("codigos_usados").insert({"codigo": codigo}).execute()
    except Exception:
        pass

# --- FUNCIONES PARA LICENCIA PRO ANTI-COMPARTIR (11,99 €) ---

def validar_o_registrar_licencia_pro(codigo: str, dispositivo_id: str) -> tuple[bool, str]:
    """
    Comprueba si una licencia PRO (11,99 €) ya está vinculada a un dispositivo.
    Si es la primera vez que se usa, la vincula al dispositivo actual.
    Retorna (es_valido, mensaje_error)
    """
    supabase = get_supabase_client()
    if not supabase:
        return True, "" # Si falla Supabase, permite el paso temporalmente

    try:
        res = supabase.table("licencias_pro").select("dispositivo_id").eq("codigo", codigo).execute()
        
        # Si la licencia ya fue activada en la base de datos
        if len(res.data) > 0:
            dispositivo_registrado = res.data[0].get("dispositivo_id")
            if dispositivo_registrado == dispositivo_id:
                return True, ""
            else:
                return False, "❌ Esta licencia PRO ya está activa en otro dispositivo."
        else:
            # Es la primera vez que se introduce: la vinculamos a este dispositivo
            supabase.table("licencias_pro").insert({"codigo": codigo, "dispositivo_id": dispositivo_id}).execute()
            return True, ""
    except Exception as e:
        return True, ""

# --- VALIDACIÓN PRINCIPAL DE PAGOS EN STRIPE ---

def es_pago_valido(codigo_pago: str, dispositivo_id: str = "default_device") -> bool:
    """
    Verifica si un ID de pago de Stripe es válido.
    - Si es de 2,99 €: se quema en Supabase.
    - Si es de 11,99 €: se vincula a 1 solo dispositivo en Supabase.
    """
    codigo_pago = codigo_pago.strip()

    if not codigo_pago:
        return False

    # 1. Comprobar si es un pago individual de 2,99 € ya consumido
    if es_codigo_usado(codigo_pago):
        st.sidebar.error("❌ Este código de 2,99 € ya ha sido utilizado para crear un torneo.")
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
                # Pase individual (2,99 €)
                if monto in [299, 300]:
                    registrar_codigo_consumido(codigo_pago)
                    return True
                # Licencia PRO (11,99 €) -> Control anti-compartir por dispositivo
                elif monto in [1199, 1200]:
                    valido, msg = validar_o_registrar_licencia_pro(codigo_pago, dispositivo_id)
                    if not valido:
                        st.sidebar.error(msg)
                        return False
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
                    valido, msg = validar_o_registrar_licencia_pro(codigo_pago, dispositivo_id)
                    if not valido:
                        st.sidebar.error(msg)
                        return False
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

def es_licencia_pro(codigo_pago: str) -> bool:
    """Comprueba si un código pertenece a una licencia PRO de 11,99 €."""
    codigo_pago = codigo_pago.strip()
    if not codigo_pago:
        return False
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            return intent.amount in [1199, 1200]
        elif codigo_pago.startswith("ch_"):
            charge = stripe.Charge.retrieve(codigo_pago)
            return charge.amount in [1199, 1200]
    except Exception:
        pass
    return False

def marcar_como_usado(codigo_pago: str):
    """Función de compatibilidad."""
    pass