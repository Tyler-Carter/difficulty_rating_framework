from pathlib import Path
import pdfplumber


# ---------------------------------------------------------------------------
# Wrap `pdfplumber` extraction as a callable function.
# It replaces module-level execution in `extract_pdf.py`
# ---------------------------------------------------------------------------
def extract_pdf(pdf_path: str | Path, output_path: str | Path) -> tuple[int, str]:
    """
    Extract raw text from a PDF and write it to `output_path` with PAGE markers.

    Returns:
          (page_candidate, output_path_str) on success.
    """
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    with pdfplumber.open(pdf_path) as pdf:
        lines: list[str] = []
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines.append(f"=== PAGE {i} ===\n{text}")
        full_text = "\n\n".join(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_text, encoding="utf-8")
    return len(pdf.pages), str(output_path)
