"""Cache OCR of the downloaded primary catalogue for research discovery only.

OCR is not an accepted transcription. Inspect original rendered pages before
entering any coordinate or identity into the published evidence register.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import fitz

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "V49_sources_20261013" / "TT25_2015_PhuYen_geographic_names.pdf"
CACHE = SOURCE.parent / "TT25_review"


def ocr_page(page_index):
    CACHE.mkdir(exist_ok=True)
    stem = CACHE / f"page_{page_index + 1:03d}"
    target = stem.with_suffix(".txt")
    if not target.exists():
        with fitz.open(SOURCE) as doc:
            doc[page_index].get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False).save(stem.with_suffix(".png"))
        env = os.environ.copy()
        env["OMP_THREAD_LIMIT"] = "1"
        subprocess.run([r"C:\Program Files\Tesseract-OCR\tesseract.exe", str(stem.with_suffix(".png")),
                        str(stem), "-l", "vie+eng", "--psm", "6"], check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    text = target.read_text(encoding="utf-8")
    terms = ("thủy văn", "thuỷ văn", "ngân sơn", "hóc răm", "phú xuân", "đồng tròn", "trạm")
    hits = [line for line in text.splitlines() if any(term in line.casefold() for term in terms)]
    return page_index + 1, hits


if __name__ == "__main__":
    with fitz.open(SOURCE) as doc:
        page_count = len(doc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for page, hits in pool.map(ocr_page, range(page_count)):
            if hits:
                print(f"PDF page {page}: " + " | ".join(hits), flush=True)
    print("OCR discovery complete; all numerical transcriptions still require original-page verification", flush=True)
