from fastapi import APIRouter, Depends
from .security import require_auth

router = APIRouter(prefix="/coa", tags=["coa"])

CHART = {
    "Cash": ["1000 - Checking Account","1010 - Savings Account","1020 - Petty Cash"],
    "Accounts Receivable": ["1030 - Accounts Receivable"],
    "Prepaid Expenses": ["1040 - Prepaid Expenses"],
    "Fixed Assets": ["1060 - Fixed Assets","1070 - Accumulated Depreciation"],
    "Other Asset": ["1050 - Inventory"],
    "Accounts Payable": ["2000 - Accounts Payable"],
    "Credit Cards": ["2010 - Credit Card Payables"],
    "Loans": ["2040 - Loan Payable"],
    "Other Liabilities": ["2020 - Payroll Liabilities","2030 - Sales Tax Payable"],
    "Contributions": ["3000 - Contributions"],
    "Draws": ["3010 - Draws"],
    "Retained Earnings": ["3020 - Retained Earnings"],
    "Revenue": ["4000 - Product Sales","4010 - Service Income","4020 - Subscription Revenue","4030 - Consulting Income","4040 - Other Revenue","4090 - Refunds and Discounts"],
    "COGS": ["5000 - Inventory Purchases","5010 - Subcontracted Labor","5020 - Packaging & Shipping Supplies","5030 - Merchant Fees"],
    "Operating Expenses": ["6000 - Salaries and Wages","6010 - Payroll Taxes","6020 - Employee Benefits","6030 - Independent Contractors","6040 - Bonuses & Commissions","6050 - Workers Compensation Insurance","6060 - Recruiting & Hiring"],
    "Facilities & Overhead": ["6100 - Rent or Lease Expense","6110 - Utilities","6120 - Insurance","6130 - Repairs & Maintenance","6140 - Office Supplies","6150 - Telephone & Internet"],
    "Marketing & Sales": ["6200 - Advertising & Promotion","6210 - Social Media & Digital Ads"],
    "Meals & Entertainment": ["6220 - Meals & Entertainment"],
    "Gifts": ["6230 - Client Gifts"],
    "General & Admin": ["6300 - Software Subscriptions","6310 - Bank Fees","6320 - Dues & Licenses","6330 - Postage & Delivery"],
    "Professional Services": ["6400 - Legal Fees","6410 - Accounting & Bookkeeping","6420 - Consulting Fees","6430 - Tax Prep & Advisory"],
    "Travel": ["6500 - Travel - Airfare","6510 - Travel - Lodging","6520 - Travel - Meals","6530 - Travel - Other (Taxis, Parking)"],
    "Taxes": ["8000 - State Income Tax","8010 - Franchise Tax","8020 - Local Business Taxes","8030 - Estimated Tax Payments"],
    "Uncategorized": ["7090 - Uncategorized Expense"],
}

def _clean_contra(label: str) -> str:
    if not label:
        return ""
    t = str(label)
    i = t.find("(")
    while i != -1:
        j = t.find(")", i + 1)
        if j == -1:
            break
        inner = t[i + 1 : j]
        if "contra" in inner.lower():
            left = t[:i].rstrip()
            right = t[j + 1 :].lstrip()
            if left.endswith("-"):
                left = left[:-1].rstrip()
            t = (left + " " + right).strip()
            i = t.find("(")
            continue
        i = t.find("(", j + 1)
    dash = t.find(" - ")
    if dash != -1:
        right = t[dash + 3 :].lower()
        if "contra" in right:
            t = t[:dash].rstrip()
    while "  " in t:
        t = t.replace("  ", " ")
    return t.strip()

@router.get("/grouped")
def grouped(_: dict = Depends(require_auth)):
    out = []
    for label, options in CHART.items():
        cleaned = [_clean_contra(x) for x in options]
        out.append([label, cleaned])
    return {"groups": out}
