import pandas as pd
import streamlit as st
from db import get_conn, init_db, obtener_cuentas_con_saldo

st.set_page_config(
    page_title="Mis Cuentas y Efectivo", page_icon="🏦", layout="wide"
)

conn = get_conn()
init_db(conn)

if st.button("⬅️ Volver a Control de Deudas"):
  st.switch_page("app.py")

st.title("🏦 Gestión de Cuentas (Débito y Efectivo)")

df_cuentas = obtener_cuentas_con_saldo(conn)

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

# --- SECCIÓN DE ADMINISTRACIÓN DE CUENTAS (Crear y Editar Balance) ---
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

with col_editar:
  st.subheader("✏️ Editar Saldo Inicial / Base de Cuenta")
  if not df_cuentas.empty:
    with st.form("form_editar_cuenta"):
      cta_id_edit = st.selectbox(
          "Selecciona Cuenta a Editar",
          df_cuentas["id"].tolist(),
          format_func=lambda x: df_cuentas[df_cuentas["id"] == x][
              "nombre"
          ].values[0],
      )
      row_cta = df_cuentas[df_cuentas["id"] == cta_id_edit].iloc[0]
      base_actual = float(row_cta["saldo_inicial"])

      nuevo_saldo_base = st.number_input(
          "Nuevo Saldo Base Inicial ($)",
          min_value=0.0,
          value=base_actual,
          step=100.0,
      )

      if st.form_submit_button("Actualizar Base Inicial"):
        cursor = conn.cursor()
        try:
          cursor.execute(
              "UPDATE cuentas SET saldo_inicial = %s WHERE id = %s",
              (nuevo_saldo_base, int(cta_id_edit)),
          )
          conn.commit()
          st.success("¡Base inicial de la cuenta actualizada!")
          st.rerun()
        except Exception as e:
          conn.rollback()
          st.error(f"Error al actualizar: {e}")
  else:
    st.info("No hay cuentas para editar.")

st.markdown("---")

# --- REGISTRO Y LISTA DE TRANSACCIONES ---
col_trans, col_historial = st.columns([1, 1.3])

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

with col_historial:
  st.subheader("📜 Historial de Transacciones")
  try:
    df_trans = pd.read_sql_query(
        """
            SELECT t.id, t.fecha, c.nombre as cuenta, t.tipo, t.monto, t.concepto 
            FROM transacciones t
            JOIN cuentas c ON t.cuenta_id = c.id
            ORDER BY t.fecha DESC, t.id DESC
        """,
        conn,
    )
    if not df_trans.empty:
      st.dataframe(
          df_trans.rename(
              columns={
                  "id": "ID",
                  "fecha": "Fecha",
                  "cuenta": "Cuenta",
                  "tipo": "Tipo",
                  "monto": "Monto",
                  "concepto": "Concepto",
              }
          ),
          use_container_width=True,
      )
    else:
      st.info("Aún no hay transacciones registradas.")
  except Exception:
    st.info("No hay transacciones disponibles.")
