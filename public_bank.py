import regex as re

# =========================================================
# PATTERNS
# =========================================================

# Row WITH DATE + DEBIT + CREDIT + BALANCE
PATTERN_WITH_DATE = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+                      # 02/04
    (?P<desc>.+?)\s+                               # Description
    (?P<debit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+   # Debit column
    (?P<credit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+  # Credit column
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$        # Balance
    """,
    re.VERBOSE
)

# Row WITHOUT DATE (inherits previous date)
PATTERN_NO_DATE = re.compile(
    r"""
    ^(?P<desc>.+?)\s+
    (?P<debit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+
    (?P<credit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """,
    re.VERBOSE
)

# Balance-only rows (Balance B/F or C/F)
PATTERN_BALANCE_DATE_ONLY = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+
    (?P<desc>Balance.*)\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """,
    re.VERBOSE | re.IGNORECASE
)

# =========================================================
# BUILD TRANSACTION OBJECT
# =========================================================
def _build_tx(date_str, desc, debit_raw, credit_raw, balance_raw, page_num, default_year="2025"):

    # Skip balance forward/carry lines
    if desc.upper().startswith("BALANCE"):
        return None

    # Convert dd/mm → yyyy-mm-dd
    dd, mm = date_str.split("/")
    iso_date = f"{default_year}-{mm}-{dd}"

    # Normalize numeric fields
    def norm(x):
        return float(x.replace(",", "")) if x.strip() not in ("", "-") else 0.0

    debit = norm(debit_raw)
    credit = norm(credit_raw)
    balance = norm(balance_raw)

    return {
        "date": iso_date,
        "description": desc.strip(),
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }

# =========================================================
# MAIN PARSER
# =========================================================
def parse_transactions_pbb(text: str, page_num: int, default_year="2025"):
    tx_list = []
    current_date = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # -------------------------------
        # Case A — Balance B/F or C/F
        # -------------------------------
        m_bal = PATTERN_BALANCE_DATE_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")   # anchor date
            continue

        # -------------------------------
        # Case B — WITH DATE
        # -------------------------------
        m1 = PATTERN_WITH_DATE.match(line)
        if m1:
            current_date = m1.group("date")
            tx = _build_tx(
                m1.group("date"),
                m1.group("desc"),
                m1.group("debit"),
                m1.group("credit"),
                m1.group("balance"),
                page_num,
                default_year,
            )
            if tx:
                tx_list.append(tx)
            continue

        # Cannot parse no-date rows without a date
        if current_date is None:
            continue

        # -------------------------------
        # Case C — NO DATE rows
        # -------------------------------
        m2 = PATTERN_NO_DATE.match(line)
        if m2:
            tx = _build_tx(
                current_date,
                m2.group("desc"),
                m2.group("debit"),
                m2.group("credit"),
                m2.group("balance"),
                page_num,
                default_year,
            )
            if tx:
                tx_list.append(tx)
            continue

    return tx_list
