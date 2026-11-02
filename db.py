import pandas as pd
import streamlit as st
from db import get_conn, init_db, obtener_cuentas_con_saldo

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

# --- CREAR Y EDITAR CUENTAS ---
col_crear, col_editar_cta = st.columns(2)

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

with col_editar_cta:
  st.subheader("✏️ Editar o Eliminar Cuenta")
  if not df_cuentas.empty:
    cuenta_sel_id = st.selectbox(
        "Selecciona cuenta:",
        df_cuentas["id"].tolist(),
        format_func=lambda x: df_cuentas[df_cuentas["id"] == x][
            "nombre"
        ].values[0],
    )
    cta_row = df_cuentas[df_cuentas["id"] == cuenta_sel_id].iloc[0]

    with st.form("form_editar_cuenta"):
      nuevo_nom = st.text_input("Nombre", value=cta_row["nombre"])
      nuevo_base = st.number_input(
          "Saldo Inicial Base ($)",
          value=float(cta_row["saldo_inicial"]),
          step=100.0,
      )

      if st.form_submit_button("Actualizar Cuenta"):
        cursor.execute(
            "UPDATE cuentas SET nombre = %s, saldo_inicial = %s WHERE id = %s",
            (nuevo_nom, nuevo_base, int(cuenta_sel_id)),
        )
        conn.commit()
        st.success("¡Cuenta actualizada!")
        st.rerun()

    if st.button("🗑️ Eliminar Cuenta Seleccionada", type="primary"):
      try:
        cursor.execute("DELETE FROM cuentas WHERE id = %s", (int(cuenta_sel_id),))
        conn.commit()
        st.success("Cuenta eliminada.")
        st.rerun()
      except Exception as e:
        conn.rollback()
        st.error(f"No se pudo eliminar: {e}")
  else:
    st.info("No hay cuentas para editar.")

st.markdown("---")

# --- REGISTRAR MOVIMIENTO DIRECTO ---
st.subheader("💸 Registrar Ingreso / Gasto Directo en Cuenta")
if not df_cuentas.empty:
  with st.form("form_transaccion_directa", clear_on_submit=True):
    col_t1, col_t2, col_t3 = st.columns(3)
    fecha_t = col_t1.date_input("Fecha")
    cta_id = col_t2.selectbox(
        "Cuenta",
        df_cuentas["id"].tolist(),
        format_func=lambda x: df_cuentas[df_cuentas["id"] == x][
            "nombre"
        ].values[0],
    )
    tipo_t = col_t3.selectbox("Tipo de Movimiento", ["Ingreso", "Egreso"])

    col_t4, col_t5 = st.columns(2)
    monto_t = col_t4.number_input("Monto ($)", min_value=1.0, step=50.0)
    concepto_t = col_t5.text_input(
        "Concepto / Descripción", placeholder="Ej: Depósito nómina, retiro cajero"
    )

    if st.form_submit_button("Registrar Movimiento"):
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

st.markdown("---")

# --- HISTORIAL DE TRANSACCIONES ---
st.subheader("📜 Bitácora de Transacciones en Cuentas")
df_trans = pd.read_sql_query(
    """
    T.id, t.fecha, c.nombre as cuenta, t.tipo, t.monto, t.concepto 
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
      "Selecciona ID de transacción a eliminar si deseas revertirla:",
      df_trans["id"].tolist(),
      format_func=lambda x: f"ID #{x} - {df_trans[df_trans['id']==x]['cuenta'].values[0]} (${df_trans[df_trans['id']==x]['monto'].values[0]:,.2f}: {df_trans[df_trans['id']==x]['concepto'].values[0]})",
  )
  if st.button("🗑️ Eliminar Transacción Seleccionada"):
    try:
      cursor.execute(
          "DELETE FROM transacciones WHERE id = %s", (int(trans_a_borrar),)
      )
      conn.commit()
      st.success("Transacción eliminada y saldo restituido.")
      st.rerun()
    except Exception as e:
      conn.rollback()
      st.error(f"Error al eliminar: {e}")
else:
  st.info("Aún no hay transacciones registradas.")
