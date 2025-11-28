import regex as re

# ---------------------------------------------------------
# Regex patterns built specifically for CIMB business PDF
# ---------------------------------------------------------

# Full row WITH date
RE_ROW_WITH_DATE = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2}/\d{4})\s+
    (?P<desc>.+?)\s+
    (?P<ref>\d{6,}|-)?
    \s+
    (?P<withdraw>\d{1,3}(?:,\d{3})*\.\d{2}|-)
    \s+
    (?P<deposit>\d{1,3}(?:,\d{3})*\.\d{2}|-)
    \s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})
    $
    """, re.VERBOSE
)

# Continuation rows (NO date)
RE_ROW_NO_DATE = re.compile(
    r"""
    ^(?P<desc>.+?)\s+
    (?P<ref>\d{6,}|-)?
    \s+
    (?P<withdraw>\d{1,3}(?:,\d{3})*\.\d{2}|-)
    \s+
    (?P<deposit>\d{1,3}(?:,\d{3})*\.\d{2}|-)
    \s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})
    $
    """, re.VERBOSE
)


# Opening / closing balance
RE_BALANCE_ONLY = re.compile(
    r"""
    ^(Opening\s+Balance|Closing\s+Balance)\s+
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})
    """, re.IGNORECASE | re.VERBOSE
)

# Detect Year from header
RE_YEAR = re.compile(r"\b(20\d{2})\b")


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def fix_date(d, default_year="2024"):
    """Convert DD/MM/YYYY → YYYY-MM-DD"""
    dd, mm, yyyy = d.split("/")
    return f"{yyyy}-{mm}-{dd}"


# ---------------------------------------------------------
# Main Parser (compatible with app.py)
# ---------------------------------------------------------

def parse_transactions_cimb(text: str, page_num: int, default_year="2025"):
    tx_list = []
    current_date = None
    prev_balance = None

    # Attempt to detect year from header
    m_year = RE_YEAR.search(text)
    year = m_year.group(1) if m_year else default_year

    # Replace DD/MM with DD/MM/YYYY for consistency
    text = re.sub(r"(\d{2}/\d{2})(?!/\d{4})", r"\1/" + year, text)

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # ------------------------------------------
        # Balance-only lines
        # ------------------------------------------
        m_bal = RE_BALANCE_ONLY.match(line)
        if m_bal:
            prev_balance = float(m_bal.group("amount").replace(",", ""))
            continue

        # ------------------------------------------
        # Rows WITH date
        # ------------------------------------------
        m1 = RE_ROW_WITH_DATE.match(line)
        if m1:
            current_date = m1.group("date")

            desc = m1.group("desc")
            ref = m1.group("ref")

            withdraw = m1.group("withdraw")
            deposit = m1.group("deposit")

            debit = float(withdraw.replace(",", "")) if withdraw not in ("-", None) else 0.0
            credit = float(deposit.replace(",", "")) if deposit not in ("-", None) else 0.0

            balance = float(m1.group("balance").replace(",", ""))

            tx_list.append({
                "date": fix_date(current_date),
                "description": desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            prev_balance = balance
            continue

        # ------------------------------------------
        # Rows WITHOUT date
        # ------------------------------------------
        m2 = RE_ROW_NO_DATE.match(line)
        if m2 and current_date:
            desc = m2.group("desc")
            ref = m2.group("ref")

            withdraw = m2.group("withdraw")
            deposit = m2.group("deposit")

            debit = float(withdraw.replace(",", "")) if withdraw not in ("-", None) else 0.0
            credit = float(deposit.replace(",", "")) if deposit not in ("-", None) else 0.0

            balance = float(m2.group("balance").replace(",", ""))

            tx_list.append({
                "date": fix_date(current_date),
                "description": desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            prev_balance = balance
            continue

    return tx_list
