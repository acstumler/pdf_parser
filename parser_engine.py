import io
import re
from typing import List, Dict, Any
import pdfplumber
from clean_vendor_name import clean_vendor_name

DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
MONEY_RE = re.compile(r"[-]?\$?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})\b")
AMOUNT_ONLY_RE = re.compile(r"[-]?\d+(?:\.\d{2})")

def _parse_amount(tok: str) -> float:
    s = tok.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except:
        m = AMOUNT_ONLY_RE.search(tok)
        if not m:
            return 0.0
        try:
            return float(m.group(0))
        except:
            return 0.0

def detect_and_parse(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Universal, structure-first line scraper:
    - Scans each page's text lines.
    - Captures lines containing a date and an amount token.
    - Builds transactions with cleaned memo.
    """
    results: List[Dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            for ln in lines:
                dmatch = DATE_RE.search(ln)
                if not dmatch:
                    continue
                moneys = MONEY_RE.findall(ln)
                if not moneys:
                    continue
                amount = _parse_amount(moneys[-1])
                memo_raw = ln
                memo_clean = clean_vendor_name(memo_raw)
                mm, dd, yy = dmatch.groups()
                if len(yy) == 2:
                    yy = "20" + yy
                date = f"{mm.zfill(2)}/{dd.zfill(2)}/{yy}"
                results.append(
                    {
                        "date": date,
                        "memo_raw": memo_raw,
                        "memo_clean": memo_clean,
                        "amount": amount,
                    }
                )
    return results
