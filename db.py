import pandas as pd
import streamlit as st
from db import get_conn, obtener_cuentas_con_saldo

st.set_page_config(
    page_title="Mis Cuentas y Efectivo", page_icon="🏦", layout="wide"
)

conn = get_conn()
cursor = conn.cursor()

if st.button("⬅️ Volver a Control de Deudas"):
  st.switch_page("app.py")

st.title("🏦 Gestión de Cuentas (Débito y Efectivo)")

df_cuentas = obtener_cuentas_con_saldo(conn)

# --- 1. RESUMEN DE SALDOS ---
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

# --- 2. CREAR Y EDITAR CUENTAS ---
col_crear, col_editar = st.columns(2)

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

with col_editar:
  st.subheader("✏️ Editar Saldo de Cuenta")
  if not df_cuentas.empty:
    with st.form("form_editar_cuenta"):
      cuenta_editar_id = st.selectbox(
          "Selecciona cuenta a modificar:",
          df_cuentas["id"].tolist(),
          format_func=lambda x: df_cuentas[df_cuentas["id"] == x][
              "nombre"
          ].values[0],
      )
      row_cta = df_cuentas[df_cuentas["id"] == cuenta_editar_id].iloc[0]
      saldo_actual_cta = float(row_cta["saldo"])

      nuevo_saldo_deseado = st.number_input(
          "Nuevo Saldo Real en la Cuenta ($)",
          min_value=0.0,
          value=saldo_actual_cta,
          step=100.0,
          help=(
              "Actualiza este campo al monto exacto que tienes actualmente en"
              " esta cuenta."
          ),
      )

      if st.form_submit_button("Actualizar Saldo de Cuenta"):
        try:
          # Actualizamos directamente el saldo inicial para reflejar el monto real que ingresaste
          cursor.execute(
              "UPDATE cuentas SET saldo_inicial = %s WHERE id = %s",
              (nuevo_saldo_deseado, int(cuenta_editar_id)),
          )
          conn.commit()
          st.success("¡Saldo de la cuenta actualizado correctamente!")
          st.rerun()
        except Exception as e:
          conn.rollback()
          st.error(f"Error al actualizar: {e}")
  else:
    st.info("No hay cuentas para editar.")
