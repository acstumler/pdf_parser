import io
import pdfplumber
import re

# Detect section headers like "Payments", "New Charges", etc.
SECTION_HEADERS = ['Payments', 'Credits', 'New Charges', 'Other Fees', 'Interest Charged']
SOURCE_REGEX = re.compile(r'Account Ending(?:\s+in)?\s+(\d{4,6})', re.IGNORECASE)

def extract_pdf_lines(pdf_bytes):
    pages_data = []
    current_source = None
    current_section = None

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_data = {
                "page": page_num,
                "lines": [],
                "source": current_source,
                "section": None
            }

            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for line in lines:
                stripped = line.strip()

                # Try to capture account source (e.g. "Account Ending in 61005")
                if not current_source:
                    match = SOURCE_REGEX.search(stripped)
                    if match:
                        current_source = f"American Express {match.group(1)}"
                        page_data["source"] = current_source

                # Update section header if found
                if any(h in stripped for h in SECTION_HEADERS):
                    current_section = next((h for h in SECTION_HEADERS if h in stripped), current_section)

                # Add line to page output
                page_data["lines"].append(stripped)

            page_data["section"] = current_section
            pages_data.append(page_data)

    return pages_data
