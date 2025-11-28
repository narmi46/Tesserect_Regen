import regex as re

# =========================================================
# PATTERN 1 — Line WITH date, debit, credit, balance
# Example:
#    02/04 DEP-ECP 233130      -     83.65      31,838.34
#    02/04 DEP-ECP 151106      -   1,537.39     30,754.54
# =========================================================
PATTERN_WITH_DATE = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+                     # 02/04
    (?P<desc>.+?)\s+                              # Description
    (?P<debit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+  # Debit column
    (?P<credit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+ # Credit column
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$       # Balance
    """,
    re.VERBOSE
)

# =========================================================
# PATTERN 2 — NO DATE lines (carry forward previous date)
# =========================================================
PATTERN_NO_DATE = re.compile(
    r"""
    ^(?P<desc>.+?)\s+
    (?P<debit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+
    (?P<credit>-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """,
    re.VERBOSE
)

# =========================================================
# SPECIAL CASE — Date + Balance-only lines
# Example:
#   31/03 Balance B/F 29,217.15
#   02/04 Balance C/F 31,754.69
# =========================================================
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
    desc = desc.strip()

    # Skip Balance B/F, C/F entries
    if desc.upper().startswith("BALANCE"):
        return None

    # Format date → yyyy-mm-dd
    dd, mm = date_str.split("/")
    full_date = f"{default_year}-{mm}-{dd}"

    # Convert numbers
    debit  = float(debit_raw.replace(",", "")) if debit_raw.strip() not in ("", "-") else 0.0
    credit = float(credit_raw.replace(",", "")) if credit_raw.strip() not in ("", "-") else 0.0
    balance = float(balance_raw.replace(",", ""))

    return {
        "date": full_date,
        "description": desc,
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

        # ---------------------------------------------------
        # Case A: DATE + Balance-only line (no debit/credit)
        # ---------------------------------------------------
        m_bal = PATTERN_BALANCE_DATE_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")  # update date
            continue

        # ---------------------------------------------------
        # Case B: Full row WITH DATE
        # ---------------------------------------------------
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

        # If we have no date yet → cannot parse continuation lines
        if current_date is None:
            continue

        # ---------------------------------------------------
        # Case C: NO-DATE line (description + debit + credit)
        # ---------------------------------------------------
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
