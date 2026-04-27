"""
Extract NPC data from Danger Gal Dossier PDF using pdfplumber.
"""
import pdfplumber
import sys
import os

PDF_PATH = r"C:\Users\gtc19\OneDrive\Documents\Table Top Games\Cyberpunk\Books\Danger Gal Dossier (J Gray, James Hutt, Anne Morrison, Chris Spivey etc.).pdf"
OUTPUT_PATH = r"outputs/text_output/pdf_extract.txt"

def extract_pdf():
    print(f"Opening: {PDF_PATH}")
    all_text = []

    with pdfplumber.open(PDF_PATH) as pdf:
        num_pages = len(pdf.pages)
        print(f"Total pages: {num_pages}")

        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                all_text.append(f"\n\n{'='*60}\nPAGE {page_num}\n{'='*60}\n")
                all_text.append(text)
            else:
                all_text.append(f"\n\n{'='*60}\nPAGE {page_num} [no text extracted]\n{'='*60}\n")

            if (i + 1) % 10 == 0:
                print(f"  Processed {i+1}/{num_pages} pages...")

    full_text = "".join(all_text)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_text)

    print(f"\nSaved {len(full_text):,} characters to {OUTPUT_PATH}")
    return num_pages, full_text

if __name__ == "__main__":
    num_pages, full_text = extract_pdf()

    # Print first 10 pages sample
    print("\n" + "="*60)
    print("FIRST 10 PAGES PREVIEW")
    print("="*60)
    # Find page 10 marker and print up to that point
    marker = "PAGE 11"
    idx = full_text.find(f"\nPAGE 11\n")
    if idx == -1:
        idx = full_text.find("PAGE 11")
    preview = full_text[:idx] if idx > 0 else full_text[:8000]
    print(preview[:12000])
