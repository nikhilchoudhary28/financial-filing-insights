import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FIXING_HEADER = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Referer": "https://www.sec.gov/",
    "Accept-Language": "en-US,en;q=0.9",
}

TESLA_CIK = "0001318605"
SEC_SUBMISSIONS_URL = f"https://data.sec.gov/submissions/CIK{TESLA_CIK}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


def get_latest_10k_metadata():
    response = requests.get(SEC_SUBMISSIONS_URL, headers=FIXING_HEADER, timeout=30)
    response.raise_for_status()
    payload = response.json()

    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])

    for idx, form in enumerate(forms):
        if form == "10-K":
            return {
                "accession_number": accession_numbers[idx],
                "primary_document": primary_documents[idx],
                "filing_date": filing_dates[idx],
            }

    raise ValueError("No 10-K filing metadata found for Tesla.")


def download_tesla_10k(output_dir: str = "data") -> Path | None:
    metadata = get_latest_10k_metadata()
    accession_num = metadata["accession_number"].replace("-", "")
    cik_int = int(TESLA_CIK.replace("000", ""))
    filing_url = (
        f"{SEC_ARCHIVES_BASE}/{cik_int}/{metadata['accession_number']}/{metadata['primary_document']}"
    )

    output_path = Path(output_dir) / "Tesla_10K.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(filing_url, headers=FIXING_HEADER, timeout=60)
        response.raise_for_status()
    except requests.HTTPError:
        print(
            "SEC blocked the direct filing download from this environment with HTTP 403. "
            "The metadata URL still works, but the archive download is denied here. "
            f"Expected URL: {filing_url}"
        )
        return None

    output_path.write_bytes(response.content)
    return output_path


def html_to_markdown(html_path: Path) -> Path:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n\s+\n", "\n\n", text)

    markdown_path = html_path.with_suffix(".md")
    markdown_path.write_text(text.strip() + "\n", encoding="utf-8")
    return markdown_path


def main():
    html_path = download_tesla_10k()
    if html_path is None:
        print("No filing downloaded because SEC direct archive requests were blocked by 403 in this environment.")
        return

    markdown_path = html_to_markdown(html_path)
    print(f"Downloaded Tesla 10-K filing to: {html_path}")
    print(f"Converted markdown preview to: {markdown_path}")


if __name__ == "__main__":
    main()
