import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from openai import OpenAI

from src.config import DB_URL

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def index_markdown_document(md_file_path: str, company_name: str, fiscal_year: int):
    md_path = Path(md_file_path)
    content = md_path.read_text(encoding="utf-8")

    headers_to_split = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split)
    header_splits = md_splitter.split_text(content)

    chunk_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    final_docs = chunk_splitter.split_documents(header_splits)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    try:
        for doc in final_docs:
            text = doc.page_content.strip()
            if not text:
                continue

            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-small",
            )
            embedding = response.data[0].embedding

            cur.execute(
                """
                INSERT INTO document_embeddings (company_name, fiscal_year, chunk_content, embedding)
                VALUES (%s, %s, %s, %s)
                """,
                (company_name, fiscal_year, text, embedding),
            )

        conn.commit()
        print(f"Stored {len(final_docs)} chunks for {company_name} ({fiscal_year}).")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    md_file = Path("data/Tesla_2024.md")
    if md_file.exists():
        index_markdown_document(str(md_file), "Tesla", 2024)
    else:
        print(f"Markdown file not found: {md_file}")
