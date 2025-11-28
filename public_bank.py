import regex as re

# ---------------------------------------------------------
# Patterns:
#   1) Line WITH date: "02/05 DEP-ECP 125453 1,411.99 2,780.16"
#   2) Line WITHOUT date: "DEP-ECP 222798 20.09 2,800.25"
# Only lines with TWO decimal numbers (amount + balance) are matched.
# ---------------------------------------------------------

PATTERN_WITH_DATE = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+                         # 02/05
    (?P<desc>.+?)\s+                                  # description
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+          # 1,411.99
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$           # 2,780.16
    """,
    re.VERBOSE
)

PATTERN_NO_DATE = re.compile(
    r"""
    ^(?P<desc>.+?)\s+                                 # description only
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+          # 20.09
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$           # 2,800.25
    """,
    re.VERBOSE
)

def _classify_debit_credit(desc: str, amount: float) -> tuple[float, float]:
    """
    Decide whether 'amount' is a debit or credit based on the description.
    Returns (debit, credit).
    """
    d = desc.upper()

    # Clear credit patterns (money IN)
    credit_keywords = [
        "DEP-ECP",               # deposits
        "DUITNOW TRSF CR",       # DuitNow credit
        "TSFR FUND CR",          # transfer in
        "TSFR FUND  CR",
        "HSE CHEQ RTN",          # house cheque returned -> back to account
    ]

    # Clear debit patterns (money OUT)
    debit_keywords = [
        "DUITNOW TRSF DR",
        "DR-ECP",
        " HANDLING CHRG",
        "CHEQ ",                 # cheque payments
        "CHQ ",                  # alt spelling
        "GST DR",
        " DR ",                  # generic DR
    ]

    is_credit = any(k in d for k in credit_keywords)
    is_debit  = any(k in d for k in debit_keywords)

    if is_credit and not is_debit:
        return 0.0, amount
    if is_debit and not is_credit:
        return amount, 0.0

    # Default: for this account type, most transactions are deposits,
    # so safest default is to treat as credit.
    return 0.0, amount


def _build_tx(date_str: str,
              desc: str,
              amount_raw: str,
              balance_raw: str,
              page_num: int,
              default_year: str = "2025") -> dict | None:
    """
    Build a transaction dict from parsed parts.
    """
    desc = desc.strip()

    # Optional: skip pure balance rows if they ever match patterns
    if desc.upper().startswith("BALANCE ") or desc.upper().startswith("CLOSING BALANCE"):
        return None

    # Convert date dd/mm -> yyyy-mm-dd
    day, month = date_str.split("/")
    full_date = f"{default_year}-{month}-{day}"

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


def parse_transactions_pbb(text: str, page_num: int, default_year: str = "2025"):
    """
    Parse all PBB transactions on a single page of text.
    Handles:
      - First row with date
      - Subsequent rows on same date without date
    """
    tx_list = []
    current_date = None  # remembers last seen date like "02/05"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Try match line WITH date
        m = PATTERN_WITH_DATE.match(line)
        if m:
            current_date = m.group("date")
            desc = m.group("desc")
            amount_raw = m.group("amount")
            balance_raw = m.group("balance")

            tx = _build_tx(current_date, desc, amount_raw, balance_raw,
                           page_num, default_year)
            if tx:
                tx_list.append(tx)
            continue

        # If no date yet, we can't assign a date to no-date rows
        if current_date is None:
            continue

        # Try match line WITHOUT date (same date as previous)
        m2 = PATTERN_NO_DATE.match(line)
        if m2:
            desc = m2.group("desc")
            amount_raw = m2.group("amount")
            balance_raw = m2.group("balance")

            tx = _build_tx(current_date, desc, amount_raw, balance_raw,
                           page_num, default_year)
            if tx:
                tx_list.append(tx)

    return tx_list
