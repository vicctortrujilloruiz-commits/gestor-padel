import streamlit as st
import stripe
import requests
import json

STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "")
WEBHOOK_GSHEET_URL = st.secrets.get("WEBHOOK_GSHEET_URL", "")

def obtener_codigos_usados_gsheet() -> set:
    """Lee la lista de códigos usados desde Google Sheets."""
    if not SHEET_ID:
        return set()
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            lineas = response.text.splitlines()
            codigos = {linea.replace('"', '').strip() for linea in lineas[1:] if linea.strip()}
            return codigos
    except Exception:
        pass
    return set()

def es_pago_valido(codigo_pago: str) -> bool:
    """
    Verifica si un ID de pago de Stripe es válido y no ha sido consumido.
    """
    codigo_pago = codigo_pago.strip()

    if not codigo_pago:
        return False

    # 1. Comprobar en Google Sheets si ya fue consumido antes
    codigos_usados = obtener_codigos_usados_gsheet()
    if codigo_pago in codigos_usados:
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
    Escribe el código usado en la hoja de Google Sheets vía Apps Script Webhook.
    Aplica únicamente a pases de 2,99 €.
    """
    codigo_pago = codigo_pago.strip()
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        es_individual = False
        
        if codigo_pago.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(codigo_pago)
            if intent.amount in [299, 300]:
                es_individual = True
        elif codigo_pago.startswith("ch_"):
            charge = stripe.Charge.retrieve(codigo_pago)
            if charge.amount in [299, 300]:
                es_individual = True

        # Si es de 2,99 €, enviamos la petición para escribir en Google Sheets
        if es_individual and WEBHOOK_GSHEET_URL:
            requests.post(
                WEBHOOK_GSHEET_URL,
                data=json.dumps({"codigo": codigo_pago}),
                headers={"Content-Type": "application/json"},
                timeout=5
            )
    except Exception:
        pass