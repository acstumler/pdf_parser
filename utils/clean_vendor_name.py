import re

def clean_vendor_name(memo):
    if not memo or not isinstance(memo, str):
        return ""
    
    # Cut off at first known date or card string
    memo = re.split(r'\d{2}/\d{2}/\d{2,4}|T\s+\d{4}', memo)[0]

    # Remove long digit sequences and common tokens
    memo = re.sub(r'\b\d{6,}\b', '', memo)
    memo = re.sub(r'[^a-zA-Z\s&.-]', '', memo)

    # Normalize spacing and title case
    memo = re.sub(r'\s+', ' ', memo).strip()
    return memo.title()
