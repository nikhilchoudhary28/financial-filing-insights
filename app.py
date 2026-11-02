import re
import tempfile
import hashlib
from pathlib import Path

import streamlit as st
from docling.document_converter import DocumentConverter
from openai import OpenAI

from src.config import OPENAI_API_KEY

st.set_page_config(layout="wide", page_title="AI Investor Intelligence")
st.title("AI Investor Intelligence Dashboard")


def infer_company_name(markdown_text: str, fallback: str = "Uploaded Company") -> str:
    patterns = [
        r"(?m)^##?\s*([A-Z][A-Z0-9 &.,'-]{2,80}(?:CORPORATION|INC\.?|COMPANY|LLC|LTD\.?))\s*$",
        r"([A-Z][A-Za-z0-9&.\- ]{3,60}?(?:Inc\.|Corporation|Company|LLC|Ltd\.))",
        r"([A-Z][A-Za-z0-9&.\- ]{3,60}?(?:, Inc\.|, Corp\.|, Company))",
    ]
    for pattern in patterns:
        match = re.search(pattern, markdown_text)
        if match:
            return match.group(1).strip()
    return fallback


def extract_sections(markdown_text: str):
    matches = list(re.finditer(r"(?m)^#{1,6}\s+(.+)$", markdown_text))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        title = match.group(1).strip()
        content = markdown_text[match.end():end].strip()
        if content:
            sections.append((title, content))
    if not sections and markdown_text.strip():
        sections.append(("Filing", markdown_text.strip()))
    return sections


def extract_metric_value(markdown_text: str, labels: tuple[str, ...]):
    number_pattern = re.compile(r"\(?\s*-?\$?\s*\d[\d,]*(?:\.\d+)?\s*\)?")
    for line in markdown_text.splitlines():
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        row_label = re.sub(r"\s+", " ", cells[0]).strip("* ").lower()
        if row_label not in labels:
            continue
        for cell in cells[1:]:
            number = number_pattern.search(cell)
            if not number:
                continue
            raw_value = number.group(0).replace("$", "").replace(",", "").strip()
            is_parenthetical = raw_value.startswith("(") and raw_value.endswith(")")
            raw_value = raw_value.strip("()").strip()
            try:
                value = float(raw_value)
            except ValueError:
                continue
            return -value if is_parenthetical else value

    for line in markdown_text.splitlines():
        normalized_line = line.strip().lower()
        for label in labels:
            match = re.match(rf"{re.escape(label)}\b", normalized_line)
            if not match:
                continue
            number = number_pattern.search(line, match.end())
            if not number:
                continue
            raw_value = number.group(0).replace("$", "").replace(",", "").strip()
            is_parenthetical = raw_value.startswith("(") and raw_value.endswith(")")
            raw_value = raw_value.strip("()").strip()
            try:
                value = float(raw_value)
            except ValueError:
                continue
            return -value if is_parenthetical else value
    return None


def extract_metrics(markdown_text: str):
    text = markdown_text.replace("\r", "")
    year_match = re.search(
        r"(?:Fiscal Year Ended|Year Ended)[^\n]{0,80}\b(20\d{2})\b",
        text,
        flags=re.I,
    )
    return {
        "company_name": infer_company_name(text),
        "fiscal_year": int(year_match.group(1)) if year_match else None,
        "total_revenue": extract_metric_value(text, ("total revenue", "revenue")),
        "net_income": extract_metric_value(text, ("net income", "net earnings")),
        "operating_income": extract_metric_value(text, ("operating income",)),
        "total_assets": extract_metric_value(text, ("total assets",)),
        "total_liabilities": extract_metric_value(text, ("total liabilities",)),
        "cash_and_equivalents": extract_metric_value(
            text, ("cash and cash equivalents", "cash, cash equivalents")
        ),
    }


def matching_sentences(markdown_text: str, terms: tuple[str, ...], limit: int = 5):
    sentences = re.split(r"(?<=[.!?])\s+|\n+", markdown_text)
    findings = []
    seen = set()
    for sentence in sentences:
        clean_sentence = re.sub(r"\s+", " ", sentence).strip(" |-")
        if len(clean_sentence) < 40:
            continue
        if any(term in clean_sentence.lower() for term in terms):
            normalized = clean_sentence.lower()
            if normalized not in seen:
                findings.append(clean_sentence)
                seen.add(normalized)
        if len(findings) >= limit:
            break
    return findings


def extract_growth_drivers(markdown_text: str):
    return matching_sentences(
        markdown_text,
        (
            "demand",
            "growth",
            "efficiency",
            "cloud",
            "artificial intelligence",
            "productivity",
            "innovation",
            "subscription",
            "sales increased",
        ),
    )


def extract_risk_factors(markdown_text: str):
    return matching_sentences(
        markdown_text,
        (
            "risk",
            "competition",
            "supply chain",
            "pricing pressure",
            "regulation",
            "foreign currency",
            "cybersecurity",
            "privacy",
            "geopolitical",
            "uncertainty",
            "litigation",
        ),
    )


def build_summary(markdown_text: str, company_name: str):
    sections = extract_sections(markdown_text)
    preferred_terms = ("business", "management", "operations", "results", "liquidity")
    selected = [
        re.sub(r"\s+", " ", content).strip()[:400]
        for title, content in sections
        if len(content) > 80
        and any(term in title.lower() for term in preferred_terms)
    ][:3]
    return (
        f"{company_name} filing overview: " + " ".join(selected)
        if selected
        else "Financial filing processed successfully."
    )


def build_investor_insights(markdown_text: str):
    drivers = extract_growth_drivers(markdown_text)
    risks = extract_risk_factors(markdown_text)
    lines = [
        "Growth drivers found in filing:",
        *[f"- {item}" for item in drivers or ["No matching statements found."]],
        "",
        "Risk statements found in filing:",
        *[f"- {item}" for item in risks or ["No matching statements found."]],
    ]
    return "\n".join(lines)


def create_openai_client():
    if not OPENAI_API_KEY:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)


def answer_question(question: str, markdown_text: str):
    sections = extract_sections(markdown_text)
    if not sections:
        return "No filing content was extracted from the uploaded file."

    question_terms = [term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", question)]
    ranked = []
    for title, content in sections:
        chunk = f"Section: {title}\n{content}"
        lower_chunk = chunk.lower()
        score = sum(lower_chunk.count(term) for term in question_terms) if question_terms else 1
        ranked.append((score, title, content))
    ranked.sort(key=lambda result: result[0], reverse=True)
    best_chunks = [
        f"Section: {title}\n{content}" for _, title, content in ranked[:3]
    ]
    context = "\n---\n".join(best_chunks)

    client = create_openai_client()
    if client is not None:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Answer using only the uploaded filing text. Cite relevant numbers when available.",
                },
                {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"},
            ],
        )
        return response.choices[0].message.content

    excerpts = []
    for chunk in best_chunks:
        excerpt = re.sub(r"\s+", " ", chunk).strip()
        if excerpt:
            excerpts.append(excerpt[:900])
    return (
        "No OpenAI API key is configured, so here are the most relevant filing excerpts:\n\n"
        + "\n\n---\n\n".join(excerpts)
    )


def convert_pdf_to_markdown(file_bytes: bytes):
    temp_path = None
    converter = DocumentConverter()
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
            pdf_file.write(file_bytes)
            temp_path = Path(pdf_file.name)
        result = converter.convert(str(temp_path))
        return result.document.export_to_markdown()
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


st.sidebar.title("Controls")
uploaded_file = st.sidebar.file_uploader("Upload SEC filing (PDF)", type=["pdf"])
company_name_input = st.sidebar.text_input("Company name (optional)", value="")

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    if not file_bytes.startswith(b"%PDF"):
        st.error("The uploaded file does not appear to be a valid PDF.")
        st.stop()
    upload_id = hashlib.sha256(file_bytes).hexdigest()
    if (
        st.session_state.get("processed_pdf_id") != upload_id
    ):
        with st.spinner("Parsing the filing and extracting signals..."):
            markdown_text = convert_pdf_to_markdown(file_bytes)
        if not markdown_text.strip():
            st.error("No text could be extracted from this PDF.")
            st.stop()
        detected_company = infer_company_name(
            markdown_text, uploaded_file.name.rsplit(".", 1)[0]
        )
        final_company = company_name_input.strip() or detected_company
        st.session_state["processed_pdf_id"] = upload_id
        st.session_state["markdown_text"] = markdown_text
        st.session_state["company_name"] = final_company
        st.session_state["metrics"] = extract_metrics(markdown_text)

    markdown_text = st.session_state["markdown_text"]
    detected_company = st.session_state["company_name"]
    final_company = company_name_input.strip() or detected_company
    metrics = st.session_state["metrics"]
    metrics["company_name"] = final_company

    st.subheader(f"Filing overview: {final_company}")
    st.caption(f"Source file: {uploaded_file.name}")
    st.write(build_summary(markdown_text, final_company))

    st.subheader("Financial KPIs")
    st.caption(
        "Values are taken from the first matching table row where available. "
        "Verify them against the statement units and source text before relying on them."
    )
    unit_match = re.search(
        r"\(\s*in\s+(thousands|millions|billions)\b", markdown_text, flags=re.I
    )
    if unit_match:
        st.caption(f"Reported statement units: {unit_match.group(1).lower()}")
    metric_fields = [
        ("Revenue", "total_revenue"),
        ("Net income", "net_income"),
        ("Operating income", "operating_income"),
        ("Total assets", "total_assets"),
        ("Total liabilities", "total_liabilities"),
        ("Cash & equivalents", "cash_and_equivalents"),
    ]
    metric_cols = st.columns(len(metric_fields))
    for col, (label, key) in zip(metric_cols, metric_fields):
        value = metrics.get(key)
        col.metric(label, f"{value:,.2f}" if value is not None else "Not found")
    if metrics.get("fiscal_year"):
        st.caption(f"Detected fiscal year: {metrics['fiscal_year']}")

    insights_tab, qa_tab, source_tab = st.tabs(
        ["Growth & risks", "Ask about the filing", "Extracted text"]
    )

    with insights_tab:
        growth_col, risk_col = st.columns(2)
        with growth_col:
            st.markdown("#### Growth drivers found in filing")
            drivers = extract_growth_drivers(markdown_text)
            if not drivers:
                st.info("No matching growth statements were found in the extracted text.")
            for driver in drivers:
                st.markdown(f"- {driver}")
        with risk_col:
            st.markdown("#### Risks found in filing")
            risks = extract_risk_factors(markdown_text)
            if not risks:
                st.info("No matching risk statements were found in the extracted text.")
            for risk in risks:
                st.markdown(f"- {risk}")
        if not OPENAI_API_KEY:
            st.info(
                "These are keyword-based indicators, not an AI-generated financial "
                "recommendation. Add an OpenAI API key for filing-grounded answers."
            )

    with qa_tab:
        question = st.text_input(
            "Ask a question about this filing:",
            value="What were the main growth drivers and risks?",
        )
        if st.button("Get answer", type="primary") and question.strip():
            with st.spinner("Reviewing relevant filing sections..."):
                st.write(answer_question(question.strip(), markdown_text))
        if not OPENAI_API_KEY:
            st.caption(
                "Without an API key, the app returns relevant excerpts rather than "
                "generating a synthesized answer."
            )

    with source_tab:
        st.text_area("Parsed filing text", markdown_text, height=500)
else:
    st.info("Upload a PDF filing to begin. The dashboard will parse the text, extract KPI signals, and answer filing-specific questions.")
    st.markdown("""
    Suggested demo input:
    - Tesla annual report / 10-K PDF
    - Apple or Microsoft annual report
    - Any investor filing in PDF format
    """)
