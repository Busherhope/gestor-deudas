import pandas as pd
import psycopg2
import streamlit as st

# --- INTERFAZ STREAMLIT ---
st.set_page_config(
    page_title="Gestor de Deudas Catorcenal", page_icon="💳", layout="wide"
)

from db import get_conn, init_db, obtener_cuentas_con_saldo

# --- CONEXIÓN A BASE DE DATOS EN LA NUBE ---
conn = get_conn()
init_db(conn)
cursor = conn.cursor()

ORIGENES = ["Sueldo Base", "Bono Desempeño", "Nomix / Adelanto", "Otro"]

st.title("💳 Control y Seguimiento de Deudas")

if st.button("🏦 Ir a Mis Cuentas (débito y efectivo)"):
  st.switch_page("pages/1_Cuentas.py")

# --- DASHBOARD DE RESUMEN ---
st.subheader("Estado Actual de Deudas")

df_acreedores = pd.read_sql_query("SELECT * FROM acreedores", conn)
df_abonos = pd.read_sql_query("SELECT * FROM abonos", conn)
df_cuentas = obtener_cuentas_con_saldo(conn)

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

# --- ADMINISTRACIÓN DE ACREEDORES ---
with st.expander("➕ / ⚙️ Registrar o Administrar Acreedores (Deudas)"):
  col_nueva_deuda, col_editar_deuda, col_lista_deudas = st.columns(3)

  with col_nueva_deuda:
    st.write("#### Agregar Nueva Deuda")
    with st.form("form_nueva_deuda", clear_on_submit=True):
      nuevo_nombre = st.text_input(
          "Nombre / Emisor de la Deuda", placeholder="Ej: Liverpool"
      )
      nuevo_monto = st.number_input(
          "Monto Inicial de la Deuda ($)", min_value=1.0, step=500.0
      )
      if st.form_submit_button("Añadir Deuda"):
        if nuevo_nombre.strip() == "":
          st.error("Ingresa un nombre válido.")
        else:
          try:
            cursor.execute(
                "INSERT INTO acreedores (nombre, monto_inicial) VALUES (%s,"
                " %s)",
                (nuevo_nombre.strip(), nuevo_monto),
            )
            conn.commit()
            st.success(f"¡Deuda '{nuevo_nombre.strip()}' añadida!")
            st.rerun()
          except psycopg2.IntegrityError:
            conn.rollback()
            st.error("El acreedor ya existe.")

  with col_editar_deuda:
    st.write("#### ✏️ Editar Saldo Actual")
    if not df_acreedores.empty:
      acreedor_a_editar = st.selectbox(
          "Selecciona deuda:",
          df_acreedores["nombre"].tolist(),
          key="sel_ed_deuda_ principal",
      )
      abonado_ ed = (
          float(
              df_abonos[df_abonos["acreedor_nombre"] == acreedor_a_editar][
                  "monto"
              ].sum()
          )
          if not df_abonos.empty
          else 0.0
      )
      inicial_ed = float(
          df_acreedores[df_acreedores["nombre"] == acreedor_a_editar][
              "monto_inicial"
          ].iloc[0]
      )
      saldo_act = max(inicial_ed - abonado_ed, 0.0)

      with st.form("form_editar_saldo_deuda"):
        nuevo_s = st.number_input(
            "Nuevo saldo ($)", min_value=0.0, value=saldo_act, step=100.0
        )
        if st.form_submit_button("Actualizar Saldo"):
          nuevo_inicial = round(float(nuevo_s) + abonado_ed, 2)
          cursor.execute(
              "UPDATE acreedores SET monto_inicial = %s WHERE nombre = %s",
              (nuevo_inicial, acreedor_a_editar),
          )
          conn.commit()
          st.success("¡Saldo actualizado!")
          st.rerun()

  with col_lista_deudas:
    st.write("#### Eliminar Deuda")
    if not df_acreedores.empty:
      acreedor_a_borrar = st.selectbox(
          "Selecciona a borrar:",
          df_acreedores["nombre"].tolist(),
          key="select_borrar_acreedor",
      )
      if st.button("🗑️ Eliminar Deuda", type="primary"):
        cursor.execute(
            """
                    UPDATE transacciones SET abono_id = NULL
                    WHERE abono_id IN (SELECT id FROM abonos WHERE acreedor_nombre = %s)
                """,
            (acreedor_a_borrar,),
        )
        cursor.execute(
            "DELETE FROM acreedores WHERE nombre = %s", (acreedor_a_borrar,)
        )
        cursor.execute(
            "DELETE FROM abonos WHERE acreedor_nombre = %s", (acreedor_a_borrar,)
        )
        conn.commit()
        st.success("Deuda eliminada.")
        st.rerun()

st.markdown("---")

# --- REGISTRO Y HISTORIAL DE ABONOS ---
col_form, col_historial = st.columns([1, 1.3])

with col_form:
  st.subheader("📝 Registrar Nuevo Abono")
  if df_cuentas.empty:
    st.caption(
        "💡 Consejo: Crea cuentas en la sección **Mis Cuentas** para descontar"
        " tus abonos automáticamente."
    )

  with st.form("form_abono", clear_on_submit=True):
    fecha = st.date_input("Fecha de pago")
    catorcena = st.text_input("Catorcena / Periodo", value="25 de Septiembre")
    acreedor = st.selectbox(
        "Acreedor",
        (
            df_acreedores["nombre"].tolist()
            if not df_acreedores.empty
            else ["Sin Acreedores"]
        ),
    )
    monto = st.number_input("Monto a abonar ($)", min_value=1.0, step=50.0)

    # AQUÍ ES DONDE APARECEN TUS CUENTAS CREADAS
    cuenta_sel = st.selectbox(
        "Cuenta de origen (de dónde sale el dinero)",
        opciones_cuenta,
        format_func=fmt_cuenta,
        help=(
            "Selecciona tu tarjeta de débito o efectivo para descontar el"
            " saldo."
        ),
    )

    origen = st.selectbox("Origen del ingreso / fondo", ORIGENES)
    notas = st.text_input("Notas adicionales", value="")

    btn_guardar = st.form_submit_button("Guardar Abono")

    if btn_guardar:
      if df_acreedores.empty:
        st.error("No hay acreedores registrados.")
      elif cuenta_sel is not None and round(monto, 2) > round(
          saldo_de_cuenta(cuenta_sel), 2
      ):
        st.error(
            f"Saldo insuficiente en la cuenta seleccionada (Tienes"
            f" ${saldo_de_cuenta(cuenta_sel):,.2f})."
        )
      else:
        try:
          cursor.execute(
              """
                        INSERT INTO abonos (fecha, catorcena, acreedor_nombre, monto, origen, notas, cuenta_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """,
              (
                  str(fecha),
                  catorcena,
                  acreedor,
                  monto,
                  origen,
                  notas,
                  cuenta_sel,
              ),
          )
          nuevo_abono_id = cursor.fetchone()[0]

          if cuenta_sel is not None:
            cursor.execute(
                """
                            INSERT INTO transacciones (fecha, cuenta_id, tipo, monto, concepto, abono_id)
                            VALUES (%s, %s, 'Egreso', %s, %s, %s)
                        """,
                (
                    str(fecha),
                    cuenta_sel,
                    monto,
                    f"Abono a {acreedor}",
                    nuevo_abono_id,
                ),
            )

          conn.commit()
          st.success(f"¡Abono de ${monto:,.2f} registrado con éxito!")
          st.rerun()
        except Exception as e:
          conn.rollback()
          st.error(f"Error al registrar: {e}")

with col_historial:
  st.subheader("📜 Bitácora de Abonos")
  tab_ver, tab_gestion = st.tabs(["Ver Historial", "⚙️ Editar / Eliminar"])

  with tab_ver:
    if not df_abonos.empty:
      df_mostrar = df_abonos.copy()
      nombres_cuentas = (
          dict(zip(df_cuentas["id"], df_cuentas["nombre"]))
          if not df_cuentas.empty
          else {}
      )
      df_mostrar["cuenta"] = df_mostrar["cuenta_id"].map(
          lambda x: nombres_cuentas.get(int(x), "—") if pd.notna(x) else "—"
      )
      df_mostrar = df_mostrar[[
          "id",
          "fecha",
          "catorcena",
          "acreedor_nombre",
          "monto",
          "cuenta",
          "origen",
          "notas",
      ]].sort_values(by="fecha", ascending=False)
      df_mostrar.columns = [
          "ID",
          "Fecha",
          "Catorcena",
          "Acreedor",
          "Monto",
          "Cuenta",
          "Origen",
          "Notas",
      ]
      st.dataframe(df_mostrar, use_container_width=True)
    else:
      st.info("Aún no hay abonos registrados.")

  with tab_gestion:
    if not df_abonos.empty:
      abono_id_sel = st.selectbox(
          "Selecciona ID del abono:", df_abonos["id"].tolist()
      )
      abono_dat = df_abonos[df_abonos["id"] == abono_id_sel].iloc[0]
      monto_orig = float(abono_dat["monto"])
      cta_act = (
          None if pd.isna(abono_dat["cuenta_id"]) else int(abono_dat["cuenta_id"])
      )

      with st.form("form_edit_ab"):
        e_cat = st.text_input("Catorcena", value=abono_dat["catorcena"])
        e_acr = st.selectbox(
            "Acreedor",
            df_acreedores["nombre"].tolist(),
            index=df_acreedores["nombre"].tolist().index(
                abono_dat["acreedor_nombre"]
            ),
        )
        e_mon = st.number_input("Monto ($)", value=monto_orig, min_value=1.0)
        e_cta = st.selectbox(
            "Cuenta de origen",
            opciones_cuenta,
            index=(
                opciones_cuenta.index(cta_act) if cta_act in opciones_cuenta else 0
            ),
            format_func=fmt_cuenta,
        )
        e_ori = st.selectbox(
            "Origen",
            ORIGENES,
            index=(
                ORIGENES.index(abono_dat["origen"])
                if abono_dat["origen"] in ORIGENES
                else 0
            ),
        )
        e_not = st.text_input("Notas", value=abono_dat["notas"] or "")

        if st.form_submit_button("Actualizar Abono"):
          try:
            cursor.execute(
                """
                            UPDATE abonos SET catorcena = %s, acreedor_nombre = %s, monto = %s, origen = %s, notas = %s, cuenta_id = %s
                            WHERE id = %s
                        """,
                (e_cat, e_acr, e_mon, e_ori, e_not, e_cta, int(abono_id_sel)),
            )
            cursor.execute(
                "DELETE FROM transacciones WHERE abono_id = %s",
                (int(abono_id_sel),),
            )
            if e_cta is not None:
              cursor.execute(
                  """
                                INSERT INTO transacciones (fecha, cuenta_id, tipo, monto, concepto, abono_id)
                                VALUES (%s, %s, 'Egreso', %s, %s, %s)
                            """,
                  (
                      abono_dat["fecha"],
                      e_cta,
                      e_mon,
                      f"Abono a {e_acr}",
                      int(abono_id_sel),
                  ),
              )
            conn.commit()
            st.success("¡Abono actualizado!")
            st.rerun()
          except Exception as e:
            conn.rollback()
            st.error(f"Error: {e}")

      if st.button("🗑️ Eliminar este Abono"):
        cursor.execute(
            "DELETE FROM transacciones WHERE abono_id = %s",
            (int(abono_id_sel),),
        )
        cursor.execute("DELETE FROM abonos WHERE id = %s", (int(abono_id_sel),))
        conn.commit()
        st.success("Abono eliminado y saldo devuelto a la cuenta.")
        st.rerun()
    else:
      st.info("No hay abonos para editar.")
