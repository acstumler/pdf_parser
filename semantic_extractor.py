import re

def extract_semantic_blocks(text_lines):
    semantic_blocks = []
    current_block = []
    skip_page = False

    for line in text_lines:
        # Detect and skip interest summary / non-transaction pages
        lowered_line = line.lower()
        if "interest charged" in lowered_line or "interest charge calculation" in lowered_line or "trailing interest" in lowered_line:
            skip_page = True
        if skip_page:
            continue

        # Clean up line
        clean_line = line.strip()

        # Detect a new block start with a valid transaction date
        if re.match(r'\d{2}/\d{2}/\d{2,4}', clean_line):
            if current_block:
                semantic_blocks.append(current_block)
                current_block = []
            current_block.append(clean_line)
        elif current_block:
            current_block.append(clean_line)

    # Catch any trailing block
    if current_block:
        semantic_blocks.append(current_block)

    return semantic_blocks
