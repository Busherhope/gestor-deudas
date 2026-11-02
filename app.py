import pandas as pd
import psycopg2
import streamlit as st

# --- INTERFAZ STREAMLIT (debe ser el primer comando de Streamlit) ---
st.set_page_config(
    st.markdown("""
    <style>
        /* Fondo general de la aplicación estilo lujoso/minimalista */
        .stApp {
            background-color: #141619;
            color: #e5e7eb;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Ocultar elementos predeterminados de Streamlit que ensucian la vista */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Tarjetas y contenedores con bordes finos y sutiles (Estilo Old Money) */
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

        /* Tablas y DataFrames estilizados */
        dataframe, table {
            border-radius: 8px !important;
            overflow: hidden;
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
""", unsafe_allow_html=True)
    
    page_title="Gestor de Deudas y Nómina Catorcenal",
    page_icon="💳",
    layout="wide",
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

# --- ADMINISTRACIÓN DE ACREEDORES ---
with st.expander("➕ / ⚙️ Registrar o Administrar Acreedores (Deudas)"):
  col_nueva_deuda, col_lista_deudas = st.columns([1, 1.2])

  with col_nueva_deuda:
    st.write("#### Agregar Nueva Deuda")
    with st.form("form_nueva_deuda", clear_on_submit=True):
      nuevo_nombre = st.text_input(
          "Nombre / Emisor de la Deuda",
          placeholder="Ej: Liverpool, Banamex, etc.",
      )
      nuevo_monto = st.number_input(
          "Monto Inicial de la Deuda ($)", min_value=1.0, step=500.0
      )
      btn_guardar_deuda = st.form_submit_button("Añadir Deuda")

      if btn_guardar_deuda:
        if nuevo_nombre.strip() == "":
          st.error("Ingresa un nombre válido para el acreedor.")
        else:
          try:
            cursor.execute(
                "INSERT INTO acreedores (nombre, monto_inicial) VALUES (%s,"
                " %s)",
                (nuevo_nombre.strip(), nuevo_monto),
            )
            conn.commit()
            st.success(
                f"¡Deuda '{nuevo_nombre.strip()}' por ${nuevo_monto:,.2f}"
                " añadida!"
            )
            st.rerun()
          except psycopg2.IntegrityError:
            conn.rollback()
            st.error(
                "Ya existe un acreedor con el nombre"
                f" '{nuevo_nombre.strip()}'."
            )

  with col_lista_deudas:
    # --- EDITAR SALDO ACTUAL DE UNA DEUDA ---
    st.write("#### ✏️ Editar Saldo Actual de una Deuda")
    if not df_acreedores.empty:
      acreedor_a_editar = st.selectbox(
          "Selecciona la deuda a editar:",
          df_acreedores["nombre"].tolist(),
          key="select_editar_acreedor",
      )

      abonado_editar = (
          float(
              df_abonos[df_abonos["acreedor_nombre"] == acreedor_a_editar][
                  "monto"
              ].sum()
          )
          if not df_abonos.empty
          else 0.0
      )
      inicial_editar = float(
          df_acreedores[df_acreedores["nombre"] == acreedor_a_editar][
              "monto_inicial"
          ].iloc[0]
      )
      saldo_actual_editar = max(inicial_editar - abonado_editar, 0.0)

      st.caption(
          f"Saldo actual registrado: **${saldo_actual_editar:,.2f}** "
          f"(abonado hasta ahora: ${abonado_editar:,.2f})"
      )

      with st.form("form_editar_deuda"):
        nuevo_saldo = st.number_input(
            "Nuevo saldo actual de la deuda ($)",
            min_value=0.0,
            value=float(saldo_actual_editar),
            step=100.0,
            key=f"nuevo_saldo_{acreedor_a_editar}_{saldo_actual_editar}",
            help=(
                "Este será el saldo pendiente real, sin importar cuánto se haya"
                " abonado antes."
            ),
        )
        btn_editar_deuda = st.form_submit_button("💾 Actualizar Saldo")

        if btn_editar_deuda:
          nuevo_monto_inicial = round(float(nuevo_saldo) + abonado_editar, 2)
          cursor.execute(
              "UPDATE acreedores SET monto_inicial = %s WHERE nombre = %s",
              (nuevo_monto_inicial, acreedor_a_editar),
          )
          conn.commit()
          st.success(
              f"Saldo de '{acreedor_a_editar}' actualizado a"
              f" ${nuevo_saldo:,.2f}."
          )
          st.rerun()
    else:
      st.info("Aún no hay deudas registradas para editar.")

    st.write("---")
    st.write("#### Eliminar Deuda Existente")
    if not df_acreedores.empty:
      acreedor_a_borrar = st.selectbox(
          "Selecciona la deuda a eliminar:",
          df_acreedores["nombre"].tolist(),
          key="select_borrar_acreedor",
      )
      st.caption(
          "⚠️ Al borrar una deuda también se eliminan sus abonos. Los"
          " movimientos ya descontados en tus cuentas se conservan."
      )
      if st.button("🗑️ Eliminar Deuda Seleccionada", type="primary"):
        try:
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
              "DELETE FROM abonos WHERE acreedor_nombre = %s",
              (acreedor_a_borrar,),
          )
          conn.commit()
        except Exception as e:
          conn.rollback()
          st.error(f"No se pudo eliminar la deuda: {e}")
        else:
          st.success(f"Deuda '{acreedor_a_borrar}' eliminada.")
          st.rerun()

st.markdown("---")

# --- REGISTRO Y HISTORIAL DE ABONOS ---
col_form, col_historial = st.columns([1, 1.3])

with col_form:
  st.subheader("📝 Registrar Nuevo Abono")
  if df_cuentas.empty:
    st.caption(
        "💡 Aún no tienes cuentas. Créalas en **Mis Cuentas** para descontar tus"
        " abonos automáticamente."
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
    cuenta_sel = st.selectbox(
        "Cuenta de origen (de dónde sale el dinero)",
        opciones_cuenta,
        format_func=fmt_cuenta,
        help=(
            "Se descontará de esa cuenta y quedará registrado como"
            " transacción."
        ),
    )
    origen = st.selectbox("Origen del dinero", ORIGENES)
    notas = st.text_input("Notas adicionales", value="")

    btn_guardar = st.form_submit_button("Guardar Abono")

    if btn_guardar:
      if df_acreedores.empty:
        st.error("No hay acreedores registrados. Añade uno primero.")
      elif cuenta_sel is not None and round(monto, 2) > round(
          saldo_de_cuenta(cuenta_sel), 2
      ):
        st.error(
            f"Saldo insuficiente en la cuenta: tiene"
            f" ${saldo_de_cuenta(cuenta_sel):,.2f} y quieres abonar"
            f" ${monto:,.2f}."
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
        except Exception as e:
          conn.rollback()
          st.error(f"No se pudo guardar el abono: {e}")
        else:
          st.success(f"¡Abono de ${monto:,.2f} registrado con éxito!")
          st.rerun()

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
      st.info("Aún no has registrado ningún abono.")

  with tab_gestion:
    if not df_abonos.empty:
      abono_id_seleccionado = st.selectbox(
          "Selecciona el ID del abono a modificar:",
          df_abonos["id"].tolist(),
          format_func=lambda x: (
              f"ID #{x} -"
              f" {df_abonos[df_abonos['id']==x]['acreedor_nombre'].values[0]}"
              f" (${df_abonos[df_abonos['id']==x]['monto'].values[0]:,.2f})"
          ),
      )

      abono_datos = df_abonos[df_abonos["id"] == abono_id_seleccionado].iloc[0]
      monto_original = float(abono_datos["monto"])
      cuenta_actual = (
          None
          if pd.isna(abono_datos["cuenta_id"])
          else int(abono_datos["cuenta_id"])
      )

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
              "Monto ($)", value=monto_original, min_value=1.0
          )
          edit_cuenta = st.selectbox(
              "Cuenta de origen",
              opciones_cuenta,
              index=(
                  opciones_cuenta.index(cuenta_actual)
                  if cuenta_actual in opciones_cuenta
                  else 0
              ),
              format_func=fmt_cuenta,
              help="El saldo mostrado ya tiene descontado este abono.",
          )
          edit_origen = st.selectbox(
              "Origen",
              ORIGENES,
              index=(
                  ORIGENES.index(abono_datos["origen"])
                  if abono_datos["origen"] in ORIGENES
                  else 0
              ),
          )
          edit_notas = st.text_input("Notas", value=abono_datos["notas"] or "")

          btn_actualizar = st.form_submit_button("Actualizar Abono")

          if btn_actualizar:
            disponible = saldo_de_cuenta(edit_cuenta) + (
                monto_original if edit_cuenta == cuenta_actual else 0.0
            )
            if edit_cuenta is not None and round(edit_monto, 2) > round(
                disponible, 2
            ):
              st.error(
                  f"Saldo insuficiente: la cuenta tiene ${disponible:,.2f}"
                  " disponibles para este abono."
              )
            else:
              try:
                cursor.execute(
                    """
                                UPDATE abonos
                                SET catorcena = %s, acreedor_nombre = %s, monto = %s, origen = %s, notas = %s, cuenta_id = %s
                                WHERE id = %s
                                """,
                    (
                        edit_catorcena,
                        edit_acreedor,
                        edit_monto,
                        edit_origen,
                        edit_notas,
                        edit_cuenta,
                        int(abono_id_seleccionado),
                    ),
                )
                cursor.execute(
                    "DELETE FROM transacciones WHERE abono_id = %s",
                    (int(abono_id_seleccionado),),
                )
                if edit_cuenta is not None:
                  cursor.execute(
                      """
                                    INSERT INTO transacciones (fecha, cuenta_id, tipo, monto, concepto, abono_id)
                                    VALUES (%s, %s, 'Egreso', %s, %s, %s)
                                    """,
                      (
                          abono_datos["fecha"],
                          edit_cuenta,
                          edit_monto,
                          f"Abono a {edit_acreedor}",
                          int(abono_id_seleccionado),
                      ),
                  )
                conn.commit()
              except Exception as e:
                conn.rollback()
                st.error(f"No se pudo actualizar el abono: {e}")
              else:
                st.success("¡Abono actualizado!")
                st.rerun()

      st.markdown("---")
      with st.expander("🗑️ Eliminar Abono"):
        st.caption(
            "Si el abono salió de una cuenta, el dinero se devuelve a su saldo."
        )
        if st.button("Confirmar Eliminación", type="primary"):
          try:
            cursor.execute(
                "DELETE FROM transacciones WHERE abono_id = %s",
                (int(abono_id_seleccionado),),
            )
            cursor.execute(
                "DELETE FROM abonos WHERE id = %s",
                (int(abono_id_seleccionado),),
            )
            conn.commit()
          except Exception as e:
            conn.rollback()
            st.error(f"No se pudo eliminar el abono: {e}")
          else:
            st.success("Abono eliminado.")
            st.rerun()
    else:
      st.info("No hay abonos para modificar.")
