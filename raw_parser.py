import re

def extract_transaction_blocks(text):
    lines = text.splitlines()
    blocks = []
    block = []
    for line in lines:
        if re.search(r"\d{2}/\d{2}/\d{2,4}", line):
            if block:
                blocks.append("\n".join(block))
                block = []
        block.append(line)
    if block:
        blocks.append("\n".join(block))
    return blocks

def clean_block(block):
    return re.sub(r"\s+", " ", block).strip()

def extract_visual_rows_v2(pdf_text):
    blocks = extract_transaction_blocks(pdf_text)
    return [clean_block(b) for b in blocks]
