import regex as re

# ============================================================
# UNIVERSAL RHB STATEMENT PARSER
# ============================================================

PATTERN_RHB_REFLEX = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"
    r"(\d{3})\s+"
    r"(.+?)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2})([+-])"
)

PATTERN_RHB_ISLAMIC = re.compile(
    r"^(?:0[1-9]|[12][0-9]|3[01])\s+[A-Za-z]{3}\s+"
    r"(?!B/F|C/F|DEPOSIT|ACCOUNT|SUMMARY|RINGKASAN|\(RM\))"
    r"(.+?)\s+"
    r"(\d{6,12}|-)\s+"
    r"([0-9,]+\.\d{2})\s+"
    r"([0-9,]+\.\d{2})$"
)

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

BLOCKED_PREFIXES = (
    "RHBQR",
    "DuitQR",
    "Fund Transfer",
    "DR.",
    "MY CARD",
    "KUALA LUMPUR",
    "Oversize",
    "Restock",
    "Payment",
    "baju",
    "pay",
)


def parse_reflex(m, page_num):
    date_raw, branch, desc, dr_raw, cr_raw, bal_raw, sign = m.groups()
    d, m_, y = date_raw.split("-")
    date = f"{y}-{m_}-{d}"

    debit = float(dr_raw.replace(",", "")) if dr_raw != "-" else 0
    credit = float(cr_raw.replace(",", "")) if cr_raw != "-" else 0

    balance = float(bal_raw.replace(",", ""))
    if sign == "-":
        balance = -balance

    return dict(
        date=date,
        description=f"{branch} {desc.strip()}",
        debit=debit,
        credit=credit,
        balance=balance,
        page=page_num,
    )


def parse_islamic(m, page_num, default_year="2025"):
    desc, refnum, amount_raw, balance_raw = m.groups()

    parts = m.group(0).split()
    day, mon = parts[0], parts[1]
    date = f"{default_year}-{MONTH_MAP[mon]}-{day}"

    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    # Debit detection
    text = desc.lower()
    debit_keywords = ("dr", "deduct", "withdraw", "atm", "mbk instant trf dr")

    if any(k in text for k in debit_keywords):
        debit = amount
        credit = 0
    else:
        debit = 0
        credit = amount

    return dict(
        date=date,
        description=desc.strip(),
        debit=debit,
        credit=credit,
        balance=balance,
        page=page_num,
    )


def parse_line_rhb(line, page_num, default_year="2025"):
    line = line.strip()
    if not line:
        return None

    # Skip continuation lines
    if line.startswith(BLOCKED_PREFIXES):
        return None

    # Corporate Reflex
    m = PATTERN_RHB_REFLEX.search(line)
    if m:
        return parse_reflex(m, page_num)

    # Islamic / Personal
    m = PATTERN_RHB_ISLAMIC.search(line)
    if m:
        return parse_islamic(m, page_num, default_year)

    return None


def parse_transactions_rhb(text, page_num, default_year="2025"):
    tx_list = []
    for line in text.splitlines():
        tx = parse_line_rhb(line, page_num, default_year)
        if tx:
            tx_list.append(tx)
    return tx_list
