import random
import math
import uuid
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import verificador
import json
from datetime import datetime, timedelta, time as dt_time
# ==================================================================
# CONFIGURACIÓN DE LA PÁGINA
# ==================================================================
st.set_page_config(
    page_title="GeneradorPadel | Cuadros y Horarios Automáticos",
    page_icon="🎾",
    layout="wide"
)

# ... (resto de tus importaciones y lógica)

# ==================================================================
# APLICACIÓN PRINCIPAL (MAIN)
# ==================================================================
def main():
    st.title("🎾 GeneradorPadel")
    st.caption("Generador de Cuadros y Horarios Automáticos con Restricciones")

    # --- BARRA LATERAL: BOTÓN REINICIAR Y SECCIÓN GUARDAR / CARGAR ---
    with st.sidebar:
        if st.session_state.etapa != "config":
            st.info(f"Torneo en curso con {len(st.session_state.parejas)} parejas.")
            if st.button("🔄 Empezar un torneo nuevo", use_container_width=True):
                reiniciar_torneo()

        st.divider()
        st.subheader("💾 Guardar / Cargar torneo")

        # Botón para descargar el torneo en curso
        if st.session_state.etapa != "config":
            st.download_button(
                "💾 Descargar Copia del Torneo (.json)",
                data=exportar_torneo(),
                file_name=f"torneo_padel_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )

        # Cargador para subir un archivo .json guardado previamente
        archivo_torneo = st.file_uploader(
            "📂 Cargar Torneo Guardado (.json)",
            type=["json"],
            key="cargador_torneo"
        )
        if archivo_torneo is not None:
            if st.button("♻️ Restaurar este torneo", use_container_width=True):
                try:
                    contenido = archivo_torneo.read().decode("utf-8")
                    cargar_torneo(contenido)
                    st.success("✅ Torneo restaurado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ No se pudo cargar el archivo: {e}")

    barra_progreso()
    st.divider()

    # Navegación por etapas
    if st.session_state.etapa == "config":
        panel_configuracion()
        st.info("👈 Configura las parejas, pistas, días y duración en la barra lateral y pulsa **Generar torneo**.")
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
STRIPE_LINK_PASE_1_TORNEO = "https://buy.stripe.com/aFabJ18hJ7HGdoVeWNfbq00"
STRIPE_LINK_PRO_ILIMITADA = "https://buy.stripe.com/7sYcN555x7HG5WtaGxfbq01"
LIMITE_PAREJAS_GRATIS = 8
LIMITE_PISTAS_GRATIS = 2
def es_plan_gratuito(num_parejas, num_pistas, restricciones_horarias):
    return (num_parejas <= LIMITE_PAREJAS_GRATIS and num_pistas <= LIMITE_PISTAS_GRATIS and not restricciones_horarias)
def obtener_dispositivo_id():
    """Genera un ID único para la sesión actual."""
    if 'padel_device_id' not in st.session_state:
        st.session_state['padel_device_id'] = str(uuid.uuid4())
    return st.session_state['padel_device_id']
CAMPOS_TORNEO = [
    "etapa", "parejas", "restricciones", "pistas", "dias", "duracion",
    "formato", "partidos_por_pareja", "rondas_programadas",
    "partidos_sin_hueco", "clasificacion", "clasificados",
    "eliminados_previa", "cuadro_actual", "ronda_eliminatoria_num",
    "partidos_ronda_actual", "partidos_ronda_actual_num", "campeon",
    "liguilla_partido", "liguilla_campeon"
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
        # Los dicts con claves int (restricciones, partidos_por_pareja)
        # vuelven como str tras el JSON; los reconvertimos.
        if campo in ("restricciones", "partidos_por_pareja") and isinstance(valor, dict):
            valor = {int(k): v for k, v in valor.items()}
        st.session_state[campo] = valor
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
        if verificador.es_pago_valido(codigo, email):
            st.session_state['codigo_verificado'] = codigo
            st.session_state['acceso_pro'] = True
            st.sidebar.success("✅ ¡Acceso verificado!")
            return True
    return False
def pareja_disponible(
    idx,
    dia_partido,
    hora_inicio_partido,
    hora_fin_partido,
    restricciones
):
    """
    Comprueba si la pareja `idx` puede jugar un partido que
    empieza en `dia_partido` entre `hora_inicio_partido` y
    `hora_fin_partido`.

    `restricciones[idx]` es ahora una LISTA de dicts (una pareja
    puede tener varias restricciones, en distintos días o incluso
    varias en el mismo día). Cada dict tiene:
      - "dia": etiqueta de un día concreto (ej. "Día 2") o
        "Todos" si la restricción aplica a todos los días.
      - "desde" / "hasta": franja horaria en la que la pareja
        NO puede jugar ese día (hora de bloqueo, no de
        disponibilidad).

    La pareja NO está disponible si CUALQUIERA de sus
    restricciones se solapa con el partido. Si ninguna
    restricción aplica o ninguna solapa, está disponible.
    """
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
            and
            hora_fin_partido.time() > bloqueado_desde
        )
        if hay_solape:
            return False
    return True
def obtener_slots(
    dias,
    duracion
):
    slots = []
    for dia in dias:
        for franja in dia["franjas"]:
            actual = franja["inicio"]
            while (
                actual + timedelta(minutes=duracion)
                <= franja["fin"]
            ):
                slots.append({
                    "dia": dia["etiqueta"],
                    "hora": actual
                })
                actual += timedelta(
                    minutes=duracion
                )
    return slots
def calcular_capacidad(
    dias,
    pistas,
    duracion
):
    slots = obtener_slots(
        dias,
        duracion
    )
    return len(slots) * len(pistas)
def calcular_tamano_cuadro(num_parejas):
    """
    Devuelve la mayor potencia de 2 que no supera
    el número de parejas.
    Este tamaño ya NO se usa para generar BYEs ni
    partidos de play-in: es simplemente cuántas parejas
    (las mejor clasificadas) entrarán en la fase
    eliminatoria. El resto queda fuera aplicando el
    criterio de "mejor perdedor" sobre la clasificación.
    """
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
    return nombres.get(
        num_equipos,
        "🎯 FASE ELIMINATORIA"
    )
def generar_todos_enfrentamientos(
    num_parejas
):
    partidos = []
    for i in range(num_parejas):
        for j in range(
            i + 1,
            num_parejas
        ):
            partidos.append(
                (i, j)
            )
    return partidos
def seleccionar_partidos_previos(
    num_parejas,
    cantidad
):
    todos = generar_todos_enfrentamientos(
        num_parejas
    )
    seleccionados = []
    partidos_por_pareja = {
        i: 0
        for i in range(num_parejas)
    }
    while (
        todos
        and len(seleccionados) < cantidad
    ):
        candidatos = []
        for partido in todos:
            a, b = partido
            max_partidos = max(
                partidos_por_pareja[a],
                partidos_por_pareja[b]
            )
            suma_partidos = (
                partidos_por_pareja[a]
                + partidos_por_pareja[b]
            )
            candidatos.append(
                (
                    max_partidos,
                    suma_partidos,
                    random.random(),
                    partido
                )
            )
        candidatos.sort(
            key=lambda x: (
                x[0],
                x[1],
                x[2]
            )
        )
        partido_elegido = candidatos[0][3]
        seleccionados.append(
            partido_elegido
        )
        todos.remove(
            partido_elegido
        )
        a, b = partido_elegido
        partidos_por_pareja[a] += 1
        partidos_por_pareja[b] += 1
    return (
        seleccionados,
        partidos_por_pareja
    )
def agrupar_en_rondas(
    partidos,
    num_parejas
):
    pendientes = partidos.copy()
    rondas = []
    while pendientes:
        usados = set()
        ronda = []
        restantes = []
        for partido in pendientes:
            a, b = partido
            if (
                a not in usados
                and
                b not in usados
            ):
                ronda.append(partido)
                usados.add(a)
                usados.add(b)
            else:
                restantes.append(partido)
        if not ronda:
            break
        descansan = [
            i
            for i in range(num_parejas)
            if i not in usados
        ]
        rondas.append({
            "enfrentamientos": ronda,
            "descansan": descansan
        })
        pendientes = restantes
    return rondas
def calcular_formato_automatico(
    num_parejas,
    dias,
    pistas,
    duracion
):
    capacidad_total = calcular_capacidad(
        dias,
        pistas,
        duracion
    )
    # ==============================================================
    # 2 PAREJAS
    # ==============================================================
    if num_parejas == 2:
        return {
            "tipo": "eliminatoria",
            "partidos_previos": 0,
            "bracket": 2,
            "capacidad_total": capacidad_total,
            "partidos_eliminatoria": 1
        }
    # ==============================================================
    # 3-4 PAREJAS -> con suficiente tiempo hacemos liguilla.
    # ==============================================================
    if num_parejas <= 4:
        partidos_liguilla = (
            num_parejas * (num_parejas - 1)
        ) // 2
        partidos_final = 1
        necesarios_liguilla = (
            partidos_liguilla
            + partidos_final
        )
        tiempo_de_sobra = (
            capacidad_total
            >= math.ceil(
                necesarios_liguilla * 1.25
            )
        )
        if tiempo_de_sobra:
            return {
                "tipo": "liguilla",
                "partidos_previos": partidos_liguilla,
                "bracket": 2,
                "capacidad_total": capacidad_total,
                "partidos_eliminatoria": 1
            }
    # ==============================================================
    # 5+ PAREJAS -> sistema "mejor perdedor", sin BYEs ni play-in.
    # ==============================================================
    bracket = calcular_tamano_cuadro(
        num_parejas
    )
    partidos_eliminatoria = (
        bracket - 1
    )
    espacio_previo = max(
        0,
        capacidad_total - partidos_eliminatoria
    )
    if espacio_previo <= 0:
        partidos_previos = 0
    else:
        minimo = math.ceil(
            num_parejas / 2
        )
        partidos_previos = min(
            espacio_previo,
            minimo
        )
    return {
        "tipo": "eliminatoria",
        "partidos_previos": partidos_previos,
        "bracket": bracket,
        "capacidad_total": capacidad_total,
        "partidos_eliminatoria":
            partidos_eliminatoria
    }
def asignar_horarios(
    rondas,
    parejas,
    pistas,
    dias,
    duracion,
    restricciones
):
    """
    Idéntica en su lógica a la versión de consola.
    Único cambio: en vez de hacer print() del aviso de partidos
    sin hueco, se devuelve también la lista para que la capa de
    Streamlit la muestre con st.warning().
    """
    slots = obtener_slots(
        dias,
        duracion
    )
    rondas_programadas = []
    slot_index = 0
    partidos_sin_hueco = []
    for numero_ronda, ronda in enumerate(
        rondas,
        start=1
    ):
        pendientes = (
            ronda["enfrentamientos"].copy()
        )
        partidos_ronda = []
        while pendientes:
            if slot_index >= len(slots):
                for partido in pendientes:
                    a, b = partido
                    partidos_sin_hueco.append(
                        (
                            numero_ronda,
                            a,
                            b
                        )
                    )
                pendientes = []
                break
            slot = slots[slot_index]
            hora_inicio = slot["hora"]
            hora_fin = (
                hora_inicio
                + timedelta(
                    minutes=duracion
                )
            )
            asignados_este_slot = []
            for pista in pistas:
                if not pendientes:
                    break
                partido_elegido = None
                for partido in pendientes:
                    a, b = partido
                    disponibles = (
                        pareja_disponible(
                            a,
                            slot["dia"],
                            hora_inicio,
                            hora_fin,
                            restricciones
                        )
                        and
                        pareja_disponible(
                            b,
                            slot["dia"],
                            hora_inicio,
                            hora_fin,
                            restricciones
                        )
                    )
                    if disponibles:
                        partido_elegido = partido
                        break
                if partido_elegido is None:
                    continue
                pendientes.remove(
                    partido_elegido
                )
                a, b = partido_elegido
                asignados_este_slot.append({
                    "pista": pista,
                    "dia": slot["dia"],
                    "hora": hora_inicio.strftime(
                        "%H:%M"
                    ),
                    "idx_a": a,
                    "idx_b": b,
                    "pareja_a": parejas[a],
                    "pareja_b": parejas[b],
                    "sets_a": None,
                    "sets_b": None,
                    "juegos_a": None,
                    "juegos_b": None
                })
            partidos_ronda.extend(
                asignados_este_slot
            )
            slot_index += 1
        descansan_nombres = [
            f"{parejas[idx][0]}/"
            f"{parejas[idx][1]}"
            for idx in ronda["descansan"]
        ]
        rondas_programadas.append({
            "partidos": partidos_ronda,
            "descansan": descansan_nombres
        })
    return (
        rondas_programadas,
        partidos_sin_hueco
    )
def calcular_clasificacion(
    rondas_programadas,
    parejas
):
    stats = {
        idx: {
            "partidos": 0,
            "victorias": 0,
            "derrotas": 0,
            "sets_ganados": 0,
            "sets_perdidos": 0,
            "juegos_ganados": 0,
            "juegos_perdidos": 0
        }
        for idx in range(len(parejas))
    }
    for ronda in rondas_programadas:
        for partido in ronda["partidos"]:
            if partido["sets_a"] is None:
                continue
            idx_a = partido["idx_a"]
            idx_b = partido["idx_b"]
            sets_a = partido["sets_a"]
            sets_b = partido["sets_b"]
            juegos_a = partido["juegos_a"]
            juegos_b = partido["juegos_b"]
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
            else:
                stats[idx_b]["victorias"] += 1
                stats[idx_a]["derrotas"] += 1
    clasificacion = []
    for idx in range(len(parejas)):
        s = stats[idx]
        diferencia_sets = (
            s["sets_ganados"]
            - s["sets_perdidos"]
        )
        diferencia_juegos = (
            s["juegos_ganados"]
            - s["juegos_perdidos"]
        )
        clasificacion.append({
            "idx": idx,
            "pareja": parejas[idx],
            "partidos": s["partidos"],
            "victorias": s["victorias"],
            "derrotas": s["derrotas"],
            "sets_ganados": s["sets_ganados"],
            "sets_perdidos": s["sets_perdidos"],
            "diferencia_sets": diferencia_sets,
            "juegos_ganados": s["juegos_ganados"],
            "juegos_perdidos": s["juegos_perdidos"],
            "diferencia_juegos": diferencia_juegos
        })
    # ==============================================================
    # ORDEN DE CLASIFICACIÓN: Victorias > Dif.Sets > Dif.Juegos >
    # Juegos ganados (éste último actúa también como criterio de
    # "mejor perdedor" en los desempates al filo del corte).
    # ==============================================================
    clasificacion.sort(
        key=lambda x: (
            -x["victorias"],
            -x["diferencia_sets"],
            -x["diferencia_juegos"],
            -x["juegos_ganados"]
        )
    )
    return clasificacion
def seleccionar_clasificados(
    clasificacion,
    tamano_cuadro
):
    """
    Sistema "mejor perdedor": sin BYEs ni play-in. Se toman
    directamente las "tamano_cuadro" parejas mejor situadas.
    Devuelve (clasificados, eliminados), ambos en orden de
    clasificación (1º primero) para poder sembrar el cuadro
    como 1º vs último, 2º vs penúltimo, etc.
    """
    clasificados = list(
        clasificacion[:tamano_cuadro]
    )
    eliminados = list(
        clasificacion[tamano_cuadro:]
    )
    return (
        clasificados,
        eliminados
    )
# ==================================================================
# 2. VALIDACIÓN DE RESULTADOS DE UN SET (misma regla que la
#    versión de consola, expuesta ahora como catálogo de
#    combinaciones válidas para un selectbox de Streamlit).
# ==================================================================
def set_valido(a, b):
    if a == 6 and 0 <= b <= 4:
        return True
    if b == 6 and 0 <= a <= 4:
        return True
    if a == 7 and b == 5:
        return True
    if b == 7 and a == 5:
        return True
    if a == 7 and b == 6:
        return True
    if b == 7 and a == 6:
        return True
    return False
@st.cache_data
def opciones_set():
    opciones = []
    for a in range(0, 8):
        for b in range(0, 8):
            if set_valido(a, b):
                opciones.append(f"{a}-{b}")
    return sorted(
        opciones,
        key=lambda s: (
            -max(int(x) for x in s.split("-")),
            s
        )
    )
def procesar_resultado_partido(set1, set2, set3):
    """
    Equivalente a pedir_resultado_padel() pero a partir de
    los resultados ya introducidos en el formulario (strings
    "a-b"). set3 puede ser None si no ha hecho falta.
    Devuelve un dict con sets_a, sets_b, juegos_a, juegos_b y
    el nombre del ganador ("a" o "b"), o None si falta el
    tercer set siendo necesario.
    """
    def parse(s):
        a, b = s.split("-")
        return int(a), int(b)
    sets_a = 0
    sets_b = 0
    juegos_a = 0
    juegos_b = 0
    a1, b1 = parse(set1)
    juegos_a += a1
    juegos_b += b1
    if a1 > b1:
        sets_a += 1
    else:
        sets_b += 1
    a2, b2 = parse(set2)
    juegos_a += a2
    juegos_b += b2
    if a2 > b2:
        sets_a += 1
    else:
        sets_b += 1
    if sets_a == 1 and sets_b == 1:
        if not set3:
            return None
        a3, b3 = parse(set3)
        juegos_a += a3
        juegos_b += b3
        if a3 > b3:
            sets_a += 1
        else:
            sets_b += 1
    ganador = "a" if sets_a > sets_b else "b"
    return {
        "sets_a": sets_a,
        "sets_b": sets_b,
        "juegos_a": juegos_a,
        "juegos_b": juegos_b,
        "ganador": ganador
    }
# ==================================================================
# 3. ESTADO DE LA APLICACIÓN (st.session_state)
# ==================================================================
def inicializar_estado():
    defaults = {
        "etapa": "config",
        "parejas": [],
        "restricciones": {},
        "pistas": [],
        "dias": [],
        "duracion": 60,
        "formato": None,
        "partidos_por_pareja": {},
        "rondas_programadas": [],
        "partidos_sin_hueco": [],
        "clasificacion": [],
        "clasificados": [],
        "eliminados_previa": [],
        "cuadro_actual": [],
        "ronda_eliminatoria_num": 1,
        "partidos_ronda_actual": [],
        "partidos_ronda_actual_num": -1,
        "campeon": None,
        "liguilla_partido": None,
        "liguilla_campeon": None
    }
    for clave, valor in defaults.items():
        if clave not in st.session_state:
            st.session_state[clave] = valor
inicializar_estado()
# ==================================================================
# 4. BARRA LATERAL: CONFIGURACIÓN INICIAL DEL TORNEO
# ==================================================================
def panel_configuracion():
    st.sidebar.header("⚙️ Configuración del torneo")
    
    # 1. EXPANDERS (Entrada de datos)
    with st.sidebar.expander("👥 Parejas", expanded=True):
        num_parejas = st.number_input("¿Cuántas parejas van a participar?", min_value=2, value=max(2, len(st.session_state.parejas) or 4), step=1, key="num_parejas_input")
        nombres = []
        for i in range(1, num_parejas + 1):
            col1, col2 = st.columns(2)
            v1 = st.session_state.parejas[i-1][0] if i-1 < len(st.session_state.parejas) else ""
            v2 = st.session_state.parejas[i-1][1] if i-1 < len(st.session_state.parejas) else ""
            with col1: j1 = st.text_input(f"Pareja {i} · Jugador 1º", value=v1, key=f"pareja_{i}_j1")
            with col2: j2 = st.text_input(f"Pareja {i} · Jugador 2º", value=v2, key=f"pareja_{i}_j2")
            nombres.append((j1.strip(), j2.strip()))
    with st.sidebar.expander("📍 Pistas y duración"):
        num_pistas = st.number_input("¿Cuántas pistas vas a usar?", min_value=1, value=max(1, len(st.session_state.pistas) or 2), step=1)
        duracion = st.number_input("¿Cuántos minutos dura cada partido?", min_value=1, value=st.session_state.duracion, step=5)
    with st.sidebar.expander("📅 Días y franjas horarias"):
        num_dias = st.number_input("¿En cuántos días se jugará?", min_value=1, value=max(1, len(st.session_state.dias) or 1), step=1)
        fecha_base = datetime(2024, 1, 1)
        dias_ui = []
        for i in range(1, num_dias + 1):
            etiqueta = st.text_input(f"Nombre o fecha del día {i}", value=f"Día {i}", key=f"dia_{i}_etiqueta")
            num_franjas = st.number_input(f"¿Cuántas franjas horarias tiene el día {i}?", min_value=1, value=1, step=1, key=f"dia_{i}_num_franjas")
            franjas = []
            for f in range(1, num_franjas + 1):
                hi = st.time_input(f"Inicio franja {f} (día {i})", value=datetime(2024,1,1,9,0).time(), key=f"dia_{i}_f{f}_inicio")
                hf = st.time_input(f"Fin franja {f} (día {i})", value=datetime(2024,1,1,14,0).time(), key=f"dia_{i}_f{f}_fin")
                franjas.append({"inicio": datetime.combine(fecha_base + timedelta(days=i-1), hi), "fin": datetime.combine(fecha_base + timedelta(days=i-1), hf)})
            dias_ui.append({"etiqueta": etiqueta, "franjas": franjas})
    # ==============================================================
    # RESTRICCIONES HORARIAS: ahora cada pareja puede tener
    # MÚLTIPLES restricciones (distintos días y/o distintas franjas).
    # `restricciones[idx]` pasa a ser una LISTA de dicts en vez de
    # un único dict.
    # ==============================================================
    with st.sidebar.expander("🕐 Restricciones horarias"):
        restricciones = {}
        opciones_dias_restriccion = ["Todos"] + [d["etiqueta"] for d in dias_ui]
        for idx, pareja in enumerate(nombres):
            if not (pareja[0] and pareja[1]):
                continue
            tiene_restriccion = st.checkbox(
                f"{pareja[0]}/{pareja[1]} tiene restricción",
                key=f"restr_check_{idx}"
            )
            if not tiene_restriccion:
                continue
            num_restricciones = st.number_input(
                f"¿Cuántas restricciones tiene {pareja[0]}/{pareja[1]}?",
                min_value=1,
                value=1,
                step=1,
                key=f"restr_num_{idx}"
            )
            lista_restricciones = []
            for r in range(1, num_restricciones + 1):
                st.markdown(f"**Restricción {r}**")
                dia_restriccion = st.selectbox(
                    "Día",
                    opciones_dias_restriccion,
                    key=f"restr_dia_{idx}_{r}"
                )
                rc1, rc2 = st.columns(2)
                with rc1:
                    desde = st.time_input(
                        "No disponible desde",
                        value=datetime(2024, 1, 1, 9, 0).time(),
                        key=f"restr_desde_{idx}_{r}"
                    )
                with rc2:
                    hasta = st.time_input(
                        "No disponible hasta",
                        value=datetime(2024, 1, 1, 14, 0).time(),
                        key=f"restr_hasta_{idx}_{r}"
                    )
                lista_restricciones.append({
                    "dia": dia_restriccion,
                    "desde": desde,
                    "hasta": hasta
                })
                if r < num_restricciones:
                    st.divider()
            restricciones[idx] = lista_restricciones
    # 2. CONTROL DE ACCESO
    st.sidebar.divider()
    acceso_pro = st.session_state.get("acceso_pro", False)
    plan_gratuito = es_plan_gratuito(num_parejas, num_pistas, len(restricciones) > 0)
    
    permitido = plan_gratuito or acceso_pro
    generar = False
    if not permitido:
        if mostrar_paywall(): 
            st.rerun() # Si se valida el código, recargamos para habilitar el botón
    else:
        generar = st.sidebar.button("🚀 Generar torneo", type="primary", use_container_width=True, key="btn_unico_generar")
    # 3. EJECUCIÓN
    # 3. EJECUCIÓN
    if generar:
        nombres_validos = [p for p in nombres if p[0] and p[1]]
        if len(nombres_validos) != num_parejas:
            st.sidebar.error("⚠️ Completa los nombres de todas las parejas."); return
            
        st.session_state.parejas = nombres_validos
        st.session_state.restricciones = restricciones
        st.session_state.pistas = [f"Pista {i}" for i in range(1, num_pistas + 1)]
        st.session_state.dias = dias_ui
        st.session_state.duracion = duracion
        st.session_state.formato = calcular_formato_automatico(num_parejas, dias_ui, st.session_state.pistas, duracion)
        
        p_prev, p_par = seleccionar_partidos_previos(num_parejas, st.session_state.formato["partidos_previos"])
        st.session_state.partidos_por_pareja = p_par 
        rondas, s_h = asignar_horarios(agrupar_en_rondas(p_prev, num_parejas), nombres_validos, st.session_state.pistas, dias_ui, duracion, restricciones)
        
        st.session_state.rondas_programadas = rondas
        st.session_state.partidos_sin_hueco = s_h
        st.session_state.etapa = "previa"
        
        # --- NUEVO: A5HORA SÍ QUEMAMOS EL CÓDIGO EN STRIPE ---
        codigo = st.session_state.get('codigo_verificado')
        if codigo:
            verificador.marcar_como_usado(codigo)
            # Limpiamos el código para no volver a llamarlo accidentalmente
            st.session_state['codigo_verificado'] = None
            
        st.rerun()
# ==================================================================
# 5. FORMATO AUTOMÁTICO (resumen visual)
# ==================================================================
def mostrar_formato():
    formato = st.session_state.formato
    parejas = st.session_state.parejas
    partidos_por_pareja = st.session_state.partidos_por_pareja
    st.subheader("🤖 Formato automático del torneo")
    c1, c2, c3 = st.columns(3)
    c1.metric("👥 Parejas", len(parejas))
    c2.metric(
        "🎾 Partidos fase previa",
        formato["partidos_previos"]
    )
    c3.metric(
        "🎾 Capacidad disponible",
        formato["capacidad_total"]
    )
    if formato["tipo"] == "liguilla":
        st.success(
            "🏆 **FORMATO: LIGUILLA** — todas las parejas juegan "
            "entre sí. Los 2 primeros disputan la FINAL."
        )
    else:
        st.info(
            f"🏆 **FORMATO: ELIMINATORIA** · Cuadro principal: "
            f"**{formato['bracket']} parejas** · Fase objetivo: "
            f"**{nombre_ronda(formato['bracket'])}**\n\n"
            "🥈 Sistema de **MEJOR PERDEDOR**: pasan directamente "
            "las mejor clasificadas de la fase previa, sin BYEs "
            "ni play-in."
        )
    with st.expander("👥 Partidos previstos por pareja"):
        df = pd.DataFrame([
            {
                "Pareja": f"{p[0]}/{p[1]}",
                "Partidos previos": partidos_por_pareja[idx]
            }
            for idx, p in enumerate(parejas)
        ])
        st.dataframe(df, hide_index=True, use_container_width=True)
    if st.session_state.partidos_sin_hueco:
        st.warning(
            "⚠️ Algunos partidos de la fase previa no han podido "
            "ser colocados por falta de horarios/pistas:"
        )
        for numero_ronda, a, b in st.session_state.partidos_sin_hueco:
            pa = parejas[a]
            pb = parejas[b]
            st.write(
                f"- Ronda {numero_ronda}: {pa[0]}/{pa[1]} vs "
                f"{pb[0]}/{pb[1]}"
            )
# ==================================================================
# 6. FORMULARIO DE RESULTADO DE UN PARTIDO
# ==================================================================
def formulario_resultado(partido, key_prefix):
    """
    Sustituye a pedir_resultado_padel(). Dibuja un pequeño
    formulario con los 3 sets (el 3º solo se usa si el partido
    se decide en el tercero) y, al enviarlo, calcula y guarda
    el resultado directamente en el diccionario `partido`.
    """
    pareja_a = partido["pareja_a"]
    pareja_b = partido["pareja_b"]
    ya_jugado = partido["sets_a"] is not None
    titulo = f"🎾 {pareja_a[0]}/{pareja_a[1]}  vs  {pareja_b[0]}/{pareja_b[1]}"
    if ya_jugado:
        titulo += (
            f"   —   ✅ {partido['sets_a']}-{partido['sets_b']} "
            f"({partido['juegos_a']}-{partido['juegos_b']} juegos)"
        )
    with st.expander(titulo, expanded=not ya_jugado):
        info_bits = []
        if partido.get("pista"):
            info_bits.append(f"🎾 {partido['pista']}")
        if partido.get("dia"):
            info_bits.append(f"📅 {partido['dia']}")
        if partido.get("hora"):
            info_bits.append(f"🕐 {partido['hora']}")
        if info_bits:
            st.caption("   |   ".join(info_bits))
        opciones = opciones_set()
        with st.form(key=f"form_{key_prefix}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                set1 = st.selectbox("Set 1", opciones, key=f"{key_prefix}_s1")
            with col2:
                set2 = st.selectbox("Set 2", opciones, key=f"{key_prefix}_s2")
            with col3:
                set3 = st.selectbox(
                    "Set 3 (si procede)",
                    ["No jugado"] + opciones,
                    key=f"{key_prefix}_s3"
                )
            enviado = st.form_submit_button("💾 Guardar resultado")
        if enviado:
            set3_val = None if set3 == "No jugado" else set3
            resultado = procesar_resultado_partido(set1, set2, set3_val)
            if resultado is None:
                st.error(
                    "⚠️ El partido está 1-1 en sets: indica el "
                    "resultado del Set 3 para saber quién gana."
                )
            else:
                partido["sets_a"] = resultado["sets_a"]
                partido["sets_b"] = resultado["sets_b"]
                partido["juegos_a"] = resultado["juegos_a"]
                partido["juegos_b"] = resultado["juegos_b"]
                ganador = (
                    pareja_a if resultado["ganador"] == "a" else pareja_b
                )
                st.success(
                    f"🏆 Gana {ganador[0]}/{ganador[1]}  "
                    f"({resultado['sets_a']}-{resultado['sets_b']}, "
                    f"{resultado['juegos_a']}-{resultado['juegos_b']} "
                    "juegos)"
                )
                st.rerun()
# ==================================================================
# 7. FASE PREVIA: CALENDARIO + RESULTADOS
# ==================================================================
def panel_fase_previa():
    st.header("🎾 Calendario del torneo")
    rondas_programadas = st.session_state.rondas_programadas
    if not rondas_programadas:
        st.info(
            "No hay fase previa programada: se pasa directamente "
            "a la fase eliminatoria / final."
        )
    else:
        tabs = st.tabs([
            f"Ronda previa {i}" for i in range(1, len(rondas_programadas) + 1)
        ])
        for i, (tab, ronda) in enumerate(
            zip(tabs, rondas_programadas), start=1
        ):
            with tab:
                if not ronda["partidos"]:
                    st.warning("⚠️ No hay partidos programados.")
                for j, partido in enumerate(ronda["partidos"]):
                    formulario_resultado(
                        partido,
                        key_prefix=f"previa_{i}_{j}"
                    )
                if ronda["descansan"]:
                    st.caption(
                        "😴 Descansa: " + ", ".join(ronda["descansan"])
                    )
    todos_los_partidos = [
        partido
        for ronda in rondas_programadas
        for partido in ronda["partidos"]
    ]
    pendientes = [
        p for p in todos_los_partidos if p["sets_a"] is None
    ]
    st.divider()
    if pendientes:
        st.info(
            f"📊 Quedan {len(pendientes)} partido(s) de la fase "
            "previa por introducir."
        )
    col_a, col_b = st.columns([1, 3])
    with col_a:
        avanzar = st.button(
            "➡️ Calcular clasificación y continuar",
            type="primary",
            disabled=len(pendientes) > 0 and len(todos_los_partidos) > 0
        )
    with col_b:
        if not todos_los_partidos:
            st.caption(
                "No hay partidos de fase previa: puedes continuar "
                "directamente."
            )
    if avanzar:
        st.session_state.clasificacion = calcular_clasificacion(
            rondas_programadas,
            st.session_state.parejas
        )
        st.session_state.etapa = "clasificacion"
        st.rerun()
# ==================================================================
# 8. CLASIFICACIÓN DE LA FASE PREVIA
# ==================================================================
def tabla_clasificacion(clasificacion):
    filas = []
    for posicion, c in enumerate(clasificacion, start=1):
        filas.append({
            "#": posicion,
            "Pareja": f"{c['pareja'][0]}/{c['pareja'][1]}",
            "PJ": c["partidos"],
            "PG": c["victorias"],
            "PP": c["derrotas"],
            "Sets": f"{c['sets_ganados']}-{c['sets_perdidos']}",
            "Dif.Set": c["diferencia_sets"],
            "Juegos": f"{c['juegos_ganados']}-{c['juegos_perdidos']}",
            "Dif.J": c["diferencia_juegos"]
        })
    return pd.DataFrame(filas)
def panel_clasificacion():
    st.header("📊 Clasificación fase previa")
    clasificacion = st.session_state.clasificacion
    st.dataframe(
        tabla_clasificacion(clasificacion),
        hide_index=True,
        use_container_width=True
    )
    formato = st.session_state.formato
    if st.button("➡️ Continuar a la fase final", type="primary"):
        if formato["tipo"] == "liguilla":
            st.session_state.etapa = "liguilla_final"
        else:
            bracket = formato["bracket"]
            (
                clasificados,
                eliminados
            ) = seleccionar_clasificados(
                clasificacion,
                bracket
            )
            st.session_state.clasificados = clasificados
            st.session_state.eliminados_previa = eliminados
            # Los equipos se mantienen en orden de clasificación
            # (1º primero) para sembrar 1º vs último, 2º vs
            # penúltimo, etc.
            st.session_state.cuadro_actual = [
                c["pareja"] for c in clasificados
            ]
            st.session_state.ronda_eliminatoria_num = 1
            st.session_state.etapa = "eliminatoria"
        st.rerun()
# ==================================================================
# 9. LIGUILLA: FINAL ENTRE 1º Y 2º
# ==================================================================
def panel_liguilla_final():
    st.header("🏆 Final de la liguilla")
    clasificacion = st.session_state.clasificacion
    primero = clasificacion[0]
    segundo = clasificacion[1]
    c1, c2 = st.columns(2)
    c1.metric("🥇 1º", f"{primero['pareja'][0]}/{primero['pareja'][1]}")
    c2.metric("🥈 2º", f"{segundo['pareja'][0]}/{segundo['pareja'][1]}")
    # El partido se guarda en session_state para que sobreviva a
    # los reruns que dispara el formulario de resultado; si se
    # reconstruyera de cero en cada rerun, el resultado recién
    # introducido se perdería antes de poder comprobarlo.
    if st.session_state.liguilla_partido is None:
        st.session_state.liguilla_partido = {
            "pareja_a": primero["pareja"],
            "pareja_b": segundo["pareja"],
            "sets_a": None,
            "sets_b": None,
            "juegos_a": None,
            "juegos_b": None
        }
    partido_final = st.session_state.liguilla_partido
    if st.session_state.liguilla_campeon is None:
        formulario_resultado(partido_final, key_prefix="liguilla_final")
        if partido_final["sets_a"] is not None:
            ganador = (
                primero["pareja"]
                if partido_final["sets_a"] > partido_final["sets_b"]
                else segundo["pareja"]
            )
            st.session_state.liguilla_campeon = ganador
            st.rerun()
    else:
        campeon = st.session_state.liguilla_campeon
        st.balloons()
        st.success(f"🏆🏆🏆 CAMPEONES: {campeon[0]}/{campeon[1]} 🏆🏆🏆")
    if st.button("🔄 Empezar un torneo nuevo"):
        reiniciar_torneo()
# ==================================================================
# 10. FASE ELIMINATORIA (con sistema "mejor perdedor")
# ==================================================================
def panel_eliminatoria():
    st.header("🏆 Fase eliminatoria")
    if st.session_state.eliminados_previa:
        with st.expander(
            "📤 Quedan fuera de la eliminatoria "
            "(mejor perdedor no alcanzado)"
        ):
            for c in st.session_state.eliminados_previa:
                pareja = c["pareja"]
                st.write(
                    f"✖️ {pareja[0]}/{pareja[1]}   "
                    f"(Dif.Sets: {c['diferencia_sets']:+d}, "
                    f"Dif.Juegos: {c['diferencia_juegos']:+d}, "
                    f"Juegos ganados: {c['juegos_ganados']})"
                )
    equipos = st.session_state.cuadro_actual
    pistas = st.session_state.pistas
    if len(equipos) < 2:
        st.warning("⚠️ No hay suficientes parejas para continuar.")
        return
    numero_equipos = len(equipos)
    st.subheader(nombre_ronda(numero_equipos))
    if st.session_state.ronda_eliminatoria_num == 1:
        with st.expander(f"🎟️ Clasificados a {nombre_ronda(numero_equipos)}"):
            for posicion, pareja in enumerate(equipos, start=1):
                st.write(f"{posicion}. {pareja[0]}/{pareja[1]}")
    ronda_num = st.session_state.ronda_eliminatoria_num
    # Los partidos de la ronda se guardan en session_state y solo
    # se reconstruyen cuando cambia el número de ronda (o el
    # número de equipos). Si se reconstruyeran en cada rerun,
    # cualquier resultado recién guardado por el formulario se
    # perdería antes de poder comprobar si la ronda está completa
    # — que era exactamente el motivo de que la final no avanzara.
    necesita_reconstruir = (
        st.session_state.partidos_ronda_actual_num != ronda_num
        or len(st.session_state.partidos_ronda_actual)
        != numero_equipos // 2
    )
    if necesita_reconstruir:
        partidos_ronda = []
        for i in range(numero_equipos // 2):
            equipo_a = equipos[i]
            equipo_b = equipos[numero_equipos - 1 - i]
            pista = pistas[i % len(pistas)] if pistas else None
            partidos_ronda.append({
                "pareja_a": equipo_a,
                "pareja_b": equipo_b,
                "pista": pista,
                "sets_a": None,
                "sets_b": None,
                "juegos_a": None,
                "juegos_b": None
            })
        st.session_state.partidos_ronda_actual = partidos_ronda
        st.session_state.partidos_ronda_actual_num = ronda_num
    partidos_ronda = st.session_state.partidos_ronda_actual
    for i, partido in enumerate(partidos_ronda):
        formulario_resultado(
            partido,
            key_prefix=f"elim_r{ronda_num}_{i}"
        )
    todos_jugados = all(p["sets_a"] is not None for p in partidos_ronda)
    if todos_jugados:
        ganadores = [
            p["pareja_a"] if p["sets_a"] > p["sets_b"] else p["pareja_b"]
            for p in partidos_ronda
        ]
        if len(ganadores) == 1:
            st.session_state.campeon = ganadores[0]
            st.session_state.etapa = "final"
            st.rerun()
        else:
            etiqueta_siguiente = f"➡️ Avanzar a {nombre_ronda(len(ganadores))}"
            if st.button(etiqueta_siguiente, type="primary"):
                st.session_state.cuadro_actual = ganadores
                st.session_state.ronda_eliminatoria_num += 1
                st.session_state.partidos_ronda_actual = []
                st.session_state.partidos_ronda_actual_num = -1
                st.rerun()
# ==================================================================
# 11. CAMPEÓN
# ==================================================================
def panel_final():
    campeon = st.session_state.campeon
    st.balloons()
    st.success(f"🏆🏆🏆 CAMPEONES: {campeon[0]}/{campeon[1]} 🏆🏆🏆")
    if st.button("🔄 Empezar un torneo nuevo"):
        reiniciar_torneo()
# ==================================================================
# 12. UTILIDADES DE NAVEGACIÓN
# ==================================================================
def reiniciar_torneo():
    acceso_guardado = st.session_state.get('acceso_pro', False)
    st.session_state.clear()
    st.session_state['acceso_pro'] = acceso_guardado
    inicializar_estado()
    st.rerun()
def barra_progreso():
    etapas = [
        ("config", "1️⃣ Configurar"),
        ("previa", "2️⃣ Fase previa"),
        ("clasificacion", "3️⃣ Clasificación"),
        ("eliminatoria", "4️⃣ Eliminatoria / Final"),
        ("final", "🏆 Campeón")
    ]
    etapa_actual = st.session_state.etapa
    if etapa_actual == "liguilla_final":
        etapa_actual = "eliminatoria"
    indices = {clave: i for i, (clave, _) in enumerate(etapas)}
    st.progress(
        (indices.get(etapa_actual, 0) + 1) / len(etapas)
    )
    st.caption(
        " → ".join(
            f"**{texto}**" if clave == etapa_actual else texto
            for clave, texto in etapas
        )
    )
# ==================================================================
# 13. APP PRINCIPAL
# ==================================================================

if __name__ == "__main__":
    main()