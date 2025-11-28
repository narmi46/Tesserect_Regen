import regex as re

# ---------------------------------------------------------
# PATTERN 1 — Line WITH date AND amount:
# Example:
#   02/01 DEP-ECP 130045      609.99    2,889.09
# ---------------------------------------------------------
PATTERN_WITH_DATE = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+                       # 02/01
    (?P<desc>.+?)\s+                                # DEP-ECP 130045
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+        # 609.99
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$         # 2,889.09
    """,
    re.VERBOSE
)

# ---------------------------------------------------------
# PATTERN 2 — Line WITHOUT date:
# Example:
#   DEP-ECP 222799     39.80     2,840.05
# ---------------------------------------------------------
PATTERN_NO_DATE = re.compile(
    r"""
    ^(?P<desc>.+?)\s+
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """,
    re.VERBOSE
)

# ---------------------------------------------------------
# PATTERN 3 — SPECIAL CASE:
# Line has DATE but **NO amount column** (Balance B/F, C/F, From Last Statement)
# Example:
#   31/01 Balance B/F 23154.70
#   02/01 Balance From Last Statement 2279.10
# ---------------------------------------------------------
PATTERN_BALANCE_DATE_ONLY = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+                 # 31/01
    (?P<desc>Balance.*|BALANCE.*)\s+          # Balance B/F, Balance C/F
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$   # 23154.70
    """,
    re.VERBOSE | re.IGNORECASE
)

# ---------------------------------------------------------
# CLASSIFY CREDIT / DEBIT
# ---------------------------------------------------------
def _classify_debit_credit(desc: str, amount: float):
    """
    Determine whether the amount is debit or credit.
    """
    d = desc.upper()

    # MONEY IN (CREDIT)
    credit_keywords = [
        "DEP-ECP",
        "DUITNOW TRSF CR",
        "TSFR FUND CR",
        "HSE CHEQ RTN",
    ]

    # MONEY OUT (DEBIT)
    debit_keywords = [
        "DUITNOW TRSF DR",
        "DR-ECP",
        "HANDLING CHRG",
        "CHEQ ",
        "CHQ ",
        "GST DR",
        " DR ",
    ]

    is_credit = any(k in d for k in credit_keywords)
    is_debit  = any(k in d for k in debit_keywords)

    if is_credit and not is_debit:
        return 0.0, amount

    if is_debit and not is_credit:
        return amount, 0.0

    # Default: Public Bank Current Account typically inflow heavy
    return 0.0, amount


# ---------------------------------------------------------
# BUILD TX DICTIONARY
# ---------------------------------------------------------
def _build_tx(date_str, desc, amount_raw, balance_raw, page_num, default_year="2025"):
    desc = desc.strip()

    # Exclude unwanted non-transaction lines
    if desc.upper().startswith("BALANCE"):
        return None

    # Date "dd/mm" → "yyyy-mm-dd"
    dd, mm = date_str.split("/")
    full_date = f"{default_year}-{mm}-{dd}"

    # Convert numbers
    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    debit, credit = _classify_debit_credit(desc, amount)

    return {
        "date": full_date,
        "description": desc,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


# ---------------------------------------------------------
# MAIN PARSER
# ---------------------------------------------------------
def parse_transactions_pbb(text: str, page_num: int, default_year="2025"):
    tx_list = []
    current_date = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # -------------------------------------------------
        # SPECIAL FIX: DATE + Balance B/F but **NO debit/credit**
        # Example:
        #   "31/01 Balance B/F 23154.70"
        # This DOES NOT create a transaction,
        # but MUST SET the date so next rows inherit it.
        # -------------------------------------------------
        m_bal = PATTERN_BALANCE_DATE_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")   # anchor the date
            continue                              # do NOT create a transaction

        # -------------------------------------------------
        # Case 1 — WITH DATE + AMOUNT
        # -------------------------------------------------
        m1 = PATTERN_WITH_DATE.match(line)
        if m1:
            current_date = m1.group("date")
            tx = _build_tx(
                m1.group("date"),
                m1.group("desc"),
                m1.group("amount"),
                m1.group("balance"),
                page_num,
                default_year
            )
            if tx:
                tx_list.append(tx)
            continue

        # If no date yet, cannot parse rows without date
        if current_date is None:
            continue

        # -------------------------------------------------
        # Case 2 — NO DATE (continuation rows)
        # -------------------------------------------------
        m2 = PATTERN_NO_DATE.match(line)
        if m2:
            tx = _build_tx(
                current_date,
                m2.group("desc"),
                m2.group("amount"),
                m2.group("balance"),
                page_num,
                default_year
            )
            if tx:
                tx_list.append(tx)
            continue

    return tx_list
