import random
import math
import uuid
import json
import io
import os
import tempfile
from datetime import datetime, timedelta, time as dt_time
import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import verificador

# ==================================================================
# CONFIGURACIÓN DE LA PÁGINA
# ==================================================================
st.set_page_config(
    page_title="GeneradorPadel | Cuadros y Horarios Automáticos",
    page_icon="🎾",
    layout="wide"
)

STRIPE_LINK_PASE_1_TORNEO = "https://buy.stripe.com/aFabJ18hJ7HGdoVeWNfbq00"
STRIPE_LINK_PRO_ILIMITADA = "https://buy.stripe.com/7sYcN555x7HG5WtaGxfbq01"
LIMITE_PAREJAS_GRATIS = 8
LIMITE_PISTAS_GRATIS = 2

def es_plan_gratuito(num_parejas, num_pistas, restricciones_horarias):
    return (num_parejas <= LIMITE_PAREJAS_GRATIS and num_pistas <= LIMITE_PISTAS_GRATIS and not restricciones_horarias)

def mostrar_paywall():
    if st.session_state.get('acceso_pro', False):
        return True
    st.sidebar.warning("🔒 Has superado los límites del **Plan Gratuito**. Elige una opción PRO:")
    col1, col2 = st.sidebar.columns(2)
    with col1: 
        st.markdown(f'<a href="{STRIPE_LINK_PASE_1_TORNEO}" target="_blank" style="display: block; text-align: center; background-color: #2563eb; color: #ffffff; padding: 10px 6px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 13px;">🎟️ Pase 1 Torneo</a>', unsafe_allow_html=True)
    with col2: 
        st.markdown(f'<a href="{STRIPE_LINK_PRO_ILIMITADA}" target="_blank" style="display: block; text-align: center; background-color: #7c3aed; color: #ffffff; padding: 10px 6px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 13px;">⭐ Licencia Pro</a>', unsafe_allow_html=True)
    codigo = st.sidebar.text_input("🔑 Código de acceso (ID de pago):", key="cod_input").strip()
    email = st.sidebar.text_input("📧 Correo de la compra (solo si es Licencia PRO):", key="email_input").strip()
    if codigo:
        clave_verificacion = f"{codigo}|{email.lower()}"
        if st.session_state.get('ultimo_codigo_fallido') == clave_verificacion:
            return False
        if verificador.es_pago_valido(codigo, email):
            st.session_state['codigo_verificado'] = codigo
            st.session_state['acceso_pro'] = True
            st.sidebar.success("✅ ¡Acceso verificado!")
            return True
        else:
            st.session_state['ultimo_codigo_fallido'] = clave_verificacion
    return False

# ==================================================================
# 1. DISPONIBILIDAD Y SLOTS HORARIOS
# ==================================================================
def pareja_disponible(idx, dia_partido, hora_inicio_partido, hora_fin_partido, restricciones):
    if idx not in restricciones:
        return True
    lista_restricciones = restricciones[idx]
    for restriccion in lista_restricciones:
        dia_restringido = restriccion["dia"]
        if dia_restringido != "Todos" and dia_restringido != dia_partido:
            continue
        bloqueado_desde = restriccion["desde"]
        bloqueado_hasta = restriccion["hasta"]
        hay_solape = (
            hora_inicio_partido.time() < bloqueado_hasta
            and hora_fin_partido.time() > bloqueado_desde
        )
        if hay_solape:
            return False
    return True

def obtener_slots(dias, duracion):
    slots = []
    for dia in dias:
        for franja in dia["franjas"]:
            actual = franja["inicio"]
            while actual + timedelta(minutes=duracion) <= franja["fin"]:
                slots.append({
                    "dia": dia["etiqueta"],
                    "hora": actual
                })
                actual += timedelta(minutes=duracion)
    return slots

def calcular_capacidad(dias, pistas, duracion):
    slots = obtener_slots(dias, duracion)
    return len(slots) * len(pistas)

def calcular_tamano_cuadro(num_parejas):
    equipos = 1
    while equipos * 2 <= num_parejas:
        equipos *= 2
    return equipos

def nombre_ronda(num_equipos):
    nombres = {
        64: "🎯 TREINTAIDOSAVOS DE FINAL",
        32: "🎯 DIECISEISAVOS DE FINAL",
        16: "🎯 OCTAVOS DE FINAL",
        8: "🎯 CUARTOS DE FINAL",
        4: "🥈 SEMIFINALES",
        2: "🏆 FINAL"
    }
    return nombres.get(num_equipos, "🎯 FASE ELIMINATORIA")

def generar_todos_enfrentamientos(num_parejas):
    partidos = []
    for i in range(num_parejas):
        for j in range(i + 1, num_parejas):
            partidos.append((i, j))
    return partidos

def seleccionar_partidos_previos(num_parejas, cantidad):
    todos = generar_todos_enfrentamientos(num_parejas)
    seleccionados = []
    partidos_por_pareja = {i: 0 for i in range(num_parejas)}
    while todos and len(seleccionados) < cantidad:
        candidatos = []
        for partido in todos:
            a, b = partido
            max_partidos = max(partidos_por_pareja[a], partidos_por_pareja[b])
            suma_partidos = partidos_por_pareja[a] + partidos_por_pareja[b]
            candidatos.append((max_partidos, suma_partidos, random.random(), partido))
        candidatos.sort(key=lambda x: (x[0], x[1], x[2]))
        partido_elegido = candidatos[0][3]
        seleccionados.append(partido_elegido)
        todos.remove(partido_elegido)
        a, b = partido_elegido
        partidos_por_pareja[a] += 1
        partidos_por_pareja[b] += 1
    return seleccionados, partidos_por_pareja

def agrupar_en_rondas(partidos, num_parejas):
    pendientes = partidos.copy()
    rondas = []
    while pendientes:
        usados = set()
        ronda = []
        restantes = []
        for partido in pendientes:
            a, b = partido
            if a not in usados and b not in usados:
                ronda.append(partido)
                usados.add(a)
                usados.add(b)
            else:
                restantes.append(partido)
        if not ronda:
            break
        descansan = [i for i in range(num_parejas) if i not in usados]
        rondas.append({
            "enfrentamientos": ronda,
            "descansan": descansan
        })
        pendientes = restantes
    return rondas

def asignar_horarios(rondas, parejas, pistas, dias, duracion, restricciones, start_slot_index=0):
    slots = obtener_slots(dias, duracion)
    rondas_programadas = []
    slot_index = start_slot_index
    partidos_sin_hueco = []
    for numero_ronda, ronda in enumerate(rondas, start=1):
        pendientes = ronda["enfrentamientos"].copy()
        partidos_ronda = []
        while pendientes:
            if slot_index >= len(slots):
                for partido in pendientes:
                    a, b = partido
                    partidos_sin_hueco.append((numero_ronda, a, b))
                pendientes = []
                break
            slot = slots[slot_index]
            hora_inicio = slot["hora"]
            hora_fin = hora_inicio + timedelta(minutes=duracion)
            asignados_este_slot = []
            for pista in pistas:
                if not pendientes:
                    break
                partido_elegido = None
                for partido in pendientes:
                    a, b = partido
                    disponibles = (
                        pareja_disponible(a, slot["dia"], hora_inicio, hora_fin, restricciones)
                        and
                        pareja_disponible(b, slot["dia"], hora_inicio, hora_fin, restricciones)
                    )
                    if disponibles:
                        partido_elegido = partido
                        break
                if partido_elegido is None:
                    continue
                pendientes.remove(partido_elegido)
                a, b = partido_elegido
                asignados_este_slot.append({
                    "pista": pista,
                    "dia": slot["dia"],
                    "hora": hora_inicio.strftime("%H:%M"),
                    "idx_a": a,
                    "idx_b": b,
                    "pareja_a": parejas[a] if a is not None else ("-", "-"),
                    "pareja_b": parejas[b] if b is not None else ("-", "-"),
                    "sets_a": None,
                    "sets_b": None,
                    "juegos_a": None,
                    "juegos_b": None
                })
            partidos_ronda.extend(asignados_este_slot)
            slot_index += 1
        descansan_nombres = [
            f"{parejas[idx][0]}/{parejas[idx][1]}"
            for idx in ronda.get("descansan", [])
            if idx < len(parejas)
        ]
        rondas_programadas.append({
            "partidos": partidos_ronda,
            "descansan": descansan_nombres
        })
    return rondas_programadas, partidos_sin_hueco, slot_index

# ==================================================================
# 2. VALIDACIÓN DE SETS Y RESULTADOS
# ==================================================================
def set_valido(a, b):
    if a == 6 and 0 <= b <= 4:
        return True
    if b == 6 and 0 <= a <= 4:
        return True
    if a == 7 and b in (5, 6):
        return True
    if b == 7 and a in (5, 6):
        return True
    return False

@st.cache_data
def opciones_set():
    opciones = []
    for a in range(0, 8):
        for b in range(0, 8):
            if set_valido(a, b):
                opciones.append(f"{a}-{b}")
    return sorted(opciones, key=lambda s: (-max(int(x) for x in s.split("-")), s))

def procesar_resultado_partido(set1, set2, set3):
    def parse(s):
        a, b = s.split("-")
        return int(a), int(b)
    sets_a, sets_b, juegos_a, juegos_b = 0, 0, 0, 0
    a1, b1 = parse(set1)
    juegos_a += a1; juegos_b += b1
    if a1 > b1: sets_a += 1
    else: sets_b += 1

    a2, b2 = parse(set2)
    juegos_a += a2; juegos_b += b2
    if a2 > b2: sets_a += 1
    else: sets_b += 1

    if sets_a == 1 and sets_b == 1:
        if not set3:
            return None
        a3, b3 = parse(set3)
        juegos_a += a3; juegos_b += b3
        if a3 > b3: sets_a += 1
        else: sets_b += 1

    ganador = "a" if sets_a > sets_b else "b"
    return {
        "sets_a": sets_a,
        "sets_b": sets_b,
        "juegos_a": juegos_a,
        "juegos_b": juegos_b,
        "ganador": ganador
    }

# ==================================================================
# 3. CLASIFICACIÓN CON ENFRENTAMIENTO DIRECTO (HEAD-TO-HEAD)
# ==================================================================
def calcular_clasificacion(rondas_programadas, parejas):
    stats = {
        idx: {
            "partidos": 0, "victorias": 0, "derrotas": 0,
            "sets_ganados": 0, "sets_perdidos": 0,
            "juegos_ganados": 0, "juegos_perdidos": 0,
            "enfrentamientos_directos": {}
        }
        for idx in range(len(parejas))
    }
    for ronda in rondas_programadas:
        for partido in ronda["partidos"]:
            if partido["sets_a"] is None:
                continue
            idx_a = partido["idx_a"]
            idx_b = partido["idx_b"]
            sets_a, sets_b = partido["sets_a"], partido["sets_b"]
            juegos_a, juegos_b = partido["juegos_a"], partido["juegos_b"]
            
            stats[idx_a]["partidos"] += 1
            stats[idx_b]["partidos"] += 1
            stats[idx_a]["sets_ganados"] += sets_a
            stats[idx_a]["sets_perdidos"] += sets_b
            stats[idx_b]["sets_ganados"] += sets_b
            stats[idx_b]["sets_perdidos"] += sets_a
            stats[idx_a]["juegos_ganados"] += juegos_a
            stats[idx_a]["juegos_perdidos"] += juegos_b
            stats[idx_b]["juegos_ganados"] += juegos_b
            stats[idx_b]["juegos_perdidos"] += juegos_a

            if sets_a > sets_b:
                stats[idx_a]["victorias"] += 1
                stats[idx_b]["derrotas"] += 1
                stats[idx_a]["enfrentamientos_directos"][idx_b] = 1
                stats[idx_b]["enfrentamientos_directos"][idx_a] = -1
            else:
                stats[idx_b]["victorias"] += 1
                stats[idx_a]["derrotas"] += 1
                stats[idx_b]["enfrentamientos_directos"][idx_a] = 1
                stats[idx_a]["enfrentamientos_directos"][idx_b] = -1

    clasificacion = []
    for idx in range(len(parejas)):
        s = stats[idx]
        clasificacion.append({
            "idx": idx,
            "pareja": parejas[idx],
            "partidos": s["partidos"],
            "victorias": s["victorias"],
            "derrotas": s["derrotas"],
            "sets_ganados": s["sets_ganados"],
            "sets_perdidos": s["sets_perdidos"],
            "diferencia_sets": s["sets_ganados"] - s["sets_perdidos"],
            "juegos_ganados": s["juegos_ganados"],
            "juegos_perdidos": s["juegos_perdidos"],
            "diferencia_juegos": s["juegos_ganados"] - s["juegos_perdidos"],
            "_h2h": s["enfrentamientos_directos"]
        })

    # Criterio de ordenación: Victorias > Dif.Sets > Dif.Juegos > Juegos Ganados
    clasificacion.sort(
        key=lambda x: (
            -x["victorias"],
            -x["diferencia_sets"],
            -x["diferencia_juegos"],
            -x["juegos_ganados"]
        )
    )

    # Desempate Head-to-Head para parejas adyacentes con empate total
    for i in range(len(clasificacion) - 1):
        actual = clasificacion[i]
        siguiente = clasificacion[i+1]
        if (actual["victorias"] == siguiente["victorias"] and
            actual["diferencia_sets"] == siguiente["diferencia_sets"] and
            actual["diferencia_juegos"] == siguiente["diferencia_juegos"] and
            actual["juegos_ganados"] == siguiente["juegos_ganados"]):
            # Mirar si jugaron entre ellos
            if actual["_h2h"].get(siguiente["idx"], 0) == -1:
                # El siguiente le ganó el duelo directo -> intercambiar
                clasificacion[i], clasificacion[i+1] = clasificacion[i+1], clasificacion[i]

    return clasificacion

def seleccionar_clasificados(clasificacion, tamano_cuadro):
    return list(clasificacion[:tamano_cuadro]), list(clasificacion[tamano_cuadro:])

# ==================================================================
# 4. GENERACIÓN DE PDF PROFESIONAL DEL TORNEO (FPDF2)
# ==================================================================
class PDFTorneo(FPDF):
    def __init__(self, logo_bytes=None):
        super().__init__()
        self.logo_bytes = logo_bytes

    def header(self):
        if self.logo_bytes:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(self.logo_bytes)
                    tmp_path = tmp.name
                self.image(tmp_path, 10, 8, 24)
                os.unlink(tmp_path)
            except Exception:
                pass
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 41, 59)
        self.cell(0, 10, "CUADRO OFICIAL Y HORARIOS DEL TORNEO", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(100, 116, 139)
        self.cell(0, 6, f"Generado con GeneradorPadel · {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

def exportar_cuadro_pdf():
    logo_data = st.session_state.get("logo_torneo_bytes", None)
    pdf = PDFTorneo(logo_bytes=logo_data)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Resumen del Torneo
    pdf.set_fill_color(241, 245, 249)
    pdf.rect(10, pdf.get_y(), 190, 20, "F")
    pdf.set_xy(12, pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    formato_info = st.session_state.get("formato", {})
    tipo_txt = formato_info.get("tipo", "Torneo").upper()
    pdf.cell(90, 6, f"Formato: {tipo_txt}")
    pdf.cell(90, 6, f"Parejas: {len(st.session_state.parejas)}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(90, 6, f"Pistas: {len(st.session_state.pistas)} ({', '.join(st.session_state.pistas)})")
    pdf.cell(90, 6, f"Duracion partido: {st.session_state.duracion} min", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Fase Previa / Partidos
    rondas = st.session_state.get("rondas_programadas", [])
    if rondas:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(37, 99, 235)
        pdf.cell(0, 8, "PARTIDOS DE LA FASE PREVIA / LIGUILLA", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for num_r, r in enumerate(rondas, start=1):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(226, 232, 240)
            pdf.cell(0, 7, f" Ronda {num_r}", fill=True, new_x="LMARGIN", new_y="NEXT")
            
            # Tabla de partidos
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(248, 250, 252)
            pdf.cell(20, 6, "Dia", border=1, fill=True)
            pdf.cell(16, 6, "Hora", border=1, fill=True)
            pdf.cell(24, 6, "Pista", border=1, fill=True)
            pdf.cell(55, 6, "Pareja A", border=1, fill=True)
            pdf.cell(55, 6, "Pareja B", border=1, fill=True)
            pdf.cell(20, 6, "Resultado", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 8.5)
            for p in r.get("partidos", []):
                res_txt = f"{p['sets_a']}-{p['sets_b']}" if p.get("sets_a") is not None else "Pendiente"
                pa = f"{p['pareja_a'][0]}/{p['pareja_a'][1]}"
                pb = f"{p['pareja_b'][0]}/{p['pareja_b'][1]}"
                pdf.cell(20, 6, str(p.get("dia", "-")), border=1)
                pdf.cell(16, 6, str(p.get("hora", "-")), border=1)
                pdf.cell(24, 6, str(p.get("pista", "-")), border=1)
                pdf.cell(55, 6, pa[:28], border=1)
                pdf.cell(55, 6, pb[:28], border=1)
                pdf.cell(20, 6, res_txt, border=1, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    # Fase Eliminatoria
    partidos_elim = st.session_state.get("partidos_ronda_actual", [])
    if partidos_elim:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(124, 58, 237)
        ronda_tit = nombre_ronda(len(st.session_state.get("cuadro_actual", [])))
        pdf.cell(0, 8, f"CUADRO ELIMINATORIO ({ronda_tit})", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(248, 250, 252)
        pdf.cell(20, 6, "Dia", border=1, fill=True)
        pdf.cell(16, 6, "Hora", border=1, fill=True)
        pdf.cell(24, 6, "Pista", border=1, fill=True)
        pdf.cell(55, 6, "Pareja A", border=1, fill=True)
        pdf.cell(55, 6, "Pareja B", border=1, fill=True)
        pdf.cell(20, 6, "Resultado", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 8.5)
        for p in partidos_elim:
            res_txt = f"{p['sets_a']}-{p['sets_b']}" if p.get("sets_a") is not None else "Por jugar"
            pa = f"{p['pareja_a'][0]}/{p['pareja_a'][1]}"
            pb = f"{p['pareja_b'][0]}/{p['pareja_b'][1]}"
            pdf.cell(20, 6, str(p.get("dia", "-")), border=1)
            pdf.cell(16, 6, str(p.get("hora", "-")), border=1)
            pdf.cell(24, 6, str(p.get("pista", "-")), border=1)
            pdf.cell(55, 6, pa[:28], border=1)
            pdf.cell(55, 6, pb[:28], border=1)
            pdf.cell(20, 6, res_txt, border=1, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())

# ==================================================================
# 5. ESTADO DE LA SESIÓN Y SERIALIZACIÓN (.JSON)
# ==================================================================
CAMPOS_TORNEO = [
    "etapa", "parejas", "restricciones", "pistas", "dias", "duracion",
    "formato", "partidos_por_pareja", "rondas_programadas",
    "partidos_sin_hueco", "clasificacion", "clasificados",
    "eliminados_previa", "cuadro_actual", "ronda_eliminatoria_num",
    "partidos_ronda_actual", "partidos_ronda_actual_num", "campeon",
    "liguilla_partido", "liguilla_campeon", "slot_index_acumulado"
]

def _serializar_valor(valor):
    if isinstance(valor, datetime):
        return {"__tipo__": "datetime", "valor": valor.isoformat()}
    if isinstance(valor, dt_time):
        return {"__tipo__": "time", "valor": valor.isoformat()}
    if isinstance(valor, tuple):
        return [_serializar_valor(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): _serializar_valor(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_serializar_valor(v) for v in valor]
    return valor

def _deserializar_valor(valor):
    if isinstance(valor, dict):
        if valor.get("__tipo__") == "datetime":
            return datetime.fromisoformat(valor["valor"])
        if valor.get("__tipo__") == "time":
            return dt_time.fromisoformat(valor["valor"])
        return {k: _deserializar_valor(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_deserializar_valor(v) for v in valor]
    return valor

def exportar_torneo():
    datos = {campo: _serializar_valor(st.session_state.get(campo)) for campo in CAMPOS_TORNEO}
    return json.dumps(datos, ensure_ascii=False, indent=2)

def cargar_torneo(contenido_json):
    datos = json.loads(contenido_json)
    for campo in CAMPOS_TORNEO:
        if campo not in datos:
            continue
        valor = _deserializar_valor(datos[campo])
        if campo in ("restricciones", "partidos_por_pareja") and isinstance(valor, dict):
            valor = {int(k): v for k, v in valor.items()}
        st.session_state[campo] = valor

def inicializar_estado():
    defaults = {
        "etapa": "config", "parejas": [], "restricciones": {}, "pistas": [],
        "dias": [], "duracion": 60, "formato": None, "partidos_por_pareja": {},
        "rondas_programadas": [], "partidos_sin_hueco": [], "clasificacion": [],
        "clasificados": [], "eliminados_previa": [], "cuadro_actual": [],
        "ronda_eliminatoria_num": 1, "partidos_ronda_actual": [],
        "partidos_ronda_actual_num": -1, "campeon": None,
        "liguilla_partido": None, "liguilla_campeon": None,
        "slot_index_acumulado": 0, "logo_torneo_bytes": None
    }
    for clave, valor in defaults.items():
        if clave not in st.session_state:
            st.session_state[clave] = valor

inicializar_estado()

def reiniciar_torneo():
    acceso_guardado = st.session_state.get('acceso_pro', False)
    logo_guardado = st.session_state.get('logo_torneo_bytes', None)
    st.session_state.clear()
    st.session_state['acceso_pro'] = acceso_guardado
    st.session_state['logo_torneo_bytes'] = logo_guardado
    inicializar_estado()
    st.rerun()

# ==================================================================
# 6. CONFIGURACIÓN DEL TORNEO Y SELECTOR DE FORMATO
# ==================================================================
def panel_configuracion():
    st.sidebar.header("⚙️ Configuración del torneo")

    # Subida de Logo
    with st.sidebar.expander("🖼️ Logo del Torneo (Opcional)"):
        uploaded_logo = st.file_uploader("Sube una imagen o logo", type=["png", "jpg", "jpeg"], key="logo_uploader")
        if uploaded_logo is not None:
            st.session_state.logo_torneo_bytes = uploaded_logo.read()
            st.image(st.session_state.logo_torneo_bytes, caption="Logo cargado", width=120)

    # 1. Selector de Sistema de Competición
    with st.sidebar.expander("🏆 Formato de competición", expanded=True):
        tipo_formato = st.selectbox(
            "Selecciona cómo se jugará el torneo:",
            [
                "Fase Previa + Eliminatoria (Recomendado)",
                "Eliminatoria Directa con Repesca (Todos juegan R1)",
                "Liguilla / Todos contra todos (Round Robin)"
            ],
            key="tipo_formato_select"
        )
        if tipo_formato == "Eliminatoria Directa con Repesca (Todos juegan R1)":
            st.caption("ℹ️ Todas las parejas disputan la Ronda 1. Los ganadores avanzan y los mejores perdedores completan los huecos del cuadro.")
        elif tipo_formato == "Liguilla / Todos contra todos (Round Robin)":
            st.caption("ℹ️ Todas las parejas se enfrentan entre sí. Los 2 primeros clasificados disputan la Gran Final.")
        else:
            st.caption("ℹ️ Se juega una fase previa garantizando partidos mínimos. Los mejores de la tabla pasan al cuadro final.")

    with st.sidebar.expander("👥 Parejas", expanded=True):
        num_parejas = st.number_input("¿Cuántas parejas van a participar?", min_value=2, value=max(2, len(st.session_state.parejas) or 4), step=1, key="num_parejas_input")
        
        if tipo_formato == "Eliminatoria Directa con Repesca (Todos juegan R1)" and num_parejas % 2 != 0:
            st.warning("⚠️ Hay un número impar de parejas. Una pareja pasará exenta a la siguiente ronda por sorteo.")

        nombres = []
        for i in range(1, num_parejas + 1):
            col1, col2 = st.columns(2)
            v1 = st.session_state.parejas[i-1][0] if i-1 < len(st.session_state.parejas) else ""
            v2 = st.session_state.parejas[i-1][1] if i-1 < len(st.session_state.parejas) else ""
            with col1: j1 = st.text_input(f"Pareja {i} · J1", value=v1, key=f"pareja_{i}_j1")
            with col2: j2 = st.text_input(f"Pareja {i} · J2", value=v2, key=f"pareja_{i}_j2")
            nombres.append((j1.strip(), j2.strip()))

    with st.sidebar.expander("📍 Pistas y duración"):
        num_pistas = st.number_input("¿Cuántas pistas vas a usar?", min_value=1, value=max(1, len(st.session_state.pistas) or 2), step=1)
        duracion = st.number_input("¿Cuántos minutos dura cada partido?", min_value=1, value=st.session_state.duracion, step=5)

    with st.sidebar.expander("📅 Días y franjas horarias"):
        num_dias = st.number_input("¿En cuántos días se jugará?", min_value=1, value=max(1, len(st.session_state.dias) or 1), step=1)
        fecha_base = datetime(2026, 1, 1)
        dias_ui = []
        for i in range(1, num_dias + 1):
            etiqueta = st.text_input(f"Nombre o fecha del día {i}", value=f"Día {i}", key=f"dia_{i}_etiqueta")
            num_franjas = st.number_input(f"¿Cuántas franjas tiene el día {i}?", min_value=1, value=1, step=1, key=f"dia_{i}_num_franjas")
            franjas = []
            for f in range(1, num_franjas + 1):
                hi = st.time_input(f"Inicio franja {f} ({etiqueta})", value=datetime(2026,1,1,9,0).time(), key=f"dia_{i}_f{f}_inicio")
                hf = st.time_input(f"Fin franja {f} ({etiqueta})", value=datetime(2026,1,1,14,0).time(), key=f"dia_{i}_f{f}_fin")
                franjas.append({
                    "inicio": datetime.combine(fecha_base + timedelta(days=i-1), hi),
                    "fin": datetime.combine(fecha_base + timedelta(days=i-1), hf)
                })
            dias_ui.append({"etiqueta": etiqueta, "franjas": franjas})

    with st.sidebar.expander("🕐 Restricciones horarias"):
        restricciones = {}
        opciones_dias_restriccion = ["Todos"] + [d["etiqueta"] for d in dias_ui]
        for idx, pareja in enumerate(nombres):
            if not (pareja[0] and pareja[1]):
                continue
            tiene_restr = st.checkbox(f"{pareja[0]}/{pareja[1]} tiene restricción", key=f"restr_check_{idx}")
            if not tiene_restr:
                continue
            num_restr = st.number_input(f"Nº restricciones {pareja[0]}/{pareja[1]}", min_value=1, value=1, step=1, key=f"restr_num_{idx}")
            lista_restr = []
            for r in range(1, num_restr + 1):
                st.markdown(f"**Restricción {r}**")
                dia_r = st.selectbox("Día", opciones_dias_restriccion, key=f"restr_dia_{idx}_{r}")
                rc1, rc2 = st.columns(2)
                with rc1: desde = st.time_input("Bloqueado desde", value=datetime(2026,1,1,9,0).time(), key=f"restr_desde_{idx}_{r}")
                with rc2: hasta = st.time_input("Bloqueado hasta", value=datetime(2026,1,1,14,0).time(), key=f"restr_hasta_{idx}_{r}")
                lista_restr.append({"dia": dia_r, "desde": desde, "hasta": hasta})
                if r < num_restr: st.divider()
            restricciones[idx] = lista_restr

    st.sidebar.divider()
    acceso_pro = st.session_state.get("acceso_pro", False)
    plan_gratuito = es_plan_gratuito(num_parejas, num_pistas, len(restricciones) > 0)
    permitido = plan_gratuito or acceso_pro
    generar = False
    
    if not permitido:
        if mostrar_paywall(): 
            st.rerun()
    else:
        generar = st.sidebar.button("🚀 Generar torneo", type="primary", use_container_width=True, key="btn_unico_generar")

    if generar:
        nombres_validos = [p for p in nombres if p[0] and p[1]]
        if len(nombres_validos) != num_parejas:
            st.sidebar.error("⚠️ Completa los nombres de todas las parejas.")
            return

        st.session_state.parejas = nombres_validos
        st.session_state.restricciones = restricciones
        st.session_state.pistas = [f"Pista {i}" for i in range(1, num_pistas + 1)]
        st.session_state.dias = dias_ui
        st.session_state.duracion = duracion

        # Configuración según el formato elegido
        if tipo_formato == "Liguilla / Todos contra todos (Round Robin)":
            partidos_totales = (num_parejas * (num_parejas - 1)) // 2
            st.session_state.formato = {
                "tipo": "liguilla", "partidos_previos": partidos_totales,
                "bracket": 2, "partidos_eliminatoria": 1
            }
            p_prev, p_par = seleccionar_partidos_previos(num_parejas, partidos_totales)
            st.session_state.partidos_por_pareja = p_par
            rondas, s_h, last_slot = asignar_horarios(
                agrupar_en_rondas(p_prev, num_parejas),
                nombres_validos, st.session_state.pistas, dias_ui, duracion, restricciones
            )
            st.session_state.rondas_programadas = rondas
            st.session_state.partidos_sin_hueco = s_h
            st.session_state.slot_index_acumulado = last_slot
            st.session_state.etapa = "previa"

        elif tipo_formato == "Eliminatoria Directa con Repesca (Todos juegan R1)":
            bracket = calcular_tamano_cuadro(num_parejas)
            st.session_state.formato = {
                "tipo": "eliminatoria_directa", "partidos_previos": num_parejas // 2,
                "bracket": bracket, "partidos_eliminatoria": bracket - 1
            }
            # En R1 juegan todas las parejas
            enfrentamientos_r1 = []
            for i in range(0, (num_parejas // 2) * 2, 2):
                enfrentamientos_r1.append((i, i+1))
            
            st.session_state.partidos_por_pareja = {i: 1 for i in range(num_parejas)}
            if num_parejas % 2 != 0:
                st.session_state.partidos_por_pareja[num_parejas - 1] = 0

            rondas, s_h, last_slot = asignar_horarios(
                [{"enfrentamientos": enfrentamientos_r1, "descansan": [num_parejas - 1] if num_parejas % 2 != 0 else []}],
                nombres_validos, st.session_state.pistas, dias_ui, duracion, restricciones
            )
            st.session_state.rondas_programadas = rondas
            st.session_state.partidos_sin_hueco = s_h
            st.session_state.slot_index_acumulado = last_slot
            st.session_state.etapa = "previa"

        else: # Fase Previa + Eliminatoria
            bracket = calcular_tamano_cuadro(num_parejas)
            partidos_previos = math.ceil(num_parejas * 1.5)
            st.session_state.formato = {
                "tipo": "previa_eliminatoria", "partidos_previos": partidos_previos,
                "bracket": bracket, "partidos_eliminatoria": bracket - 1
            }
            p_prev, p_par = seleccionar_partidos_previos(num_parejas, partidos_previos)
            st.session_state.partidos_por_pareja = p_par
            rondas, s_h, last_slot = asignar_horarios(
                agrupar_en_rondas(p_prev, num_parejas),
                nombres_validos, st.session_state.pistas, dias_ui, duracion, restricciones
            )
            st.session_state.rondas_programadas = rondas
            st.session_state.partidos_sin_hueco = s_h
            st.session_state.slot_index_acumulado = last_slot
            st.session_state.etapa = "previa"

        # Quema de código si aplica
        codigo = st.session_state.get('codigo_verificado')
        if codigo:
            verificador.marcar_como_usado(codigo)
            st.session_state['codigo_verificado'] = None

        st.rerun()

# ==================================================================
# 7. RESUMEN VISUAL DEL FORMATO (LIMPIEZA DE CAPACIDAD)
# ==================================================================
def mostrar_formato():
    formato = st.session_state.formato
    parejas = st.session_state.parejas
    partidos_por_pareja = st.session_state.partidos_por_pareja
    
    st.subheader("🤖 Formato y Estructura del Torneo")
    c1, c2 = st.columns(2)
    c1.metric("👥 Parejas Participantes", len(parejas))
    c2.metric("🎾 Partidos de Ronda Previa / R1", formato["partidos_previos"])

    if formato["tipo"] == "liguilla":
        st.success("🏆 **FORMATO: LIGUILLA (TODOS CONTRA TODOS)** — Cada pareja jugará contra todas las demás. Los 2 primeros clasificados disputarán la Gran Final.")
    elif formato["tipo"] == "eliminatoria_directa":
        st.info(f"🏆 **FORMATO: ELIMINATORIA DIRECTA CON REPESCA** — Todas las parejas juegan la 1ª Ronda. Los ganadores y los mejores perdedores formarán el cuadro final de **{formato['bracket']} parejas** ({nombre_ronda(formato['bracket'])}).")
    else:
        st.info(f"🏆 **FORMATO: PREVIA + ELIMINATORIA** — Fase previa para clasificar a las mejores **{formato['bracket']} parejas** al cuadro principal ({nombre_ronda(formato['bracket'])}).")

    with st.expander("ℹ️ Partidos mínimos garantizados por pareja"):
        min_p = min(partidos_por_pareja.values()) if partidos_por_pareja else 1
        max_p = max(partidos_por_pareja.values()) if partidos_por_pareja else 1
        st.write(f"Cada pareja tiene programados entre **{min_p} y {max_p} partido(s)** en la fase inicial antes de los cortes o eliminatorias.")
        df = pd.DataFrame([{"Pareja": f"{p[0]}/{p[1]}", "Partidos programados": partidos_por_pareja.get(idx, 0)} for idx, p in enumerate(parejas)])
        st.dataframe(df, hide_index=True, use_container_width=True)

    if st.session_state.partidos_sin_hueco:
        st.warning("⚠️ Algunos partidos no tuvieron slot asignado. Añade más franjas horarias o pistas si necesitas colocarlos todos.")

# ==================================================================
# 8. FORMULARIO DE INTRODUCCIÓN DE RESULTADOS
# ==================================================================
def formulario_resultado(partido, key_prefix):
    pareja_a = partido["pareja_a"]
    pareja_b = partido["pareja_b"]
    ya_jugado = partido["sets_a"] is not None
    titulo = f"🎾 {pareja_a[0]}/{pareja_a[1]}  vs  {pareja_b[0]}/{pareja_b[1]}"
    if ya_jugado:
        titulo += f"   —   ✅ {partido['sets_a']}-{partido['sets_b']} ({partido['juegos_a']}-{partido['juegos_b']} juegos)"

    with st.expander(titulo, expanded=not ya_jugado):
        info_bits = []
        if partido.get("pista"): info_bits.append(f"🎾 {partido['pista']}")
        if partido.get("dia"): info_bits.append(f"📅 {partido['dia']}")
        if partido.get("hora"): info_bits.append(f"🕐 {partido['hora']}")
        if info_bits: st.caption("   |   ".join(info_bits))

        opciones = opciones_set()
        with st.form(key=f"form_{key_prefix}"):
            col1, col2, col3 = st.columns(3)
            with col1: set1 = st.selectbox("Set 1", opciones, key=f"{key_prefix}_s1")
            with col2: set2 = st.selectbox("Set 2", opciones, key=f"{key_prefix}_s2")
            with col3: set3 = st.selectbox("Set 3 (si procede)", ["No jugado"] + opciones, key=f"{key_prefix}_s3")
            enviado = st.form_submit_button("💾 Guardar resultado")

        if enviado:
            set3_val = None if set3 == "No jugado" else set3
            resultado = procesar_resultado_partido(set1, set2, set3_val)
            if resultado is None:
                st.error("⚠️ Partido empatado a 1 set. Introduce el resultado del 3º set.")
            else:
                partido["sets_a"] = resultado["sets_a"]
                partido["sets_b"] = resultado["sets_b"]
                partido["juegos_a"] = resultado["juegos_a"]
                partido["juegos_b"] = resultado["juegos_b"]
                ganador = pareja_a if resultado["ganador"] == "a" else pareja_b
                st.success(f"🏆 Gana {ganador[0]}/{ganador[1]}")
                st.rerun()

# ==================================================================
# 9. PANELES DE COMPETICIÓN (PREVIA, CLASIFICACIÓN, ELIMINATORIA)
# ==================================================================
def panel_fase_previa():
    st.header("🎾 Calendario y Resultados de Partidos")
    rondas_programadas = st.session_state.rondas_programadas
    if not rondas_programadas:
        st.info("No hay fase previa: se pasa directamente al cuadro final.")
    else:
        tabs = st.tabs([f"Ronda {i}" for i in range(1, len(rondas_programadas) + 1)])
        for i, (tab, ronda) in enumerate(zip(tabs, rondas_programadas), start=1):
            with tab:
                if not ronda["partidos"]: st.warning("⚠️ No hay partidos programados.")
                for j, partido in enumerate(ronda["partidos"]):
                    formulario_resultado(partido, key_prefix=f"previa_{i}_{j}")
                if ronda.get("descansan"):
                    st.caption("😴 Pasa exenta / Descansa: " + ", ".join(ronda["descansan"]))

    todos = [p for r in rondas_programadas for p in r["partidos"]]
    pendientes = [p for p in todos if p["sets_a"] is None]
    st.divider()
    if pendientes:
        st.info(f"📊 Quedan {len(pendientes)} partido(s) por introducir.")

    if st.button("➡️ Calcular clasificación y avanzar", type="primary", disabled=len(pendientes) > 0 and len(todos) > 0):
        st.session_state.clasificacion = calcular_clasificacion(rondas_programadas, st.session_state.parejas)
        st.session_state.etapa = "clasificacion"
        st.rerun()

def tabla_clasificacion(clasificacion):
    filas = []
    for pos, c in enumerate(clasificacion, start=1):
        filas.append({
            "#": pos, "Pareja": f"{c['pareja'][0]}/{c['pareja'][1]}",
            "PJ": c["partidos"], "PG": c["victorias"], "PP": c["derrotas"],
            "Sets": f"{c['sets_ganados']}-{c['sets_perdidos']}", "Dif.Set": c["diferencia_sets"],
            "Juegos": f"{c['juegos_ganados']}-{c['juegos_perdidos']}", "Dif.J": c["diferencia_juegos"]
        })
    return pd.DataFrame(filas)

def panel_clasificacion():
    st.header("📊 Clasificación General")
    clasificacion = st.session_state.clasificacion
    st.dataframe(tabla_clasificacion(clasificacion), hide_index=True, use_container_width=True)
    formato = st.session_state.formato

    if st.button("➡️ Continuar a la fase eliminatoria / final", type="primary"):
        if formato["tipo"] == "liguilla":
            st.session_state.etapa = "liguilla_final"
        else:
            bracket = formato["bracket"]
            clasificados, eliminados = seleccionar_clasificados(clasificacion, bracket)
            st.session_state.clasificados = clasificados
            st.session_state.eliminados_previa = eliminados
            st.session_state.cuadro_actual = [c["pareja"] for c in clasificados]
            st.session_state.ronda_eliminatoria_num = 1
            st.session_state.partidos_ronda_actual = []
            st.session_state.partidos_ronda_actual_num = -1
            st.session_state.etapa = "eliminatoria"
        st.rerun()

def panel_liguilla_final():
    st.header("🏆 Gran Final de la Liguilla")
    clasificacion = st.session_state.clasificacion
    primero, segundo = clasificacion[0], clasificacion[1]
    c1, c2 = st.columns(2)
    c1.metric("🥇 1º Clasificado", f"{primero['pareja'][0]}/{primero['pareja'][1]}")
    c2.metric("🥈 2º Clasificado", f"{segundo['pareja'][0]}/{segundo['pareja'][1]}")

    if st.session_state.liguilla_partido is None:
        st.session_state.liguilla_partido = {
            "pareja_a": primero["pareja"], "pareja_b": segundo["pareja"],
            "pista": st.session_state.pistas[0] if st.session_state.pistas else "Pista 1",
            "dia": st.session_state.dias[-1]["etiqueta"] if st.session_state.dias else "Día Final",
            "hora": "Horario estipulado",
            "sets_a": None, "sets_b": None, "juegos_a": None, "juegos_b": None
        }
    partido_final = st.session_state.liguilla_partido
    if st.session_state.liguilla_campeon is None:
        formulario_resultado(partido_final, key_prefix="liguilla_final")
        if partido_final["sets_a"] is not None:
            ganador = primero["pareja"] if partido_final["sets_a"] > partido_final["sets_b"] else segundo["pareja"]
            st.session_state.liguilla_campeon = ganador
            st.rerun()
    else:
        campeon = st.session_state.liguilla_campeon
        st.balloons()
        st.success(f"🏆🏆🏆 ¡CAMPEONES DEL TORNEO: {campeon[0]} y {campeon[1]}! 🏆🏆🏆")

def panel_eliminatoria():
    st.header("🏆 Cuadro Eliminatorio")

    # Mostrar aviso de eliminados / no repescados ÚNICAMENTE en la Ronda 1
    if st.session_state.ronda_eliminatoria_num == 1 and st.session_state.eliminados_previa:
        with st.expander("📤 Parejas no clasificadas al cuadro final"):
            for c in st.session_state.eliminados_previa:
                pareja = c["pareja"]
                st.write(f"✖️ {pareja[0]}/{pareja[1]} (Dif.Sets: {c['diferencia_sets']:+d}, Dif.Juegos: {c['diferencia_juegos']:+d})")

    equipos = st.session_state.cuadro_actual
    pistas = st.session_state.pistas
    dias = st.session_state.dias
    duracion = st.session_state.duracion
    numero_equipos = len(equipos)

    if numero_equipos < 2:
        st.warning("⚠️ No hay suficientes parejas.")
        return

    st.subheader(nombre_ronda(numero_equipos))
    ronda_num = st.session_state.ronda_eliminatoria_num

    # Reconstrucción y asignación con slots (Día, hora, pista)
    if (st.session_state.partidos_ronda_actual_num != ronda_num or 
        len(st.session_state.partidos_ronda_actual) != numero_equipos // 2):
        
        slots = obtener_slots(dias, duracion)
        start_slot = st.session_state.slot_index_acumulado
        partidos_ronda = []

        for i in range(numero_equipos // 2):
            equipo_a = equipos[i]
            equipo_b = equipos[numero_equipos - 1 - i]
            
            # Asignar slot disponible si existe
            slot_actual = slots[start_slot % len(slots)] if slots else None
            pista_actual = pistas[i % len(pistas)] if pistas else "Pista 1"
            dia_txt = slot_actual["dia"] if slot_actual else (dias[-1]["etiqueta"] if dias else "Día Final")
            hora_txt = slot_actual["hora"].strftime("%H:%M") if slot_actual else "TBD"

            partidos_ronda.append({
                "pareja_a": equipo_a, "pareja_b": equipo_b,
                "pista": pista_actual, "dia": dia_txt, "hora": hora_txt,
                "sets_a": None, "sets_b": None, "juegos_a": None, "juegos_b": None
            })
            start_slot += 1

        st.session_state.slot_index_acumulado = start_slot
        st.session_state.partidos_ronda_actual = partidos_ronda
        st.session_state.partidos_ronda_actual_num = ronda_num

    partidos_ronda = st.session_state.partidos_ronda_actual
    for i, partido in enumerate(partidos_ronda):
        formulario_resultado(partido, key_prefix=f"elim_r{ronda_num}_{i}")

    todos_jugados = all(p["sets_a"] is not None for p in partidos_ronda)
    if todos_jugados:
        ganadores = [p["pareja_a"] if p["sets_a"] > p["sets_b"] else p["pareja_b"] for p in partidos_ronda]
        if len(ganadores) == 1:
            st.session_state.campeon = ganadores[0]
            st.session_state.etapa = "final"
            st.rerun()
        else:
            if st.button(f"➡️ Avanzar a {nombre_ronda(len(ganadores))}", type="primary"):
                st.session_state.cuadro_actual = ganadores
                st.session_state.ronda_eliminatoria_num += 1
                st.session_state.partidos_ronda_actual = []
                st.session_state.partidos_ronda_actual_num = -1
                st.rerun()

def panel_final():
    campeon = st.session_state.campeon
    st.balloons()
    st.success(f"🏆🏆🏆 ¡CAMPEONES DEL TORNEO: {campeon[0]} y {campeon[1]}! 🏆🏆🏆")

# ==================================================================
# 10. APP PRINCIPAL Y BARRA LATERAL
# ==================================================================
def main():
    # Cabecera con Logo si se ha subido
    col_logo, col_tit = st.columns([1, 5])
    if st.session_state.get("logo_torneo_bytes"):
        with col_logo:
            st.image(st.session_state.logo_torneo_bytes, width=100)
    with col_tit:
        st.title("🎾 GeneradorPadel")
        st.caption("Gestor Profesional de Torneos de Pádel · Cuadros, Horarios y Resultados")

    with st.sidebar:
        if st.session_state.etapa != "config":
            st.info(f"Torneo en curso con {len(st.session_state.parejas)} parejas.")
            if st.button("🔄 Reiniciar / Empezar de cero", use_container_width=True):
                reiniciar_torneo()

        st.divider()
        st.subheader("💾 Guardar y Exportar")

        # Descarga de PDF
        if st.session_state.etapa != "config":
            pdf_bytes = exportar_cuadro_pdf()
            st.download_button(
                "📥 Descargar Cuadro y Horarios en PDF",
                data=pdf_bytes,
                file_name=f"cuadro_torneo_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            st.download_button(
                "💾 Guardar Copia del Torneo (.json)",
                data=exportar_torneo(),
                file_name=f"torneo_padel_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )

        archivo_torneo = st.file_uploader("📂 Cargar Torneo Guardado (.json)", type=["json"], key="cargador_torneo")
        if archivo_torneo is not None:
            if st.button("♻️ Restaurar torneo", use_container_width=True):
                try:
                    cargar_torneo(archivo_torneo.read().decode("utf-8"))
                    st.success("✅ Torneo restaurado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al cargar: {e}")

    # Barra de progreso
    etapas = [("config", "1️⃣ Configurar"), ("previa", "2️⃣ Previa / R1"), ("clasificacion", "3️⃣ Clasificación"), ("eliminatoria", "4️⃣ Eliminatorias"), ("final", "🏆 Campeón")]
    actual = st.session_state.etapa
    if actual == "liguilla_final": actual = "eliminatoria"
    idx_map = {k: i for i, (k, _) in enumerate(etapas)}
    st.progress((idx_map.get(actual, 0) + 1) / len(etapas))
    st.caption(" → ".join(f"**{txt}**" if k == actual else txt for k, txt in etapas))
    st.divider()

    # Vistas según etapa
    if st.session_state.etapa == "config":
        panel_configuracion()
        st.info("👈 Configura las opciones en la barra lateral y pulsa **Generar torneo**.")
    elif st.session_state.etapa == "previa":
        mostrar_formato()
        st.divider()
        panel_fase_previa()
    elif st.session_state.etapa == "clasificacion":
        panel_clasificacion()
    elif st.session_state.etapa == "liguilla_final":
        panel_liguilla_final()
    elif st.session_state.etapa == "eliminatoria":
        panel_eliminatoria()
    elif st.session_state.etapa == "final":
        panel_final()

if __name__ == "__main__":
    main()