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
    st.error(
        "⚠️ No se encontró la URL de la base de datos PostgreSQL en los"
        " Secrets."
    )
    st.stop()
  return psycopg2.connect(DB_URL)


conn = get_db_connection()
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute("""
CREATE TABLE IF NOT EXISTS acreedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    monto_inicial NUMERIC(10, 2) NOT NULL,
    ajuste_intereses NUMERIC(10, 2) DEFAULT 0.00
);
""")

# Asegurar que la columna ajuste_intereses exista si la tabla ya fue creada previamente
cursor.execute("""
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='acreedores' AND column_name='ajuste_intereses') THEN
        ALTER TABLE acreedores ADD COLUMN ajuste_intereses NUMERIC(10, 2) DEFAULT 0.00;
    END IF;
END $$;
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
    page_title="Gestor de Deudas y Nómina Catorcenal",
    page_icon="💳",
    layout="wide",
)
st.title("💳 Control de Nómina y Seguimiento de Deudas")

# --- DASHBOARD DE RESUMEN DE DEUDAS ---
st.subheader("Estado Actual de Deudas")

df_acreedores = pd.read_sql_query("SELECT * FROM acreedores", conn)
df_abonos = pd.read_sql_query("SELECT * FROM abonos", conn)

# Asegurar tipos numéricos
if not df_acreedores.empty:
  df_acreedores["monto_inicial"] = df_acreedores["monto_inicial"].astype(float)
  if "ajuste_intereses" in df_acreedores.columns:
    df_acreedores["ajuste_intereses"] = df_acreedores["ajuste_intereses"].astype(
        float
    )
  else:
    df_acreedores["ajuste_intereses"] = 0.0
if not df_abonos.empty:
  df_abonos["monto"] = df_abonos["monto"].astype(float)

resumen = []
for _, row in df_acreedores.iterrows():
  nombre = row["nombre"]
  inicial = float(row["monto_inicial"])
  ajuste = float(row.get("ajuste_intereses", 0.0))

  total_abonado = (
      df_abonos[df_abonos["acreedor_nombre"] == nombre]["monto"].sum()
      if not df_abonos.empty
      else 0.0
  )

  # Saldo restante considerando la base inicial, abonos y los intereses diarios sumados
  restante = (inicial - total_abonado) + ajuste
  progreso = (total_abonado / inicial) * 100 if inicial > 0 else 100.0

  resumen.append({
      "Acreedor": nombre,
      "Deuda Inicial": f"${inicial:,.2f}",
      "Total Abonado": f"${total_abonado:,.2f}",
      "Ajuste/Intereses": f"${ajuste:,.2f}",
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
saldo_total_pendiente = sum([r["Saldo_Num"] for r in resumen])

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
        ingreso_neto - gastos_totales_calculados - colchon_emergencia
    )

  with col_resultados:
    st.write("#### 2. Balance y Recomendación Automática")
    st.info(f"""
        * **Ingreso Neto (Nómina):** `${ingreso_neto:,.2f}`
        * **(-) Gastos Indispensables:** `${gastos_totales_calculados:,.2f}`
        * **(-) Colchón de Emergencia:** `${colchon_emergencia:,.2f}`
        """)

    if disponible_deudas < 0:
      st.error(
          f"⚠️ **Atención:** Tus gastos y colchón"
          f" (${gastos_totales_calculados + colchon_emergencia:,.2f}) superan tu"
          f" nómina de esta catorcena (${ingreso_neto:,.2f})."
      )
      st.warning(
          "👉 **Recomendación:** Modo Supervivencia activado. No abonar a"
          " deudas esta catorcena."
      )
    elif disponible_deudas == 0:
      st.warning(
          "ℹ️ Saldo exacto para cubrir tus gastos fijos. Asignación sugerida a"
          " deudas: **$0.00**."
      )
    else:
      st.success(
          f"💡 **Monto Neto Disponible para Deudas:** `${disponible_deudas:,.2f}"
          " MXN`"
      )
      st.write("**Estrategia Sugerida (Bola de Nieve):**")

      if not df_resumen.empty:
        deudas_pendientes = df_resumen[df_resumen["Saldo_Num"] > 0].sort_values(
            by="Saldo_Num", ascending=True
        )

        if not deudas_pendientes.empty:
          sugerencias = []
          monto_restante_distribuir = disponible_deudas

          for _, d in deudas_pendientes.iterrows():
            if monto_restante_distribuir <= 0:
              break

            saldo_deuda = d["Saldo_Num"]
            acreedor_nom = d["Acreedor"]

            if monto_restante_distribuir >= saldo_deuda:
              abono_sugerido = saldo_deuda
              nota_sug = "🎯 ¡LIQUIDA LA DEUDA COMPLETA!"
            else:
              abono_sugerido = monto_restante_distribuir
              nota_sug = "📉 Abono directo a capital"

            sugerencias.append({
                "Acreedor": acreedor_nom,
                "Abono Sugerido": f"${abono_sugerido:,.2f}",
                "Notas": nota_sug,
            })
            monto_restante_distribuir -= abono_sugerido

          st.table(pd.DataFrame(sugerencias))
        else:
          st.balloons()
          st.success("¡Excelente! No hay deudas pendientes por liquidar.")

st.markdown("---")

# --- ADMINISTRACIÓN DE ACREEDORES, EDICIÓN Y SINCRONIZACIÓN ---
with st.expander(
    "➕ / ⚙️ Registrar, Editar o Sincronizar Acreedores (Deudas)", expanded=False
):
  col_nueva_deuda, col_editar_deuda, col_sync, col_lista_deudas = st.columns(
      [1, 1, 1, 1]
  )

  with col_nueva_deuda:
    st.write("#### ➕ Agregar Deuda")
    with st.form("form_nueva_deuda", clear_on_submit=True):
      nuevo_nombre = st.text_input(
          "Nombre / Emisor", placeholder="Ej: BANCO AZTECA"
      )
      nuevo_monto = st.number_input(
          "Monto Inicial ($)", min_value=1.0, step=500.0
      )
      btn_guardar_deuda = st.form_submit_button("Añadir")

      if btn_guardar_deuda:
        if nuevo_nombre.strip() == "":
          st.error("Ingresa un nombre válido.")
        else:
          try:
            cursor.execute(
                "INSERT INTO acreedores (nombre, monto_inicial,"
                " ajuste_intereses) VALUES (%s, %s, 0.00)",
                (nuevo_nombre.strip(), nuevo_monto),
            )
            conn.commit()
            st.success(f"¡Deuda '{nuevo_nombre.strip()}' añadida!")
            st.rerun()
          except psycopg2.IntegrityError:
            conn.rollback()
            st.error("El acreedor ya existe.")

  with col_editar_deuda:
    st.write("#### ✏️ Modificar Monto")
    if not df_acreedores.empty:
      with st.form("form_editar_monto_inicial"):
        ac_editar = st.selectbox(
            "Selecciona Deuda",
            df_acreedores["nombre"].tolist(),
            key="sel_edit_deuda",
        )
        row_actual = df_acreedores[df_acreedores["nombre"] == ac_editar].iloc[0]
        monto_actual = float(row_actual["monto_inicial"])

        nuevo_monto_inicial = st.number_input(
            "Nuevo Monto Inicial ($)",
            min_value=0.0,
            value=monto_actual,
            step=100.0,
        )
        btn_actualizar_deuda = st.form_submit_button("Actualizar Monto")

        if btn_actualizar_deuda:
          cursor.execute(
              "UPDATE acreedores SET monto_inicial = %s WHERE nombre = %s",
              (nuevo_monto_inicial, ac_editar),
          )
          conn.commit()
          st.success(f"¡Monto inicial de {ac_editar} actualizado!")
          st.rerun()

  with col_sync:
    st.write("#### 🔄 Sincronizar App")
    if not df_acreedores.empty:
      with st.form("form_sync_intereses"):
        acreedor_sync = st.selectbox(
            "Selecciona Deuda",
            df_acreedores["nombre"].tolist(),
            key="sel_sync_ac",
        )
        saldo_real_app = st.number_input(
            "Saldo App ($)", min_value=0.0, value=18829.0, step=50.0
        )
        btn_sincronizar = st.form_submit_button("Sincronizar")

        if btn_sincronizar:
          row_ac = df_acreedores[df_acreedores["nombre"] == acreedor_sync].iloc[
              0
          ]
          m_inicial = float(row_ac["monto_inicial"])
          t_abonos = (
              df_abonos[df_abonos["acreedor_nombre"] == acreedor_sync][
                  "monto"
              ].sum()
              if not df_abonos.empty
              else 0.0
          )
          nuevo_ajuste = saldo_real_app - (m_inicial - t_abonos)

          cursor.execute(
              "UPDATE acreedores SET ajuste_intereses = %s WHERE nombre = %s",
              (nuevo_ajuste, acreedor_sync),
          )
          conn.commit()
          st.success(f"¡Saldo de {acreedor_sync} sincronizado!")
          st.rerun()

  with col_lista_deudas:
    st.write("#### 🗑️ Borrar Deuda")
    if not df_acreedores.empty:
      acreedor_a_borrar = st.selectbox(
          "Selecciona a borrar:",
          df_acreedores["nombre"].tolist(),
          key="select_borrar_acreedor",
      )
      if st.button("Eliminar Deuda", type="primary"):
        cursor.execute(
            "DELETE FROM acreedores WHERE nombre = %s", (acreedor_a_borrar,)
        )
        cursor.execute(
            "DELETE FROM abonos WHERE acreedor_nombre = %s", (acreedor_a_borrar,)
        )
        conn.commit()
        st.success(f"Deuda '{acreedor_a_borrar}' eliminada.")
        st.rerun()

st.markdown("---")

# --- REGISTRO Y HISTORIAL DE ABONOS ---
col_form, col_historial = st.columns([1, 1.3])

with col_form:
  st.subheader("📝 Registrar Nuevo Abono")
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
    origen = st.selectbox(
        "Origen del dinero",
        ["Sueldo Base", "Bono Desempeño", "Nomix / Adelanto", "Otro"],
    )
    notas = st.text_input("Notas adicionales", value="")

    btn_guardar = st.form_submit_button("Guardar Abono")

    if btn_guardar:
      if df_acreedores.empty:
        st.error("No hay acreedores registrados.")
      else:
        cursor.execute(
            """
                INSERT INTO abonos (fecha, catorcena, acreedor_nombre, monto, origen, notas)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(fecha), catorcena, acreedor, monto, origen, notas),
        )
        conn.commit()
        st.success(f"¡Abono de ${monto:,.2f} registrado!")
        st.rerun()

with col_historial:
  st.subheader("📜 Bitácora de Abonos")
  tab_ver, tab_gestion = st.tabs(["Ver Historial", "⚙️ Editar / Eliminar"])

  with tab_ver:
    if not df_abonos.empty:
      df_mostrar = df_abonos[
          ["id", "fecha", "catorcena", "acreedor_nombre", "monto", "origen", "notas"]
      ].sort_values(by="fecha", ascending=False)
      df_mostrar.columns = [
          "ID",
          "Fecha",
          "Catorcena",
          "Acreedor",
          "Monto",
          "Origen",
          "Notas",
      ]
      st.dataframe(df_mostrar, use_container_width=True)
    else:
      st.info("Aún no hay abonos registrados.")

  with tab_gestion:
    if not df_abonos.empty:
      abono_id_seleccionado = st.selectbox(
          "Selecciona ID a modificar:",
          df_abonos["id"].tolist(),
          format_func=lambda x: (
              f"ID #{x} -"
              f" {df_abonos[df_abonos['id']==x]['acreedor_nombre'].values[0]}"
              f" (${df_abonos[df_abonos['id']==x]['monto'].values[0]:,.2f})"
          ),
      )

      abono_datos = df_abonos[df_abonos["id"] == abono_id_seleccionado].iloc[0]

      with st.expander("✏️ Editar Abono", expanded=True):
        with st.form("form_editar_abono"):
          edit_catorcena = st.text_input(
              "Catorcena", value=abono_datos["catorcena"]
          )
          edit_acreedor = st.selectbox(
              "Acreedor",
              df_acreedores["nombre"].tolist(),
              index=(
                  df_acreedores["nombre"].tolist().index(
                      abono_datos["acreedor_nombre"]
                  )
                  if abono_datos["acreedor_nombre"]
                  in df_acreedores["nombre"].tolist()
                  else 0
              ),
          )
          edit_monto = st.number_input(
              "Monto ($)", value=float(abono_datos["monto"]), min_value=1.0
          )
          edit_origen = st.selectbox(
              "Origen",
              ["Sueldo Base", "Bono Desempeño", "Nomix / Adelanto", "Otro"],
              index=[
                  "Sueldo Base",
                  "Bono Desempeño",
                  "Nomix / Adelanto",
                  "Otro",
              ].index(abono_datos["origen"]),
          )
          edit_notas = st.text_input("Notas", value=abono_datos["notas"])

          btn_actualizar = st.form_submit_button("Actualizar Abono")

          if btn_actualizar:
            cursor.execute(
                """
                            UPDATE abonos
                            SET catorcena = %s, acreedor_nombre = %s, monto = %s, origen = %s, notas = %s
                            WHERE id = %s
                        """,
                (
                    edit_catorcena,
                    edit_acreedor,
                    edit_monto,
                    edit_origen,
                    edit_notas,
                    int(abono_id_seleccionado),
                ),
            )
            conn.commit()
            st.success("¡Abono actualizado!")
            st.rerun()

      st.markdown("---")
      with st.expander("🗑️ Eliminar Abono"):
        if st.button("Confirmar Eliminación Abono", type="primary"):
          cursor.execute(
              "DELETE FROM abonos WHERE id = %s", (int(abono_id_seleccionado),)
          )
          conn.commit()
          st.success("Abono eliminado.")
          st.rerun()
    else:
      st.info("No hay abonos para modificar.")
