import io
import pdfplumber
import re

SOURCE_REGEX = re.compile(r'Account Ending(?: in)? (\d{4,6})', re.IGNORECASE)
SECTION_HEADERS = ['Payments', 'Credits', 'New Charges', 'Other Fees', 'Interest Charged']

def extract_raw_lines(pdf_bytes):
    raw_data = []
    current_section = None
    current_source = None

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue

            page_lines = []
            lines = text.split('\n')
            for line in lines:
                line = line.strip()

                # Detect source account
                if not current_source:
                    match = SOURCE_REGEX.search(line)
                    if match:
                        current_source = f"American Express {match.group(1)}"

                # Detect section
                if any(header in line for header in SECTION_HEADERS):
                    current_section = next((h for h in SECTION_HEADERS if h in line), current_section)
                    continue

                page_lines.append(line)

            raw_data.append({
                "page": page_num,
                "lines": page_lines,
                "source": current_source or "",
                "section": current_section or ""
            })

    return raw_data
