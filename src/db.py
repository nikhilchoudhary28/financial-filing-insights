import psycopg2

from src.config import DB_URL


def get_connection():
    return psycopg2.connect(DB_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_metrics (
                id SERIAL PRIMARY KEY,
                company_name VARCHAR(100) NOT NULL,
                fiscal_year INT NOT NULL,
                total_revenue NUMERIC,
                net_income NUMERIC,
                operating_cash_flow NUMERIC,
                total_assets NUMERIC,
                total_liabilities NUMERIC,
                growth_drivers TEXT,
                top_risk_factors TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (company_name, fiscal_year)
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS document_embeddings (
                id SERIAL PRIMARY KEY,
                company_name VARCHAR(100) NOT NULL,
                fiscal_year INT NOT NULL,
                page_number INT,
                chunk_content TEXT NOT NULL,
                embedding vector(1536)
            );
            """
        )

        conn.commit()
        print("Database schema and vector extensions initialized.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init_db()
