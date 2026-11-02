import os
import pandas as pd
import psycopg2
import streamlit as st

# --- CONEXIÓN A BASE DE DATOS EN LA NUBE (PostgreSQL / Supabase) ---
DB_URL = st.secrets.get("postgres", {}).get("url") or os.environ.get(
    "DATABASE_URL"
)


@st.cache_resource
def get_db_connection():
  if not DB_URL:
    st.error("⚠️ No se encontró la URL de la base de datos en los Secrets.")
    st.stop()
  return psycopg2.connect(DB_URL)


conn = get_db_connection()
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute("""
CREATE TABLE IF NOT EXISTS acreedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    monto_inicial NUMERIC(10, 2) NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS abonos (
    id SERIAL PRIMARY KEY,
    fecha VARCHAR(20) NOT NULL,
    catorcena VARCHAR(100) NOT NULL,
    acreedor_nombre VARCHAR(100) NOT NULL,
    monto NUMERIC(10, 2) NOT NULL,
    origen VARCHAR(100),
    notas TEXT
);
""")
conn.commit()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(
    page_title="Gestor de Deudas Catorcenal", page_icon="💳", layout="wide"
)
st.title("💳 Control y Seguimiento de Deudas")

# --- DASHBOARD DE RESUMEN ---
st.subheader("Estado Actual de Deudas")

df_acreedores = pd.read_sql_query("SELECT * FROM acreedores", conn)
df_abonos = pd.read_sql_query("SELECT * FROM abonos", conn)

if not df_acreedores.empty:
  df_acreedores["monto_inicial"] = df_acreedores["monto_inicial"].astype(float)
if not df_abonos.empty:
  df_abonos["monto"] = df_abonos["monto"].astype(float)

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

# --- ADMINISTRACIÓN DE ACREEDORES (Añadir, Editar y Eliminar) ---
with st.expander(
    "➕ / ⚙️ Registrar, Editar o Administrar Acreedores (Deudas)", expanded=True
):
  col_nueva, col_editar, col_borrar = st.columns(3)

  with col_nueva:
    st.write("#### Agregar Nueva Deuda")
    with st.form("form_nueva_deuda", clear_on_submit=True):
      nuevo_nombre = st.text_input(
          "Nombre de la Deuda", placeholder="Ej: Liverpool"
      )
      nuevo_monto = st.number_input(
          "Monto Inicial ($)", min_value=1.0, step=500.0
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

  with col_editar:
    st.write("#### Editar Monto de Deuda")
    if not df_acreedores.empty:
      with st.form("form_editar_deuda"):
        acreedor_editar = st.selectbox(
            "Selecciona Deuda:", df_acreedores["nombre"].tolist()
        )
        row_sel = df_acreedores[
            df_acreedores["nombre"] == acreedor_editar
        ].iloc[0]
        monto_actual_ed = float(row_sel["monto_inicial"])

        nuevo_monto_ed = st.number_input(
            "Nuevo Monto Inicial ($)",
            min_value=0.0,
            value=monto_actual_ed,
            step=100.0,
        )
        if st.form_submit_button("Actualizar Monto"):
          cursor.execute(
              "UPDATE acreedores SET monto_inicial = %s WHERE nombre = %s",
              (nuevo_monto_ed, acreedor_editar),
          )
          conn.commit()
          st.success(f"¡Monto de '{acreedor_editar}' actualizado con éxito!")
          st.rerun()
    else:
      st.info("No hay deudas para editar.")

  with col_borrar:
    st.write("#### Eliminar Deuda")
    if not df_acreedores.empty:
      acreedor_a_borrar = st.selectbox(
          "Selecciona a borrar:",
          df_acreedores["nombre"].tolist(),
          key="select_borrar_acreedor",
      )
      st.caption("⚠️ Borra también sus abonos asociados.")
      if st.button("🗑️ Eliminar Deuda Seleccionada", type="primary"):
        cursor.execute(
            "DELETE FROM acreedores WHERE nombre = %s", (acreedor_a_borrar,)
        )
        cursor.execute(
            "DELETE FROM abonos WHERE acreedor_nombre = %s", (acreedor_a_borrar,)
        )
        conn.commit()
        st.success(f"Deuda '{acreedor_a_borrar}' eliminada.")
        st.rerun()
