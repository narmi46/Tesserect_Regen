import regex as re

# ============================================================
# UNIVERSAL CLEANER FOR MAYBANK TEXT
# ============================================================

def clean_maybank_line(line: str) -> str:
    if not line:
        return ""

    # Remove invisible unicode junk
    line = line.replace("\u200b", "")   # zero-width space
    line = line.replace("\u200e", "")   # LTR mark
    line = line.replace("\u200f", "")   # RTL mark
    line = line.replace("\ufeff", "")   # BOM
    line = line.replace("\xa0", " ")    # non-breaking space

    # Collapse multiple spaces
    line = re.sub(r"\s+", " ", line)

    # Trim
    return line.strip()


# ============================================================
# MAYBANK MTASB PATTERN (NO YEAR FORMAT)
# ============================================================

PATTERN_MAYBANK_MTASB = re.compile(
    r"(\d{2}/\d{2})\s+"                 # Date: 01/08
    r"(.+?)\s+"                         # Description
    r"([0-9,]+\.\d{2})\s*([+-])\s*"     # Amount + Sign (tolerant spacing)
    r"([0-9,]+\.\d{2})"                 # Balance
)

def parse_line_maybank_mtasb(line, page_num, default_year="2024"):
    m = PATTERN_MAYBANK_MTASB.search(line)
    if not m:
        return None

    date_raw, desc, amount_raw, sign, balance_raw = m.groups()
    day, month = date_raw.split("/")
    year = default_year

    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    credit = amount if sign == "+" else 0.0
    debit  = amount if sign == "-" else 0.0

    full_date = f"{day}/{month}/{year}"

    return {
        "date": full_date,
        "description": desc.strip(),
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


# ============================================================
# MAYBANK MBB PATTERN (FULL DATE FORMAT)
# ============================================================

PATTERN_MAYBANK_MBB = re.compile(
    r"(\d{2})\s+([A-Za-z]{3})\s+(\d{4})\s+"
    r"(.+?)\s+"
    r"([0-9,]+\.\d{2})\s*([+-])\s*"
    r"([0-9,]+\.\d{2})"
)

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

def parse_line_maybank_mbb(line, page_num):
    m = PATTERN_MAYBANK_MBB.search(line)
    if not m:
        return None

    day, mon_abbr, year, desc, amount_raw, sign, balance_raw = m.groups()
    month = MONTH_MAP.get(mon_abbr.title(), "01")

    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    credit = amount if sign == "+" else 0.0
    debit  = amount if sign == "-" else 0.0

    full_date = f"{day}/{month}/{year}"

    return {
        "date": full_date,
        "description": desc.strip(),
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


# ============================================================
# ADVANCED LINE RECONSTRUCTOR
# Fixes broken DUITNOW / long descriptions
# ============================================================

def reconstruct_broken_lines(lines):
    rebuilt = []
    buffer_line = ""

    for line in lines:
        line = clean_maybank_line(line)

        if not line:
            continue

        # If line begins with date, flush buffer
        if re.match(r"^\d{2}/\d{2}", line):
            if buffer_line:
                rebuilt.append(buffer_line)
                buffer_line = ""
            buffer_line = line
        else:
            # Continuation of previous description
            buffer_line += " " + line

    if buffer_line:
        rebuilt.append(buffer_line)

    return rebuilt


# ============================================================
# MAIN PARSER ENTRY POINT
# ============================================================

def parse_transactions_maybank(text, page_num, default_year="2024"):

    raw_lines = text.splitlines()
    cleaned_lines = [clean_maybank_line(l) for l in raw_lines]

    # Reconstruct broken lines
    lines = reconstruct_broken_lines(cleaned_lines)

    tx_list = []

    for line in lines:

        # Try MTASB format
        tx = parse_line_maybank_mtasb(line, page_num, default_year)
        if tx:
            tx_list.append(tx)
            continue

        # Try MBB format
        tx = parse_line_maybank_mbb(line, page_num)
        if tx:
            tx_list.append(tx)
            continue

    return tx_list
