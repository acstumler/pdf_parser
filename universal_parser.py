import os
import tempfile
from fastapi import UploadFile
from pdf_parser.raw_parser import extract_visual_rows_v2
from pdf_parser.utils.clean_vendor_name import clean_vendor_name
from pdf_parser.utils.classifyTransaction import classifyTransaction


def extract_transactions(pdf_path: str, start_date: str = None, end_date: str = None, source: str = "Unknown"):
    return extract_visual_rows_v2(pdf_path, start_date, end_date, source)


async def save_upload_file_tmp(upload_file: UploadFile) -> str:
    try:
        suffix = os.path.splitext(upload_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await upload_file.read())
            return tmp.name
    except Exception as e:
        print("Failed to save upload file:", e)
        raise


async def extract_visual_rows_v2(file: UploadFile, start_date: str = None, end_date: str = None):
    tmp_path = await save_upload_file_tmp(file)
    try:
        raw = extract_transactions(tmp_path, start_date, end_date, source="Unknown")

        transactions = []
        for r in raw:
            date = r.get("date", "")
            memo = r.get("memo", "")
            amount = r.get("amount", "")
            source = r.get("source", "Unknown")

            # Clean and simplify memo
            memo_clean = clean_vendor_name(memo)

            # Parse amount value
            try:
                amount_val = float(amount.replace("(", "-").replace(")", "").replace(",", "").replace("$", ""))
            except:
                amount_val = 0.0

            # Classify account
            classification = classifyTransaction(memo_clean, amount_val).get("classification", "7090 - Uncategorized Expense")

            # Format amount
            formatted_amount = f"(${abs(amount_val):,.2f})" if amount_val < 0 else f"${amount_val:,.2f}"

            transactions.append({
                "date": date,
                "memo": memo_clean,
                "account": classification,
                "source": source,
                "amount": formatted_amount,
            })

        return transactions

    finally:
        os.remove(tmp_path)
