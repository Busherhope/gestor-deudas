import pandas as pd
import psycopg2
import streamlit as st

# ------------------------------------------------------------
# CONFIGURACIÓN DE STREAMLIT: debe ir antes de otros comandos st.*
# ------------------------------------------------------------
st.set_page_config(
    page_title="Gestor de Deudas y Nómina Catorcenal",
    page_icon="💳",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp {
            background-color: #141619;
            color: #e5e7eb;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        #MainMenu, footer { visibility: hidden; }
        div[data-testid="stExpander"],
        div.stForm {
            background-color: #1a1d21 !important;
            border: 1px solid rgba(197, 168, 128, 0.15) !important;
            border-radius: 10px !important;
            padding: 1rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        }
        div[data-testid="metric-container"] {
            background-color: #1a1d21;
            border: 1px solid rgba(197, 168, 128, 0.2);
            padding: 15px 20px;
            border-radius: 10px;
        }
        div[data-testid="metric-container"] label {
            color: #a3a3a3 !important;
            font-size: .85rem !important;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
            color: #f3f4f6 !important;
            font-weight: 600;
        }
        .stButton button, button[kind="primary"] {
            background-color: #212529 !important;
            color: #d4af37 !important;
            border: 1px solid rgba(212, 175, 55, .4) !important;
            border-radius: 6px !important;
            font-weight: 500;
            transition: all .2s ease;
        }
        .stButton button:hover, button[kind="primary"]:hover {
            background-color: #d4af37 !important;
            color: #141619 !important;
            border-color: #d4af37 !important;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            background-color: #1e2227 !important;
            border: 1px solid rgba(255, 255, 255, .08) !important;
            border-radius: 6px !important;
            color: #fff !important;
        }
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stNumberInput"] input:focus {
            border-color: #d4af37 !important;
            box-shadow: 0 0 5px rgba(212, 175, 55, .3) !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

from db import get_conn, init_db, obtener_cuentas_con_saldo

ORIGENES = ["Sueldo Base", "Bono Desempeño", "Nomix / Adelanto", "Otro"]


def moneda(valor):
    """Formatea una cantidad como moneda mexicana."""
    return f"${float(valor or 0):,.2f}"


def cargar_datos(conn):
    """Carga y normaliza los datos utilizados por el dashboard."""
    df_acreedores = pd.read_sql_query(
        "SELECT * FROM acreedores ORDER BY nombre", conn
    )
    df_abonos = pd.read_sql_query(
        "SELECT * FROM abonos ORDER BY fecha DESC, id DESC", conn
    )
    df_cuentas = obtener_cuentas_con_saldo(conn)
