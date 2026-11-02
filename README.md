# Financial RAG Platform

A Streamlit prototype for exploring financial filings. Upload a PDF to extract filing text, view best-effort KPI signals, find growth and risk statements, and ask questions about the document.

## Features

- Upload a single PDF filing in the dashboard.
- Convert PDFs to Markdown with Docling.
- Detect the company and fiscal year where possible.
- Show revenue, income, balance-sheet, and cash KPI signals when recognized in tables.
- Surface growth and risk statements found in the extracted text.
- Ask filing-grounded questions using OpenAI, or view relevant excerpts without an API key.
- Optional PostgreSQL + pgvector scripts for a separate indexing and extraction workflow.

## Requirements

- Python 3.10 or later
- An OpenAI API key for generated Q&A answers (optional)
- Docker Desktop only if using the optional PostgreSQL + pgvector workflow

## Quick start

From the project directory:

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure the optional OpenAI API key:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set `OPENAI_API_KEY` to your key. Keep real credentials in `.env`; do not put them in `.env.example` or commit them to GitHub. Without a key, the Q&A tab returns relevant filing excerpts instead of generated answers.

4. Start the dashboard:

   ```bash
   streamlit run app.py
   ```

5. Open the local URL printed by Streamlit, usually <http://localhost:8501>, then upload a PDF from the sidebar.

The app processes the uploaded PDF for the current Streamlit session. It does not save upload analysis to PostgreSQL.

## Using the dashboard

1. Upload a financial filing PDF.
2. Review the detected company, filing overview, and KPI values.
3. Use **Growth & risks** to inspect matching statements.
4. Use **Ask about the filing** to ask a question. Generated answers require an OpenAI API key.
5. Use **Extracted text** to check the source text behind the displayed results.

KPI extraction and growth/risk matching are best-effort text processing, not audited financial data or investment advice. Verify values against the filing, including its reporting period, units, and tables.

## Tests

Run the filing-analysis unit tests with Python's standard-library test runner:

```bash
python -m unittest discover -s tests -v
```

The tests cover company and fiscal-year detection, table KPI extraction, negative parenthetical values, growth/risk statement matching, summaries, and both filing-excerpt and mocked OpenAI Q&A paths. They do not require a live API key, PostgreSQL, or Docker.

## Optional PostgreSQL + pgvector workflow

The dashboard upload flow does not require PostgreSQL. The repository also contains scripts for a separate vector-indexing pipeline:

```bash
docker compose up -d
python -m src.db
```

Set the database variables in `.env` if you need non-default credentials. After the database is running and initialized, the other scripts can parse, index, and extract metrics from local Markdown files:

```bash
python -m src.parser
python -m src.embed_and_index
python -m src.extract_kpis
```

The sample indexing workflow uses `data/sample_sec_filing.md`:

```bash
python -m src.sample_workflow
```

The SEC downloader is optional. SEC archive requests may be blocked depending on the network; you can upload a filing PDF directly through the dashboard instead.

## Project layout

```text
.
├── app.py                    # Streamlit PDF upload and analysis dashboard
├── data/
│   └── sample_sec_filing.md  # Small sample for the optional indexing workflow
├── src/
│   ├── config.py             # Environment and database configuration
│   ├── db.py                 # PostgreSQL + pgvector schema setup
│   ├── filing_analysis.py    # Filing text extraction and question answering
│   ├── download_sec_filing.py
│   ├── embed_and_index.py
│   ├── extract_kpis.py
│   ├── parser.py
│   └── sample_workflow.py
├── tests/
│   └── test_filing_analysis.py
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | Enables generated filing Q&A | Unset |
| `DB_HOST` | PostgreSQL host for the optional database workflow | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | PostgreSQL database name | `investor_intel` |
| `DB_USER` | PostgreSQL username | `rag_user` |
| `DB_PASSWORD` | PostgreSQL password | `rag_password` |

## GitHub

Before pushing this project, keep `.env`, the virtual environment, temporary uploads, and local PDF filings out of the repository. The `.gitignore` is configured for these files. Commit `.env.example` with its placeholder values so other developers can create their own local `.env`.

## License

No license has been specified yet. Add a license before allowing others to reuse or distribute this project.
