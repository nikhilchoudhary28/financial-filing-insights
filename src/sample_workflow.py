from pathlib import Path

from src.db import init_db
from src.embed_and_index import index_markdown_document


def ensure_sample_markdown() -> Path:
    sample_path = Path("data/sample_sec_filing.md")
    if not sample_path.exists():
        raise FileNotFoundError(f"Sample markdown file missing: {sample_path}")
    return sample_path


def run_sample_workflow(company_name: str = "Tesla", fiscal_year: int = 2024):
    sample_path = ensure_sample_markdown()
    init_db()
    index_markdown_document(str(sample_path), company_name, fiscal_year)
    print(f"Sample workflow completed for {company_name} ({fiscal_year}).")
    print(f"Sample markdown file: {sample_path}")


if __name__ == "__main__":
    run_sample_workflow()
