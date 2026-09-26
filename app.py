import os
import psycopg2
import pandas as pd
import streamlit as st

# --- CONEXIÓN A BASE DE DATOS EN LA NUBE (PostgreSQL / Supabase) ---
# Intenta obtener la URL desde los secrets de Streamlit Cloud o variable de entorno
DB_URL = st.secrets.get("postgres", {}).get("url") or os.environ.get("DATABASE_URL")

@st.cache_resource
def get_db_connection():
    if not DB_URL:
        st.error("⚠️ No se encontró la URL de la base de datos PostgreSQL en los Secrets.")
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

# Asegurar tipos numéricos
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
    resumen.append(
        {
            "Acreedor": nombre,
            "Deuda Inicial": f"${inicial:,.2f}",
            "Total Abonado": f"${total_abonado:,.2f}",
            "Saldo Restante": f"${max(restante, 0):,.2f}",
            "Saldo_Num": max(restante, 0),
            "% Pagado": f"{min(progreso, 100.0):.1f}%",
        }
    )

df_resumen = pd.DataFrame(resumen)

col1, col2, col3 = st.columns(3)
deuda_total_inicial = df_acreedores["monto_inicial"].sum() if not df_acreedores.empty else 0.0
total_pagado_global = df_abonos["monto"].sum() if not df_abonos.empty else 0.0
saldo_total_pendiente = deuda_total_inicial - total_pagado_global

col1.metric("Deuda Total Inicial", f"${deuda_total_inicial:,.2f}")
col2.metric(
    "Total Pagado",
    f"${total_pagado_global:,.2f}",
    f"{(total_pagado_global/deuda_total_inicial)*100 if deuda_total_inicial > 0 else 0:.1f}%",
)
col3.metric("Saldo Pendiente Global", f"${saldo_total_pendiente:,.2f}")

if not df_resumen.empty:
    st.dataframe(df_resumen.drop(columns=["Saldo_Num"]), use_container_width=True)

st.markdown("---")

# --- ASISTENTE Y DESGLOSE DE GASTOS DINÁMICO ---
st.subheader("🧮 Asistente de Distribución Catorcenal")

if "lista_gastos" not in st.session_state:
    st.session_state.lista_gastos = [
        {"concepto": "Pasajes / Transporte", "monto": 300.0, "activo": True},
        {"concepto": "Comida / Despensa", "monto": 500.0, "activo": True},
        {"concepto": "Recarga de Celular / Datos", "monto": 100.0, "activo": True},
    ]

with st.expander("🚀 Calcular distribución inteligente de mi nómina", expanded=True):
    col_inputs, col_resultados = st.columns([1.2, 1])

    with col_inputs:
        st.write("#### 1. Datos de Ingresos y Gastos")
        ingreso_neto = st.number_input(
            "💰 Ingreso Neto Depositado ($)",
            min_value=0.0,
            value=1500.0,
            step=100.0,
            help="Lo que te cayó libre en la cuenta",
        )

        st.write("---")
        st.write("📋 **Desglose de Gastos Indispensables para la Catorcena:**")

        col_new_c, col_new_m, col_new_b = st.columns([2, 1, 1])
        nuevo_concepto = col_new_c.text_input("Concepto de Gasto", placeholder="Ej: Medicamento", key="input_gast_concept")
        nuevo_monto_gasto = col_new_m.number_input("Monto ($)", min_value=0.0, value=50.0, step=10.0, key="input_gast_monto")
        if col_new_b.button("➕ Agregar", use_container_width=True):
            if nuevo_concepto.strip() != "":
                st.session_state.lista_gastos.append(
                    {"concepto": nuevo_concepto.strip(), "monto": nuevo_monto_gasto, "activo": True}
                )
                st.rerun()

        gastos_totales_calculados = 0.0
        indices_a_eliminar = []

        for i, g in enumerate(st.session_state.lista_gastos):
            col_check, col_monto, col_del = st.columns([2.5, 1, 0.5])
            activo = col_check.checkbox(f"{g['concepto']}", value=g["activo"], key=f"check_{i}")
            st.session_state.lista_gastos[i]["activo"] = activo

            monto_actualizado = col_monto.number_input(
                f"Monto #{i}", min_value=0.0, value=float(g["monto"]), step=10.0, label_visibility="collapsed", key=f"monto_{i}"
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

        st.caption(f"**Total de Gastos Seleccionados:** `${gastos_totales_calculados:,.2f} MXN`")

        st.write("---")
        colchon_emergencia = st.number_input(
            "🛡️ Colchón Imprevistos / Fondo Reserva ($)",
            min_value=0.0,
            value=100.0,
            step=50.0,
        )

        disponible_deudas = ingreso_neto - gastos_totales_calculados - colchon_emergencia

    with col_resultados:
        st.write("#### 2. Balance y Recomendación Automática")
        st.info(f"""
        * **Ingreso Neto:** `${ingreso_neto:,.2f}`
        * **(-) Gastos Indispensables:** `${gastos_totales_calculados:,.2f}`
        * **(-) Colchón de Emergencia:** `${colchon_emergencia:,.2f}`
        """)

        if disponible_deudas < 0:
            st.error(
                f"⚠️ **Atención:** Tus gastos y colchón (${gastos_totales_calculados + colchon_emergencia:,.2f}) superan tu nómina de esta catorcena (${ingreso_neto:,.2f})."
            )
            st.warning("👉 **Recomendación:** Modo Supervivencia activado. No abonar a deudas esta catorcena.")
        elif disponible_deudas == 0:
            st.warning("ℹ️ Saldo exacto para cubrir tus gastos fijos. Asignación sugerida a deudas: **$0.00**.")
        else:
            st.success(
                f"💡 **Monto Neto Disponible para Deudas:** `${disponible_deudas:,.2f} MXN`"
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
                            "Notas": nota_sug
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
            nuevo_nombre = st.text_input("Nombre / Emisor de la Deuda", placeholder="Ej: Liverpool, Banamex, etc.")
            nuevo_monto = st.number_input("Monto Inicial de la Deuda ($)", min_value=1.0, step=500.0)
            btn_guardar_deuda = st.form_submit_button("Añadir Deuda")

            if btn_guardar_deuda:
                if nuevo_nombre.strip() == "":
                    st.error("Ingresa un nombre válido para el acreedor.")
                else:
                    try:
                        cursor.execute(
                            "INSERT INTO acreedores (nombre, monto_inicial) VALUES (%s, %s)",
                            (nuevo_nombre.strip(), nuevo_monto),
                        )
                        conn.commit()
                        st.success(f"¡Deuda '{nuevo_nombre.strip()}' por ${nuevo_monto:,.2f} añadida!")
                        st.rerun()
                    except psycopg2.IntegrityError:
                        conn.rollback()
                        st.error(f"Ya existe un acreedor con el nombre '{nuevo_nombre.strip()}'.")

    with col_lista_deudas:
        st.write("#### Eliminar Deuda Existente")
        if not df_acreedores.empty:
            acreedor_a_borrar = st.selectbox(
                "Selecciona la deuda a eliminar:",
                df_acreedores["nombre"].tolist(),
                key="select_borrar_acreedor"
            )
            st.caption("⚠️ Al borrar una deuda, también se eliminarán sus abonos asociados.")
            if st.button("🗑️ Eliminar Deuda Seleccionada", type="primary"):
                cursor.execute("DELETE FROM acreedores WHERE nombre = %s", (acreedor_a_borrar,))
                cursor.execute("DELETE FROM abonos WHERE acreedor_nombre = %s", (acreedor_a_borrar,))
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
            "Acreedor", df_acreedores["nombre"].tolist() if not df_acreedores.empty else ["Sin Acreedores"]
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
                st.error("No hay acreedores registrados. Añade uno primero.")
            else:
                cursor.execute(
                    """
                    INSERT INTO abonos (fecha, catorcena, acreedor_nombre, monto, origen, notas)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """,
                    (str(fecha), catorcena, acreedor, monto, origen, notas),
                )
                conn.commit()
                st.success(f"¡Abono de ${monto:,.2f} registrado con éxito!")
                st.rerun()

with col_historial:
    st.subheader("📜 Bitácora de Abonos")
    tab_ver, tab_gestion = st.tabs(["Ver Historial", "⚙️ Editar / Eliminar"])

    with tab_ver:
        if not df_abonos.empty:
            df_mostrar = df_abonos[
                ["id", "fecha", "catorcena", "acreedor_nombre", "monto", "origen", "notas"]
            ].sort_values(by="fecha", ascending=False)
            df_mostrar.columns = ["ID", "Fecha", "Catorcena", "Acreedor", "Monto", "Origen", "Notas"]
            st.dataframe(df_mostrar, use_container_width=True)
        else:
            st.info("Aún no has registrado ningún abono.")

    with tab_gestion:
        if not df_abonos.empty:
            abono_id_seleccionado = st.selectbox(
                "Selecciona el ID del abono a modificar:",
                df_abonos["id"].tolist(),
                format_func=lambda x: f"ID #{x} - {df_abonos[df_abonos['id']==x]['acreedor_nombre'].values[0]} (${df_abonos[df_abonos['id']==x]['monto'].values[0]:,.2f})",
            )

            abono_datos = df_abonos[df_abonos["id"] == abono_id_seleccionado].iloc[0]

            with st.expander("✏️ Editar Abono", expanded=True):
                with st.form("form_editar_abono"):
                    edit_catorcena = st.text_input("Catorcena", value=abono_datos["catorcena"])
                    edit_acreedor = st.selectbox(
                        "Acreedor",
                        df_acreedores["nombre"].tolist(),
                        index=df_acreedores["nombre"].tolist().index(abono_datos["acreedor_nombre"]) if abono_datos["acreedor_nombre"] in df_acreedores["nombre"].tolist() else 0,
                    )
                    edit_monto = st.number_input("Monto ($)", value=float(abono_datos["monto"]), min_value=1.0)
                    edit_origen = st.selectbox(
                        "Origen",
                        ["Sueldo Base", "Bono Desempeño", "Nomix / Adelanto", "Otro"],
                        index=["Sueldo Base", "Bono Desempeño", "Nomix / Adelanto", "Otro"].index(abono_datos["origen"]),
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
                            (edit_catorcena, edit_acreedor, edit_monto, edit_origen, edit_notas, int(abono_id_seleccionado)),
                        )
                        conn.commit()
                        st.success("¡Abono actualizado!")
                        st.rerun()

            st.markdown("---")
            with st.expander("🗑️ Eliminar Abono"):
                if st.button("Confirmar Eliminación", type="primary"):
                    cursor.execute("DELETE FROM abonos WHERE id = %s", (int(abono_id_seleccionado),))
                    conn.commit()
                    st.success("Abono eliminado.")
                    st.rerun()
        else:
            st.info("No hay abonos para modificar.")