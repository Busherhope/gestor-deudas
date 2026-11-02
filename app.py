import pandas as pd
import psycopg2
import streamlit as st

# --- INTERFAZ STREAMLIT (debe ser el primer comando) ---
st.set_page_config(
    page_title="Gestor de Deudas y Nómina Catorcenal",
    page_icon="💳",
    layout="wide",
)

# --- ESTILO AESTHETIC / OLD MONEY ---
st.markdown(
    """
    <style>
        /* Fondo general de la aplicación estilo lujoso/minimalista */
        .stApp {
            background-color: #141619;
            color: #e5e7eb;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Ocultar elementos predeterminados de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Tarjetas y contenedores con bordes finos y sutiles */
        div[data-testid="stExpander"], div.stForm, div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background-color: #1a1d21 !important;
            border: 1px solid rgba(197, 168, 128, 0.15) !important;
            border-radius: 10px !important;
            padding: 1.2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }

        /* Métricos con diseño limpio y tipografía elegante */
        div[data-testid="metric-container"] {
            background-color: #1a1d21;
            border: 1px solid rgba(197, 168, 128, 0.2);
            padding: 15px 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        div[data-testid="metric-container"] label {
            color: #a3a3a3 !important;
            font-size: 0.85rem !important;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
            color: #f3f4f6 !important;
            font-weight: 600;
        }

        /* Botones principales refinados con acento sutil */
        .stButton button, button[kind="primary"] {
            background-color: #212529 !important;
            color: #d4af37 !important;
            border: 1px solid rgba(212, 175, 55, 0.4) !important;
            border-radius: 6px !important;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        .stButton button:hover, button[kind="primary"]:hover {
            background-color: #d4af37 !important;
            color: #141619 !important;
            border-color: #d4af37 !important;
        }

        /* Inputs y Selectbox limpios */
        div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            background-color: #1e2227 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 6px !important;
            color: #fff !important;
        }
        div[data-testid="stTextInput"] input:focus, div[data-testid="stNumberInput"] input:focus {
            border-color: #d4af37 !important;
            box-shadow: 0 0 5px rgba(212, 175, 55, 0.3) !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

from db import get_conn, init_db, obtener_cuentas_con_saldo

# --- CONEXIÓN A BASE DE DATOS EN LA NUBE (PostgreSQL / Supabase) ---
conn = get_conn()
init_db(conn)
cursor = conn.cursor()

ORIGENES = ["Sueldo Base", "Bono Desempeño", "Nomix / Adelanto", "Otro"]

st.title("💳 Control de Nómina y Seguimiento de Deudas")

if st.button("🏦 Ir a Mis Cuentas (débito y efectivo)"):
  st.switch_page("pages/1_Cuentas.py")

# --- DASHBOARD DE RESUMEN ---
st.subheader("Estado Actual de Deudas")

df_acreedores = pd.read_sql_query("SELECT * FROM acreedores", conn)
df_abonos = pd.read_sql_query("SELECT * FROM abonos", conn)
df_cuentas = obtener_cuentas_con_saldo(conn)

# Asegurar tipos numéricos
if not df_acreedores.empty:
  df_acreedores["monto_inicial"] = df_acreedores["monto_inicial"].astype(float)
if not df_abonos.empty:
  df_abonos["monto"] = df_abonos["monto"].astype(float)


# --- HELPERS DE CUENTAS ---
def saldo_de_cuenta(cuenta_id):
  if cuenta_id is None:
    return 0.0
  fila = df_cuentas[df_cuentas["id"] == cuenta_id]
  return float(fila["saldo"].iloc[0]) if not fila.empty else 0.0


def fmt_cuenta(cuenta_id):
  if cuenta_id is None:
    return "— Sin cuenta (no descontar de ningún saldo) —"
  fila = df_cuentas[df_cuentas["id"] == cuenta_id]
  if fila.empty:
    return "Cuenta no encontrada"
  r = fila.iloc[0]
  return f"{r['nombre']} ({r['tipo']}) — Saldo: ${r['saldo']:,.2f}"


opciones_cuenta = [None] + [int(x) for x in df_cuentas["id"].tolist()]

resumen = []
for _, row in df_acreedores.iterrows():
  nombre = row["nombre"]
  inicial = float(row["monto_inicial"])
  total_abonado = (
      df_abonos[df_abonos["acreedor_nombre"] == nombre]["monto"].sum()
      if not df_abonos.empty
      else 0.0
  )
  restante = inicial - total_abonado
  progreso = (total_abonado / inicial) * 100 if inicial > 0 else 100.0
  resumen.append({
      "Acreedor": nombre,
      "Deuda Inicial": f"${inicial:,.2f}",
      "Total Abonado": f"${total_abonado:,.2f}",
      "Saldo Restante": f"${max(restante, 0):,.2f}",
      "Saldo_Num": max(restante, 0),
      "% Pagado": f"{min(progreso, 100.0):.1f}%",
  })

df_resumen = pd.DataFrame(resumen)

col1, col2, col3 = st.columns(3)
deuda_total_inicial = (
    df_acreedores["monto_inicial"].sum() if not df_acreedores.empty else 0.0
)
total_pagado_global = df_abonos["monto"].sum() if not df_abonos.empty else 0.0
saldo_total_pendiente = deuda_total_inicial - total_pagado_global

col1.metric("Deuda Total Inicial", f"${deuda_total_inicial:,.2f}")
col2.metric(
    "Total Pagado",
    f"${total_pagado_global:,.2f}",
    (
        f"{(total_pagado_global/deuda_total_inicial)*100 if deuda_total_inicial > 0 else 0:.1f}%"
    ),
)
col3.metric("Saldo Pendiente Global", f"${saldo_total_pendiente:,.2f}")

if not df_resumen.empty:
  st.dataframe(df_resumen.drop(columns=["Saldo_Num"]), use_container_width=True)

st.markdown("---")

# --- ASISTENTE Y CÁLCULO DE NÓMINA DINÁMICO ---
st.subheader("🧮 Asistente de Nómina y Distribución Catorcenal")

if "lista_gastos" not in st.session_state:
  st.session_state.lista_gastos = [
      {"concepto": "Pasajes / Transporte", "monto": 300.0, "activo": True},
      {"concepto": "Comida / Despensa", "monto": 500.0, "activo": True},
      {
          "concepto": "Recarga de Celular / Datos",
          "monto": 100.0,
          "activo": True,
      },
  ]

with st.expander(
    "🚀 Calcular mi Nómina y Distribución Inteligente", expanded=True
):
  col_inputs, col_resultados = st.columns([1.2, 1])

  with col_inputs:
    st.write("#### 1. Parámetros de la Catorcena (Nómina)")

    with st.container():
      st.markdown("*Calculadora automática de ingresos:*")
      col_h1, col_h2 = st.columns(2)
      horas_trabajadas = col_h1.number_input(
          "Horas Trabajadas", value=48.0, step=0.5, format="%.2f"
      )
      sueldo_hora = col_h2.number_input(
          "Sueldo por Hora ($)", value=48.61, step=0.10, format="%.2f"
      )

      col_b1, col_b2 = st.columns(2)
      bono_nocturno = col_b1.number_input(
          "Bono Nocturno ($)", value=30.0, step=5.0, format="%.2f"
      )
      prima_dominical = col_b2.number_input(
          "Prima Dominical ($)", value=80.0, step=5.0, format="%.2f"
      )

      saldo_prestamo_pendiente_nomina = st.number_input(
          "Saldo Pendiente Préstamo Nomix a descontar ($)",
          value=550.46,
          step=50.0,
          format="%.2f",
      )

    # --- Lógica interna de cálculo de nómina ---
    sueldo_base = horas_trabajadas * sueldo_hora
    bono_desempeno = sueldo_base * 0.34
    fondo_ahorro_empresa = 340.96
    apoyo_teletrabajo = 18.60
    vales_despensa = 76.00

    total_percepciones = (
        sueldo_base
        + bono_desempeno
        + bono_nocturno
        + prima_dominical
        + fondo_ahorro_empresa
        + apoyo_teletrabajo
        + vales_despensa
    )

    cuotas_imss = 53.71
    cesantia_vejez = 44.63
    fondo_ahorro_empleado = 340.96
    fondo_ahorro_empresa_ded = 340.96
    prestamo_nomix_ded = saldo_prestamo_pendiente_nomina

    total_deducciones = (
        cuotas_imss
        + cesantia_vejez
        + fondo_ahorro_empleado
        + fondo_ahorro_empresa_ded
        + prestamo_nomix_ded
    )

    ingreso_neto = total_percepciones - total_deducciones
    st.success(
        f"💰 **Ingreso Neto Calculado (Libre):** `${ingreso_neto:,.2f} MXN`"
        f" *(Vales de despensa aparte: ${vales_despensa:,.2f})*"
    )

    st.write("---")
    st.write("📋 **Desglose de Gastos Indispensables para la Catorcena:**")

    col_new_c, col_new_m, col_new_b = st.columns([2, 1, 1])
    nuevo_concepto = col_new_c.text_input(
        "Concepto de Gasto",
        placeholder="Ej: Medicamento",
        key="input_gast_concept",
    )
    nuevo_monto_gasto = col_new_m.number_input(
        "Monto ($)", min_value=0.0, value=50.0, step=10.0, key="input_gast_monto"
    )
    if col_new_b.button("➕ Agregar", use_container_width=True):
      if nuevo_concepto.strip() != "":
        st.session_state.lista_gastos.append({
            "concepto": nuevo_concepto.strip(),
            "monto": nuevo_monto_gasto,
            "activo": True,
        })
        st.rerun()

    gastos_totales_calculados = 0.0
    indices_a_eliminar = []

    for i, g in enumerate(st.session_state.lista_gastos):
      col_check, col_monto, col_del = st.columns([2.5, 1, 0.5])
      activo = col_check.checkbox(
          f"{g['concepto']}", value=g["activo"], key=f"check_{i}"
      )
      st.session_state.lista_gastos[i]["activo"] = activo

      monto_actualizado = col_monto.number_input(
          f"Monto #{i}",
          min_value=0.0,
          value=float(g["monto"]),
          step=10.0,
          label_visibility="collapsed",
          key=f"monto_{i}",
      )
      st.session_state.lista_gastos[i]["monto"] = monto_actualizado

      if activo:
        gastos_totales_calculados += monto_actualizado

      if col_del.button("❌", key=f"del_{i}"):
        indices_a_eliminar.append(i)

    if indices_a_eliminar:
      for idx in sorted(indices_a_eliminar, reverse=True):
        st.session_state.lista_gastos.pop(idx)
      st.rerun()

    st.caption(
        f"**Total de Gastos Seleccionados:** `${gastos_totales_calculados:,.2f}"
        " MXN`"
    )

    st.write("---")
    colchon_emergencia = st.number_input(
        "🛡️ Colchón Imprevistos / Fondo Reserva ($)",
        min_value=0.0,
        value=100.0,
        step=50.0,
    )

    disponible_deudas = (
        ingreso_neto )
