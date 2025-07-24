# ...[imports and other functions unchanged]...

def extract_transactions_from_text(text_lines):
    transactions = []
    seen_fingerprints = set()

    end_date = extract_closing_date(text_lines) or datetime.today().date()
    start_date = end_date - timedelta(days=60)
    print(f"[INFO] Enforcing date filter: Start = {start_date}, End = {end_date}")

    source = extract_source_account(text_lines)
    blocks = build_candidate_blocks(text_lines)
    print(f"[INFO] Found {len(blocks)} candidate blocks")

    for block in blocks:
        if len(block) < 2:
            print("[SKIP] Block too short:", block)
            continue

        date_obj = extract_date(block)
        if not date_obj:
            print("[SKIP] Could not parse date:", block[0])
            continue
        if not (start_date <= date_obj <= end_date):
            print(f"[SKIP] Date out of range: {date_obj} not in {start_date}–{end_date}")
            continue

        amount = parse_amount(block)
        if amount is None:
            print("[SKIP] No valid amount found:", block)
            continue

        memo = extract_memo(block)
        if not memo:
            print("[SKIP] No valid memo found:", block)
            continue

        date_str = date_obj.strftime("%m/%d/%Y")

        if "payment" in memo.lower() or "thank you" in memo.lower():
            amount = -abs(amount)

        fingerprint = f"{date_str}|{memo.lower()}|{amount:.2f}|{source}"
        if fingerprint in seen_fingerprints:
            print(f"[SKIPPED] Duplicate fingerprint: {fingerprint}")
            continue
        seen_fingerprints.add(fingerprint)

        transactions.append({
            "date": date_str,
            "memo": clean_vendor_name(memo),
            "account": "7090 - Uncategorized Expense",
            "source": source,
            "amount": amount
        })

    print(f"[INFO] Final parsed transactions: {len(transactions)}")
    return { "transactions": transactions }

# ...[extract_transactions() unchanged]...
