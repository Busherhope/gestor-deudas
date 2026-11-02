
import streamlit as st
import psycopg2
import pandas as pd


# ==========================================
# CONEXIÓN A POSTGRESQL
# ==========================================

def get_conn():
    """
    Obtiene conexión a PostgreSQL usando los secretos
    configurados en Streamlit Cloud.
    """

    try:
        if "DATABASE_URL" in st.secrets:
            return psycopg2.connect(
                st.secrets["DATABASE_URL"],
                sslmode="require"
            )

        if "postgres" in st.secrets:
            config = st.secrets["postgres"]

            return psycopg2.connect(
                host=config["host"],
                database=config["database"],
                user=config.get("username", config.get("user")),
                password=config["password"],
                port=config.get("port", 5432),
                sslmode=config.get("sslmode", "require")
            )

        return psycopg2.connect(
            host=st.secrets["DB_HOST"],
            database=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=st.secrets.get("DB_PORT", 5432),
            sslmode=st.secrets.get("DB_SSLMODE", "require")
        )

    except Exception as e:
        raise RuntimeError(
            "No se pudo conectar a PostgreSQL. "
            "Revisa las credenciales de Streamlit Secrets."
        ) from e


# ==========================================
# CREACIÓN DE TABLAS
# ==========================================

def init_db(conn):

    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acreedores (
                id SERIAL PRIMARY KEY,
                nombre TEXT UNIQUE NOT NULL,
                monto_inicial NUMERIC(14,2) NOT NULL DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cuentas (
                id SERIAL PRIMARY KEY,
                nombre TEXT UNIQUE NOT NULL,
                tipo TEXT NOT NULL,
                saldo_inicial NUMERIC(14,2) NOT NULL DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS abonos (
                id SERIAL PRIMARY KEY,
                fecha DATE NOT NULL,
                catorcena TEXT,
                acreedor_nombre TEXT NOT NULL,
                monto NUMERIC(14,2) NOT NULL,
                origen TEXT,
                notas TEXT,
                cuenta_id INTEGER REFERENCES cuentas(id)
                    ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transacciones (
                id SERIAL PRIMARY KEY,
                fecha DATE NOT NULL,
                cuenta_id INTEGER REFERENCES cuentas(id)
                    ON DELETE SET NULL,
                tipo TEXT NOT NULL,
                monto NUMERIC(14,2) NOT NULL,
                concepto TEXT,
                abono_id INTEGER REFERENCES abonos(id)
                    ON DELETE SET NULL
            )
        """)

        # Compatibilidad con tablas existentes:
        cursor.execute("""
            ALTER TABLE abonos
            ADD COLUMN IF NOT EXISTS cuenta_id INTEGER
        """)

        cursor.execute("""
            ALTER TABLE transacciones
            ADD COLUMN IF NOT EXISTS abono_id INTEGER
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()


# ==========================================
# CONSULTAR CUENTAS Y SALDOS
# ==========================================

def obtener_cuentas_con_saldo(conn):

    consulta = """
        SELECT
            c.id,
            c.nombre,
            c.tipo,
            c.saldo_inicial,
            (
                COALESCE(c.saldo_inicial, 0)
                +
                COALESCE(
                    SUM(
                        CASE
                            WHEN LOWER(t.tipo) = 'ingreso'
                                THEN t.monto
                            WHEN LOWER(t.tipo) = 'egreso'
                                THEN -t.monto
                            ELSE 0
                        END
                    ), 0
                )
            ) AS saldo

        FROM cuentas c

        LEFT JOIN transacciones t
            ON c.id = t.cuenta_id

        GROUP BY
            c.id,
            c.nombre,
            c.tipo,
            c.saldo_inicial

        ORDER BY c.nombre
    """

    return pd.read_sql_query(consulta, conn)
