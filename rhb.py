import regex as re

# ============================================================
# UNIVERSAL RHB STATEMENT PARSER
# Supports:
#   1. Reflex Corporate Format
#   2. Islamic/QARD Current Account
#   3. Personal Current Account (e.g. Mar 2024)
# ============================================================

# ------------------------------------------------------------
# Regex Patterns
# ------------------------------------------------------------

# 1️⃣ Reflex Corporate Format (branch code + +/- balance)
PATTERN_RHB_REFLEX = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"          # 01-10-2024
    r"(\d{3})\s+"                      # 999
    r"(.+?)\s+"                        # Description
    r"([0-9,]+\.\d{2}|-)\s+"           # Debit OR '-'
    r"([0-9,]+\.\d{2}|-)\s+"           # Credit OR '-'
    r"([0-9,]+\.\d{2})([+-])"          # Balance with +/-
)

# 2️⃣ Islamic / Personal RHB Format
PATTERN_RHB_ISLAMIC = re.compile(
    r"^(?:0[1-9]|[12][0-9]|3[01])\s+[A-Za-z]{3}\s+"                   # 07 Mar
    r"(?!B/F|C/F|DEPOSIT|ACCOUNT|SUMMARY|RINGKASAN|\(RM\))"          # Skip summary lines
    r"(.+?)\s+"                                                       # Description
    r"(\d{6,12}|-)\s+"                                                # Cheque/ref no.
    r"([0-9,]+\.\d{2})\s+"                                            # Amount
    r"([0-9,]+\.\d{2})"                                               # Balance
)

MONTH_MAP = {
    "Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
    "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"
}

# Lines that belong to descriptions (we must skip them)
BLOCKED_PREFIXES = (
    "RHBQR",
    "DUITNOW",
    "DuitQR",
    "QR P2P",
    "Fund Transfer",
    "Payment",
    "Oversize",
    "Restock",
    "pay",
    "MYDEBIT",
    "MY CARD",
    "ATM CASH",
    "KUALA",
)


# ------------------------------------------------------------
# Helper Parsing Functions
# ------------------------------------------------------------

def parse_reflex(m, page_num):
    date_raw, branch, desc, dr_raw, cr_raw, bal_raw, sign = m.groups()

    # Convert DD-MM-YYYY to YYYY-MM-DD
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
    desc, refnum, amount_raw, balance_raw = m.groups()

    # Extract date from the matched text
    full_text = m.group(0).split()
    day = full_text[0]
    mon = full_text[1]

    full_date = f"{default_year}-{MONTH_MAP.get(mon,'01')}-{day}"

    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    text_lower = desc.lower()

    # Basic debit detection
    debit_keywords = (" dr", "deduct", "withdraw", "atm", "mbk instant trf dr")
    if any(k in text_lower for k in debit_keywords):
        debit = amount
        credit = 0.0
    else:
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
# LINE PARSER (auto-detect format)
# ------------------------------------------------------------

def parse_line_rhb(line, page_num, default_year="2025"):
    line = line.strip()
    if not line:
        return None

    # Skip continuation description lines (very common in Mar 2024 file)
    if line.startswith(BLOCKED_PREFIXES):
        return None

    # 1) Reflex Corporate
    m = PATTERN_RHB_REFLEX.search(line)
    if m:
        return parse_reflex(m, page_num)

    # 2) Islamic / Personal formats
    m = PATTERN_RHB_ISLAMIC.search(line)
    if m:
        return parse_islamic(m, page_num, default_year)

    return None


# ------------------------------------------------------------
# MASTER FUNCTION
# ------------------------------------------------------------

def parse_transactions_rhb(text, page_num, default_year="2025"):
    results = []

    for line in text.splitlines():
        tx = parse_line_rhb(line, page_num, default_year)
        if tx:
            results.append(tx)

    return results
