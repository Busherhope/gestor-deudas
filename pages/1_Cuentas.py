import pandas as pd
import streamlit as st
from db import get_conn, init_db, obtener_cuentas_con_saldo

st.set_page_config(
    page_title="Mis Cuentas y Efectivo", page_icon="🏦", layout="wide"
)

conn = get_conn()
init_db(conn)  # <--- ¡ESTO ES LO QUE FALTABA PARA CREAR LAS TABLAS!

if st.button("⬅️ Volver a Control de Deudas"):
  st.switch_page("app.py")

st.title("🏦 Gestión de Cuentas (Débito y Efectivo)")

df_cuentas = obtener_cuentas_con_saldo(conn)

# --- RESTO DEL CÓDIGO DE CUENTAS ---
...

# --- RESUMEN DE SALDOS ---
st.subheader("Balances Actuales")
if not df_cuentas.empty:
  col1, col2 = st.columns(2)
  efectivo_total = df_cuentas[df_cuentas["tipo"] == "Efectivo"]["saldo"].sum()
  debito_total = df_cuentas[df_cuentas["tipo"] != "Efectivo"]["saldo"].sum()
  balance_global = df_cuentas["saldo"].sum()

  col1.metric("Dinero en Tarjetas / Débito", f"${debito_total:,.2f}")
  col2.metric("Efectivo Total", f"${efectivo_total:,.2f}")
  st.metric("Balance Total en Cuentas", f"${balance_global:,.2f}")

  st.dataframe(
      df_cuentas[["id", "nombre", "tipo", "saldo_inicial", "saldo"]].rename(
          columns={
              "id": "ID",
              "nombre": "Cuenta",
              "tipo": "Tipo",
              "saldo_inicial": "Base Inicial",
              "saldo": "Saldo Actual",
          }
      ),
      use_container_width=True,
  )
else:
  st.info("No tienes cuentas registradas todavía.")

st.markdown("---")

# --- CREAR CUENTA ---
col_crear, col_trans = st.columns(2)

with col_crear:
  st.subheader("➕ Nueva Cuenta")
  with st.form("form_crear_cuenta", clear_on_submit=True):
    nombre_cta = st.text_input(
        "Nombre de la Cuenta", placeholder="Ej: BBVA Débito, Efectivo Bolsa"
    )
    tipo_cta = st.selectbox(
        "Tipo", ["Débito / Nomina", "Efectivo", "Ahorro", "Crédito"]
    )
    saldo_base = st.number_input(
        "Saldo Inicial Base ($)", min_value=0.0, value=0.0, step=100.0
    )

    if st.form_submit_button("Crear Cuenta"):
      if nombre_cta.strip() == "":
        st.error("Ingresa un nombre válido.")
      else:
        cursor = conn.cursor()
        try:
          cursor.execute(
              """
                        INSERT INTO cuentas (nombre, tipo, saldo_inicial) 
                        VALUES (%s, %s, %s)
                    """,
              (nombre_cta.strip(), tipo_cta, saldo_base),
          )
          conn.commit()
          st.success(f"¡Cuenta '{nombre_cta}' creada con éxito!")
          st.rerun()
        except Exception as e:
          conn.rollback()
          st.error(f"Error al crear cuenta: {e}")

with col_trans:
  st.subheader("💸 Registrar Ingreso / Gasto Directo")
  if not df_cuentas.empty:
    with st.form("form_transaccion_directa", clear_on_submit=True):
      fecha_t = st.date_input("Fecha")
      cta_id = st.selectbox(
          "Cuenta",
          df_cuentas["id"].tolist(),
          format_func=lambda x: df_cuentas[df_cuentas["id"] == x][
              "nombre"
          ].values[0],
      )
      tipo_t = st.selectbox("Tipo de Movimiento", ["Ingreso", "Egreso"])
      monto_t = st.number_input("Monto ($)", min_value=1.0, step=50.0)
      concepto_t = st.text_input(
          "Concepto / Descripción", placeholder="Ej: Depósito nómina, retiro cajero"
      )

      if st.form_submit_button("Registrar Movimiento"):
        cursor = conn.cursor()
        try:
          cursor.execute(
              """
                        INSERT INTO transacciones (fecha, cuenta_id, tipo, monto, concepto)
                        VALUES (%s, %s, %s, %s, %s)
                    """,
              (str(fecha_t), cta_id, tipo_t, monto_t, concepto_t),
          )
          conn.commit()
          st.success("¡Movimiento registrado correctamente!")
          st.rerun()
        except Exception as e:
          conn.rollback()
          st.error(f"Error: {e}")
  else:
    st.info("Crea una cuenta primero para registrar movimientos.")
