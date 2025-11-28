import regex as re

# ---------------------------------------------------------
# PATTERN 1 — Line WITH date:
# Example:
#   02/05 DEP-ECP 125453        1,411.99    2,780.16
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

# ---------------------------------------------------------
# PATTERN 2 — Line WITHOUT date:
# Example:
#   DEP-ECP 222798        20.09      2,800.25
# ---------------------------------------------------------
PATTERN_NO_DATE = re.compile(
    r"""
    ^(?P<desc>.+?)\s+                                 # description only
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+          # 20.09
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$           # 2,800.25
    """,
    re.VERBOSE
)

# ---------------------------------------------------------
# CLASSIFY CREDIT / DEBIT
# ---------------------------------------------------------
def _classify_debit_credit(desc: str, amount: float) -> tuple[float, float]:
    """
    Decide whether the amount is a debit or credit.
    Returns (debit, credit).
    """
    d = desc.upper()

    # MONEY IN (CREDITS)
    credit_keywords = [
        "DEP-ECP",             # Deposits
        "DUITNOW TRSF CR",     # DuitNow incoming
        "TSFR FUND CR",        # Transfer in
        "HSE CHEQ RTN",        # House cheque returned
    ]

    # MONEY OUT (DEBITS)
    debit_keywords = [
        "DUITNOW TRSF DR",
        "DR-ECP",
        "HANDLING CHRG",       # Fixed here — this is DEBIT
        "CHEQ ",
        "CHQ ",
        "GST DR",
        " DR ",                # generic DR
    ]

    is_credit = any(k in d for k in credit_keywords)
    is_debit  = any(k in d for k in debit_keywords)

    if is_credit and not is_debit:
        return 0.0, amount

    if is_debit and not is_credit:
        return amount, 0.0

    # Default fallback: deposit-heavy account → assume credit if uncertain
    return 0.0, amount


# ---------------------------------------------------------
# BUILD TRANSACTION OBJECT
# ---------------------------------------------------------
def _build_tx(date_str: str,
              desc: str,
              amount_raw: str,
              balance_raw: str,
              page_num: int,
              default_year: str = "2025") -> dict | None:

    desc = desc.strip()

    # Skip balance rows if they ever match
    if desc.upper().startswith("BALANCE "):
        return None

    # Convert date: dd/mm → yyyy-mm-dd
    day, month = date_str.split("/")
    full_date = f"{default_year}-{month}-{day}"

    # Convert numeric fields
    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    # Classify debit/credit
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
def parse_transactions_pbb(text: str, page_num: int, default_year: str = "2025"):
    """
    Parse all PBB transactions on a single PDF page.
    Handles:
      ✓ Lines with date
      ✓ Lines without date (use last seen date)
      ✓ Correct debit/credit classification
    """
    tx_list = []
    current_date = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # --------------------------
        # Match line WITH date
        # --------------------------
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

        # No date to attach a no-date row → skip
        if current_date is None:
            continue

        # --------------------------
        # Match line WITHOUT date
        # --------------------------
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
