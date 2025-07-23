import re

def clean_vendor_name(raw_memo: str) -> str:
    # Remove long numbers, emails, order numbers, misc codes
    raw = re.sub(r'\d{4,}', '', raw_memo)
    raw = re.sub(r'(?i)(paypal|apple\.com|aplpay|venmo|corelife|tst\*|drake\'s|levelup\*|squareup\.com)', '', raw)
    raw = re.sub(r'[^a-zA-Z\s&]', '', raw)
    raw = re.sub(r'\s+', ' ', raw)
    return raw.strip().title()
