import hashlib
import re
import tempfile
from pathlib import Path

import streamlit as st
from docling.document_converter import DocumentConverter
from openai import OpenAI

from src.config import OPENAI_API_KEY
from src.filing_analysis import (
    answer_question,
    build_summary,
    extract_growth_drivers,
    extract_metrics,
    extract_risk_factors,
    infer_company_name,
)

st.set_page_config(layout="wide", page_title="AI Investor Intelligence")
st.title("AI Investor Intelligence Dashboard")


def create_openai_client():
    if not OPENAI_API_KEY:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)


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
    if st.session_state.get("processed_pdf_id") != upload_id:
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
                st.write(
                    answer_question(
                        question.strip(),
                        markdown_text,
                        client=create_openai_client(),
                    )
                )
        if not OPENAI_API_KEY:
            st.caption(
                "Without an API key, the app returns relevant excerpts rather than "
                "generating a synthesized answer."
            )

    with source_tab:
        st.text_area("Parsed filing text", markdown_text, height=500)
else:
    st.info(
        "Upload a PDF filing to begin. The dashboard will parse the text, extract KPI "
        "signals, and answer filing-specific questions."
    )
    st.markdown("""
    Suggested demo input:
    - Tesla annual report / 10-K PDF
    - Apple or Microsoft annual report
    - Any investor filing in PDF format
    """)
