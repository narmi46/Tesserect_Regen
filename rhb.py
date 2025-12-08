import re
from datetime import datetime

# ============================================================
#                   REGEX PATTERNS
# ============================================================

# New RHB Reflex Format (2025)
PATTERN_RHB_NEW = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"         # date
    r"(\d{3})\s+"                     # branch code
    r"(.+?)\s+"                       # description
    r"([0-9,]+\.\d{2}|-)\s+"          # debit
    r"([0-9,]+\.\d{2}|-)\s+"          # credit
    r"([0-9,]+\.\d{2})([+-])"         # balance + trailing +/- sign
)

# Old RHB Format (pre-2025)
PATTERN_RHB_OLD = re.compile(
    r"(\d{2}\s+\w{3})\s+"             # date like '07 Mar'
    r"(.+?)\s+"                       # description
    r"(\d{6,12})\s+"                  # cheque / serial no
    r"([0-9,]+\.\d{2})\s+"            # amount
    r"(-?[0-9,]+\.\d{2})"             # balance (may start with '-')
)

# Map month short name → number
MONTH_MAP = {
    "Jan": "01","Feb": "02","Mar": "03","Apr": "04","May": "05","Jun": "06",
    "Jul": "07","Aug": "08","Sep": "09","Oct": "10","Nov": "11","Dec": "12"
}

# ============================================================
#                   HELPER FUNCTIONS
# ============================================================

def convert_old_date(raw_date, year):
    """Convert '07 Mar' → '2024-03-07'"""
    d, mon = raw_date.split()
    return f"{year}-{MONTH_MAP[mon]}-{d}"


def parse_amount(val):
    """Convert amount or '-' into float"""
    if val == "-" or val is None:
        return 0.00
    return float(val.replace(",", ""))


# ============================================================
#                   PARSER: NEW FORMAT
# ============================================================

def parse_rhb_new(line, page):
    m = PATTERN_RHB_NEW.search(line)
    if not m:
        return None

    date_raw, branch, desc, debit_raw, credit_raw, bal_raw, sign = m.groups()

    # Balance sign handling
    balance = parse_amount(bal_raw)
    if sign == "-":
        balance = -balance

    return {
        "date": date_raw,
        "description": desc.strip(),
        "debit": parse_amount(debit_raw),
        "credit": parse_amount(credit_raw),
        "balance": balance,
        "page": page,
        "format": "NEW"
    }


# ============================================================
#                   PARSER: OLD FORMAT
# ============================================================

def parse_rhb_old(line, page, year):
    m = PATTERN_RHB_OLD.search(line)
    if not m:
        return None

    date_raw, desc, cheque, amount_raw, bal_raw = m.groups()
    full_date = convert_old_date(date_raw, year)

    amount = parse_amount(amount_raw)
    balance = parse_amount(bal_raw)

    # Determine debit or credit (approximation)
    debit = 0.00
    credit = 0.00

    # Clue-based classification
    if any(x in desc.upper() for x in ["DEPOSIT", "QR", "TRANSFER", "CR", "P2P"]):
        credit = amount
    else:
        debit = amount

    desc_full = f"{desc.strip()} ({cheque})"

    return {
        "date": full_date,
        "description": desc_full,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page,
        "format": "OLD"
    }


# ============================================================
#                   AUTO-DETECT PARSER
# ============================================================

def parse_rhb_any(line, page, year=None):
    """Try new Reflex format first, then fall back to old format."""
    tx = parse_rhb_new(line, page)
    if tx:
        return tx

    if year:
        tx_old = parse_rhb_old(line, page, year)
        if tx_old:
            return tx_old

    return None


# ============================================================
#                   DOCUMENT PARSER
# ============================================================

def parse_rhb_document(text, year=None):
    """
    Parse entire PDF text.
    - text: extracted text from PDF (string)
    - year: required for old format (e.g. 2024)
    """
    results = []
    page = 1

    for raw_line in text.splitlines():
        line = raw_line.strip()

        # Detect page number (fallback)
        if "Page" in line and "/" in line:
            try:
                page = int(line.split()[1].split("/")[0])
            except:
                pass

        tx = parse_rhb_any(line, page, year)
        if tx:
            results.append(tx)

    return results


# ============================================================
#                   EXAMPLE USAGE
# ============================================================

if __name__ == "__main__":

    # EXAMPLE: parse new Reflex format
    # pdf_text = extract_text("02. FEB 2025-RHB.pdf")
    # data = parse_rhb_document(pdf_text)
    # print(data)

    # EXAMPLE: parse old format (must supply year)
    # pdf_text = extract_text("3 March 2024 Statement.pdf")
    # data = parse_rhb_document(pdf_text, year=2024)
    # print(data)

    print("RHB parser ready. You can call parse_rhb_document(text).")
