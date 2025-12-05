import regex as re

# ============================================================
# UNIVERSAL RHB STATEMENT PARSER
# Supports:
#   1. Reflex Corporate Format  (Oct 2024)
#   2. Islamic/QARD Current Account (Jan 2025)
#   3. Personal Current Account (Mar 2024)
# ============================================================

# ------------------------------------------------------------
# Regex Patterns
# ------------------------------------------------------------

# 1️⃣ Reflex Corporate (Ftech Travel)
PATTERN_RHB_REFLEX = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"
    r"(\d{3})\s+"
    r"(.+?)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2})([+-])"
)

# 2️⃣ Islamic & Personal Format (same structure)
PATTERN_RHB_ISLAMIC = re.compile(
    r"(\d{2}\s+[A-Za-z]{3})\s+"      # e.g. "06 Jan"
    r"(.+?)\s+"
    r"(\d{1,12}|-)\s+"
    r"([0-9,]+\.\d{2})\s+"           # debit or credit column
    r"([0-9,]+\.\d{2})"              # balance
)

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

# ------------------------------------------------------------
# Parsing Functions
# ------------------------------------------------------------

def parse_reflex(m, page_num):
    date_raw, branch, desc, dr_raw, cr_raw, bal_raw, sign = m.groups()

    d, m_, y = date_raw.split("-")
    full_date = f"{y}-{m_}-{d}"

    debit = float(dr_raw.replace(",", "")) if dr_raw != "-" else 0.0
    credit = float(cr_raw.replace(",", "")) if cr_raw != "-" else 0.0

    balance = float(bal_raw.replace(",", ""))
    if sign == "-":
        balance = -balance

    return {
        "date": full_date,
        "description": f"{branch} {desc.strip()}",
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


def parse_islamic(m, page_num, default_year="2025"):
    date_raw, desc, refnum, amount_raw, balance_raw = m.groups()

    day, mon = date_raw.split()
    mon_num = MONTH_MAP.get(mon, "01")

    full_date = f"{default_year}-{mon_num}-{day}"

    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    # DR/CR AUTODETECT LOGIC  
    # If description contains common debit markers → treat as debit
    desc_lower = desc.lower()

    likely_debit = any(x in desc_lower for x in [
        "trf dr", "transfer dr", "mbk instant trf dr",
        "withdrawal", "atm", "payment", "petty", "labour", "rental"
    ])

    if likely_debit:
        debit = amount
        credit = 0.0
    else:
        # Otherwise assume it is incoming money
        debit = 0.0
        credit = amount

    return {
        "date": full_date,
        "description": desc.strip(),
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


# ------------------------------------------------------------
# Master RHB Parser
# ------------------------------------------------------------

def parse_line_rhb(line, page_num, default_year="2025"):
    line = line.strip()
    if not line:
        return None

    # 1) Reflex Corporate
    m = PATTERN_RHB_REFLEX.search(line)
    if m:
        return parse_reflex(m, page_num)

    # 2) Islamic/Personal Format
    m = PATTERN_RHB_ISLAMIC.search(line)
    if m:
        return parse_islamic(m, page_num, default_year)

    return None


def parse_transactions_rhb(text, page_num, default_year="2025"):
    """
    Main RHB parser called by app.py.
    Works for ALL RHB formats.
    """
    tx_list = []
    for raw_line in text.splitlines():
        tx = parse_line_rhb(raw_line, page_num, default_year)
        if tx:
            tx_list.append(tx)

    return tx_list
