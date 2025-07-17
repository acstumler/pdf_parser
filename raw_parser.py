import pdfplumber
from collections import defaultdict
import os

def extract_raw_lines(pdf_file_path):
    if not os.path.exists(pdf_file_path):
        raise FileNotFoundError(f"File not found: {pdf_file_path}")

    parsed_pages = []

    with pdfplumber.open(pdf_file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance=2, y_tolerance=1)

            # Group words into visual lines using the Y position
            lines_by_top = defaultdict(list)
            for word in words:
                top_key = round(word['top'])  # bucket by vertical position
                lines_by_top[top_key].append(word)

            lines = []
            for top_y, word_list in sorted(lines_by_top.items()):
                sorted_words = sorted(word_list, key=lambda w: w['x0'])
                line_text = " ".join(w['text'] for w in sorted_words)

                # Optionally get the leftmost and rightmost words
                x0 = min(w['x0'] for w in sorted_words)
                x1 = max(w['x1'] for w in sorted_words)

                lines.append({
                    "text": line_text,
                    "x0": x0,
                    "x1": x1,
                    "top": top_y,
                    "page": page_num,
                    "source": os.path.basename(pdf_file_path),
                    "section": "",  # Can later be inferred by heading detection
                })

            parsed_pages.append({
                "page_number": page_num,
                "lines": lines,
                "source": os.path.basename(pdf_file_path),
                "section": ""
            })

    return parsed_pages
