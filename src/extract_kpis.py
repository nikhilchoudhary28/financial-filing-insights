import os

import psycopg2
from openai import OpenAI
from pydantic import BaseModel, Field

from src.config import DB_URL

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class FinancialMetrics(BaseModel):
    total_revenue: float = Field(description="Total revenue in millions")
    net_income: float = Field(description="Net income in millions")
    operating_cash_flow: float = Field(description="Operating cash flow in millions")
    total_assets: float = Field(description="Total assets in millions")
    total_liabilities: float = Field(description="Total liabilities in millions")
    growth_drivers: str = Field(description="Concise bullet points of primary growth drivers")
    top_risk_factors: str = Field(description="Concise summary of top risk factors")


def extract_and_store_metrics(company_name: str, fiscal_year: int):
    query = f"Consolidated Statements of Operations Balance Sheet {company_name} {fiscal_year}"
    query_emb = client.embeddings.create(
        input=query,
        model="text-embedding-3-small",
    ).data[0].embedding

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT chunk_content
            FROM document_embeddings
            WHERE company_name = %s AND fiscal_year = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
            """,
            (company_name, fiscal_year, query_emb),
        )
        context = "\n---\n".join(row[0] for row in cur.fetchall())

        completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Extract accurate financial metrics from the provided SEC 10-K sections. Return values in millions.",
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nExtract metrics for {company_name} {fiscal_year}.",
                },
            ],
            response_format=FinancialMetrics,
        )
        result = completion.choices[0].message.parsed

        cur.execute(
            """
            INSERT INTO financial_metrics (
                company_name, fiscal_year, total_revenue, net_income,
                operating_cash_flow, total_assets, total_liabilities,
                growth_drivers, top_risk_factors
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (company_name, fiscal_year) DO UPDATE SET
                total_revenue = EXCLUDED.total_revenue,
                net_income = EXCLUDED.net_income,
                operating_cash_flow = EXCLUDED.operating_cash_flow,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                growth_drivers = EXCLUDED.growth_drivers,
                top_risk_factors = EXCLUDED.top_risk_factors;
            """,
            (
                company_name,
                fiscal_year,
                result.total_revenue,
                result.net_income,
                result.operating_cash_flow,
                result.total_assets,
                result.total_liabilities,
                result.growth_drivers,
                result.top_risk_factors,
            ),
        )
        conn.commit()
        print(f"Metrics saved for {company_name} {fiscal_year}.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    extract_and_store_metrics("Tesla", 2024)
