from db import get_conn, init_db, obtener_cuentas_con_saldo
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Mis Cuentas y Efectivo", page_icon="🏦", layout="wide"
)

conn = get_conn()
init_db(conn)
cursor = conn.cursor()

if st.button("⬅️ Volver a Control de Deudas"):
  st.switch_page("app.py")

st.title("🏦 Gestión de Cuentas (Débito y Efectivo)")

df_cuentas = obtener_cuentas_con_saldo(conn)

# --- 1. BALANCES Y TABLA DE CUENTAS ---
st.subheader("📊 Balances Actuales y Cuentas")
if not df_cuentas.empty:
  col1, col2, col3 = st.columns(3)
  efectivo_total = df_cuentas[df_cuentas["tipo"] == "Efectivo"]["saldo"].sum()
  debito_total = df_cuentas[df_cuentas["tipo"] != "Efectivo"]["saldo"].sum()
  balance_global = df_cuentas["saldo"].sum()

  col1.metric("Tarjetas / Débito", f"${debito_total:,.2f}")
  col2.metric("Efectivo", f"${efectivo_total:,.2f}")
  col3.metric("Balance Total", f"${balance_global:,.2f}")

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
  st.info("Aún no tienes cuentas registradas.")

st.markdown("---")

# --- 2. EDITAR MONTO / SALDO DE LA CUENTA (¡Muy visible arriba!) ---
st.subheader("✏️ Editar Monto o Saldo de una Cuenta")
if not df_cuentas.empty:
  with st.form("form_editar_monto_cuenta"):
    col_e1, col_e2, col_e3 = st.columns([2, 1, 1])
    cuenta_sel_id = col_e1.selectbox(
        "Selecciona Cuenta:",
        df_cuentas["id"].tolist(),
        format_func=lambda x: f"{df_cuentas[df_cuentas['id'] == x]['nombre'].values[0]} (Saldo Actual: ${df_cuentas[df_cuentas['id'] == x]['saldo'].values[0]:,.2f})",
    )
    cta_row = df_cuentas[df_cuentas["id"] == cuenta_sel_id].iloc[0]
    saldo_actual_actual = float(cta_row["saldo"])
    movimiento_neto = float(cta_row["movimiento_neto"])

    nuevo_saldo_deseado = col_e2.number_input(
        "Nuevo Saldo Real ($)", value=saldo_actual_actual, step=100.0
    )
    btn_act_saldo = col_e3.form_submit_button("💾 Actualizar Monto")

    if btn_act_saldo:
      # Ajusta la base inicial para que el saldo actual refleje exactamente el monto deseado
      nueva_base_inicial = round(nuevo_saldo_deseado - movimiento_neto, 2)
      cursor.execute(
          "UPDATE cuentas SET saldo_inicial = %s WHERE id = %s",
          (nueva_base_inicial, int(cuenta_sel_id)),
      )
      conn.commit()
      st.success("¡Monto/Saldo de la cuenta actualizado con éxito!")
      st.rerun()
else:
  st.info("Crea una cuenta primero para poder editar su monto.")

st.markdown("---")

# --- 3. CREAR NUEVA CUENTA Y REGISTRAR MOVIMIENTO DIRECTO ---
col_c, col_r = st.columns(2)

with col_c:
  st.subheader("➕ Agregar Nueva Cuenta")
  with st.form("form_crear_cuenta", clear_on_submit=True):
    nombre_cta = st.text_input(
        "Nombre", placeholder="Ej: BBVA Débito, Efectivo Bolsa"
    )
    tipo_cta = st.selectbox(
        "Tipo", ["Débito / Nomina", "Efectivo", "Ahorro", "Crédito"]
    )
    saldo_base = st.number_input(
        "Saldo Inicial Base ($)", min_value=0.0, step=100.0
    )

    if st.form_submit_button("Crear Cuenta"):
      if nombre_cta.strip() == "":
        st.error("Ingresa un nombre válido.")
      else:
        cursor.execute(
            "INSERT INTO cuentas (nombre, tipo, saldo_inicial) VALUES (%s, %s,"
            " %s)",
            (nombre_cta.strip(), tipo_cta, saldo_base),
        )
        conn.commit()
        st.success("¡Cuenta creada!")
        st.rerun()

with col_r:
  st.subheader("💸 Registrar Movimiento Directo")
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
      tipo_t = st.selectbox("Tipo", ["Ingreso", "Egreso"])
      monto_t = st.number_input("Monto ($)", min_value=1.0, step=50.0)
      concepto_t = st.text_input("Concepto", placeholder="Ej: Depósito, retiro")

      if st.form_submit_button("Guardar Movimiento"):
        cursor.execute(
            """
                    INSERT INTO transacciones (fecha, cuenta_id, tipo, monto, concepto)
                    VALUES (%s, %s, %s, %s, %s)
                """,
            (str(fecha_t), cta_id, tipo_t, monto_t, concepto_t),
        )
        conn.commit()
        st.success("¡Movimiento registrado!")
        st.rerun()
  else:
    st.info("Crea una cuenta primero.")

st.markdown("---")

# --- 4. BITÁCORA DE TRANSACCIONES ---
st.subheader("📜 Bitácora de Transacciones en Cuentas")
df_trans = pd.read_sql_query(
    """
    SELECT t.id, t.fecha, c.nombre as cuenta, t.tipo, t.monto, t.concepto 
    FROM transacciones t
    JOIN cuentas c ON t.cuenta_id = c.id
    ORDER BY t.fecha DESC
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

  trans_a_borrar = st.selectbox(
      "Selecciona transacción a eliminar si deseas revertirla:",
      df_trans["id"].tolist(),
      format_func=lambda x: f"ID #{x} - {df_trans[df_trans['id']==x]['cuenta'].values[0]} (${df_trans[df_trans['id']==x]['monto'].values[0]:,.2f}: {df_trans[df_trans['id']==x]['concepto'].values[0]})",
  )
  if st.button("🗑️ Eliminar Transacción Seleccionada"):
    cursor.execute(
        "DELETE FROM transacciones WHERE id = %s", (int(trans_a_borrar),)
    )
    conn.commit()
    st.success("Transacción eliminada y saldo restituido.")
    st.rerun()
else:
  st.info(
      "ℹ️ Aún no hay transacciones registradas. (Los abonos a deudas que"
      " realices seleccionando una cuenta aparecerán aquí automáticamente)."
  )
