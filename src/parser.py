from pathlib import Path

from docling.document_converter import DocumentConverter


def convert_pdf_to_markdown(pdf_path: str) -> str:
    """Convert a PDF filing into Markdown while preserving tables."""
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    return result.document.export_to_markdown()


if __name__ == "__main__":
    sample_pdf = Path("data/Tesla_2024_10K.pdf")
    if sample_pdf.exists():
        markdown_text = convert_pdf_to_markdown(str(sample_pdf))
        output_file = Path("data/Tesla_2024.md")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(markdown_text, encoding="utf-8")
        print("PDF successfully parsed into Markdown.")
    else:
        print(f"Sample PDF not found: {sample_pdf}")
