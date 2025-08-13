from typing import List, Dict, Any, Tuple
import io
import re
from datetime import datetime
import pdfplumber

NUM_TAIL = re.compile(r"\b(\d{4,6})\b")
DATE_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
DATE_MON = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2}),\s*(\d{4})\b", re.I)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12
}

def _extract_header_words(page: pdfplumber.page.Page) -> List[str]:
    try:
        words = page.extract_words() or []
    except:
        return []
    top = page.bbox[1]
    bottom = page.bbox[3]
    left = page.bbox[0]
    right = page.bbox[2]
    band_h = (bottom - top) * 0.18
    header_top = top
    header_bottom = top + band_h
    tokens = []
    for w in words:
        y0 = w.get("top", 0)
        y1 = w.get("bottom", 0)
        if y0 >= header_top and y1 <= header_bottom:
            t = w.get("text", "")
            if t:
                tokens.append(t)
    return tokens

def _extract_header_text(pdf: pdfplumber.PDF) -> str:
    if not pdf.pages:
        return ""
    page = pdf.pages[0]
    tokens = _extract_header_words(page)
    return " ".join(tokens)

def _doc_numeric_frequencies(pdf: pdfplumber.PDF) -> Dict[str, int]:
    freq: Dict[str, int] = {}
    for page in pdf.pages:
        t = page.extract_text() or ""
        for m in NUM_TAIL.finditer(t):
            k = m.group(1)
            freq[k] = freq.get(k, 0) + 1
    return freq

def _extract_header_tails(pdf: pdfplumber.PDF) -> List[str]:
    tails: List[str] = []
    if not pdf.pages:
        return tails
    page = pdf.pages[0]
    tokens = _extract_header_words(page)
    for tok in tokens:
        m = NUM_TAIL.search(tok)
        if m:
            tails.append(m.group(1))
    return tails

def _pick_best_tail(header_tails: List[str], doc_freq: Dict[str, int]) -> str:
    if not header_tails and not doc_freq:
        return ""
    scores: Dict[str, float] = {}
    header_set = set(header_tails)
    candidates = set(doc_freq.keys()) | header_set
    for k in candidates:
        base = float(doc_freq.get(k, 0))
        bonus = 2.5 if k in header_set else 0.0
        scores[k] = base + bonus
    best = max(scores.items(), key=lambda kv: kv[1])[0]
    return best

def _match_coa_label_by_tail(tail: str) -> str:
    if not tail:
        return ""
    try:
        from chart_of_accounts import CHART_OF_ACCOUNTS
    except:
        CHART_OF_ACCOUNTS = []
    candidates = []
    for entry in CHART_OF_ACCOUNTS:
        name = str(entry.get("name", ""))
        group = str(entry.get("group", "")).lower()
        if tail in name:
            priority = 2
            if "liab" in group:
                priority = 0
            elif "asset" in group:
                priority = 1
            candidates.append((priority, name))
    if not candidates:
        return ""
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]

def _detect_source_account(pdf_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            header_tails = _extract_header_tails(pdf)
            freq = _doc_numeric_frequencies(pdf)
            tail = _pick_best_tail(header_tails, freq)
            if not tail:
                return ""
            mapped = _match_coa_label_by_tail(tail)
            if mapped:
                return mapped
            if len(tail) >= 4:
                return f"Account ****{tail[-4:]}"
            return f"Account ****{tail}"
    except:
        return ""

def _parse_date_token(tok: str) -> datetime | None:
    tok = tok.strip()
    m = DATE_NUM.search(tok)
    if m:
        mm, dd, yy = m.groups()
        if len(yy) == 2:
            yy = "20" + yy
        try:
            return datetime(int(yy), int(mm), int(dd))
        except:
            return None
    m2 = DATE_MON.search(tok)
    if m2:
        mon, dd, yyyy = m2.groups()
        try:
            mm = MONTHS[mon.lower()]
            return datetime(int(yyyy), int(mm), int(dd))
        except:
            return None
    return None

def _collect_dates_from_text(text: str) -> List[datetime]:
    dates: List[datetime] = []
    for m in DATE_NUM.finditer(text):
        mm, dd, yy = m.groups()
        if len(yy) == 2:
            yy = "20" + yy
        try:
            dt = datetime(int(yy), int(mm), int(dd))
            dates.append(dt)
        except:
            pass
    for m in DATE_MON.finditer(text):
        mon, dd, yyyy = m.groups()
        try:
            mm = MONTHS[mon.lower()]
            dt = datetime(int(yyyy), int(mm), int(dd))
            dates.append(dt)
        except:
            pass
    return dates

def _detect_statement_period(pdf_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            header_text = _extract_header_text(pdf)
            header_dates = _collect_dates_from_text(header_text)
            if len(header_dates) >= 2:
                start = min(header_dates)
                end = max(header_dates)
                return end.strftime("%m/%d/%Y")
            if len(header_dates) == 1:
                only = header_dates[0]
                return only.strftime("%m/%d/%Y")
            if pdf.pages:
                first_text = pdf.pages[0].extract_text() or ""
                page_dates = _collect_dates_from_text(first_text)
                if len(page_dates) >= 2:
                    start = min(page_dates)
                    end = max(page_dates)
                    return end.strftime("%m/%d/%Y")
                if len(page_dates) == 1:
                    return page_dates[0].strftime("%m/%d/%Y")
    except:
        pass
    return ""

def extract_transactions_from_bytes(pdf_bytes: bytes) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    from parser_engine import detect_and_parse
    txns = detect_and_parse(pdf_bytes)
    source_account = _detect_source_account(pdf_bytes)
    for t in txns:
        t["source_account"] = source_account
    statement_end_date = _detect_statement_period(pdf_bytes)
    meta = {
        "source_account": source_account,
        "statement_end_date": statement_end_date,
    }
    return txns, meta
