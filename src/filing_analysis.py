import re


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


def answer_question(question: str, markdown_text: str, client=None):
    sections = extract_sections(markdown_text)
    if not sections:
        return "No filing content was extracted from the uploaded file."

    question_terms = [
        term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", question)
    ]
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
