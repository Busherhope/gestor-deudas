import os
import pandas as pd
import psycopg2
import streamlit as st


@st.cache_resource
def get_conn():
  db_url = st.secrets.get("postgres", {}).get("url") or os.environ.get(
      "DATABASE_URL"
  )
  if not db_url:
    st.error("⚠️ No se encontró la URL de la base de datos en los Secrets.")
    st.stop()
  return psycopg2.connect(db_url)


def init_db(conn):
  cursor = conn.cursor()
  # Tabla de Acreedores (Deudas)
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS acreedores (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(100) UNIQUE NOT NULL,
        monto_inicial NUMERIC(10, 2) NOT NULL
    );
    """)

  # Tabla de Abonos a Deudas
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS abonos (
        id SERIAL PRIMARY KEY,
        fecha VARCHAR(20) NOT NULL,
        catorcena VARCHAR(100) NOT NULL,
        acreedor_nombre VARCHAR(100) NOT NULL,
        monto NUMERIC(10, 2) NOT NULL,
        origen VARCHAR(100),
        notas TEXT,
        cuenta_id INTEGER
    );
    """)

  # Tabla de Cuentas (Débito, Efectivo, etc.)
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS cuentas (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(100) UNIQUE NOT NULL,
        tipo VARCHAR(50) NOT NULL,
        saldo_inicial NUMERIC(10, 2) DEFAULT 0.00
    );
    """)

  # Tabla de Transacciones (Ingresos/Egresos en cuentas)
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS transacciones (
        id SERIAL PRIMARY KEY,
        fecha VARCHAR(20) NOT NULL,
        cuenta_id INTEGER REFERENCES cuentas(id) ON DELETE CASCADE,
        tipo VARCHAR(20) NOT NULL,
        monto NUMERIC(10, 2) NOT NULL,
        concepto TEXT,
        abono_id INTEGER
    );
    """)
  conn.commit()


def obtener_cuentas_con_saldo(conn):
  query = """
        SELECT 
            c.id, 
            c.nombre, 
            c.tipo, 
            c.saldo_inicial,
            COALESCE(SUM(CASE WHEN t.tipo = 'Ingreso' THEN t.monto ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN t.tipo = 'Egreso' THEN t.monto ELSE 0 END), 0) as movimiento_neto,
            (c.saldo_inicial + 
             COALESCE(SUM(CASE WHEN t.tipo = 'Ingreso' THEN t.monto ELSE 0 END), 0) -
             COALESCE(SUM(CASE WHEN t.tipo = 'Egreso' THEN t.monto ELSE 0 END), 0)) as saldo
        FROM cuentas c
        LEFT JOIN transacciones t ON c.id = t.cuenta_id
        GROUP BY c.id, c.nombre, c.tipo, c.saldo_inicial
        ORDER BY c.id;
    """
  return pd.read_sql_query(query, conn)
