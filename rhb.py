import regex as re

# ============================================================
# INTERNAL STATE (PERSISTS ACROSS PAGES)
# ============================================================

_prev_balance_global = None  # last seen balance in this statement


# ============================================================
# SIMPLE DESCRIPTION CLEANER
# ============================================================

def fix_description(desc):
    if not desc:
        return desc
    return " ".join(desc.split())


# ============================================================
# BALANCE → DEBIT / CREDIT LOGIC (FOR 2nd,3rd,... TX)
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    if prev_balance is None:
        # First usable tx should NOT come here anymore
        return 0.0, 0.0

    diff = round(curr_balance - prev_balance, 2)

    if diff > 0:
        # balance increased → credit
        return 0.0, diff
    elif diff < 0:
        # balance decreased → debit
        return abs(diff), 0.0
    else:
        return 0.0, 0.0


# ============================================================
# FIRST TRANSACTION: SCAN METHOD
# ============================================================

def classify_first_tx(desc, amount):
    """
    For the first transaction only (no previous balance),
    decide debit vs credit from description keywords.
    """
    if amount is None:
        return 0.0, 0.0

    s = re.sub(r"\s+", "", desc or "").upper()  # no spaces

    # Heuristics for CREDIT:
    # - cash deposit
    # - DUITNOW ... CR
    # - INWARD TRF CR
    # - anything ending with 'CR'
    if (
        "DEPOSIT" in s or
        "CDT" in s or
        "INWARD" in s or
        s.endswith("CR")
    ):
        return 0.0, amount  # credit

    # Otherwise treat as DEBIT (fees, DR, MYDEBIT, etc)
    return amount, 0.0


# ============================================================
# REGEX PATTERNS
# ============================================================

MONTH_MAP = {
    "Jan": "-01-", "Feb": "-02-", "Mar": "-03-",
    "Apr": "-04-", "May": "-05-", "Jun": "-06-",
    "Jul": "-07-", "Aug": "-08-", "Sep": "-09-",
    "Oct": "-10-", "Nov": "-11-", "Dec": "-12-"
}

PATTERN_TX = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"
    r"(.+?)\s+"
    r"(\d{6,12})\s+"
    r"([0-9,]+\.\d{2})\s+"
    r"([0-9,]+\.\d{2})$"
)

PATTERN_BF_CF = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+(B/F BALANCE|C/F BALANCE)\s+([0-9,]+\.\d{2})$"
)


# ============================================================
# LINE PARSER
# ============================================================

def parse_line_rhb(line, page_num, year=2025):
    line = line.strip()
    if not line:
        return None

    # B/F or C/F row → we will IGNORE for logic (no output, no balance)
    m_bf = PATTERN_BF_CF.match(line)
    if m_bf:
        # If you ever want to use opening/closing internally, you could,
        # but per your request we ignore it now.
        return {"type": "bf_cf"}

    # Normal transaction (first line only)
    m = PATTERN_TX.match(line)
    if not m:
        return None

    day, mon, desc_raw, serial, amt1, amt2 = m.groups()
    date_fmt = f"{year}{MONTH_MAP.get(mon, '-01-')}{day.zfill(2)}"

    return {
        "type": "tx",
        "date": date_fmt,
        "description": fix_description(desc_raw),
        "serial": serial,
        "amount_raw": float(amt1.replace(",", "")),
        "balance": float(amt2.replace(",", "")),
        "page": page_num,
    }


# ============================================================
# MAIN: parse_transactions_rhb() — MUST RETURN ONLY A LIST
# ============================================================

def parse_transactions_rhb(text, page_num, year=2025):
    """
    - First transaction (after reset) → scan description to decide debit/credit.
    - Subsequent transactions → use balance difference.
    - B/F and C/F rows are ignored.
    """
    global _prev_balance_global

    # Assume page 1 = new statement → reset continuity
    if page_num == 1:
        _prev_balance_global = None

    tx_list = []

    for raw_line in text.splitlines():
        parsed = parse_line_rhb(raw_line, page_num, year)
        if not parsed:
            continue

        # Skip B/F & C/F completely (no state update)
        if parsed["type"] == "bf_cf":
            continue

        curr_balance = parsed["balance"]
        amount = parsed["amount_raw"]

        # FIRST TX: prev_balance is None → scan method
        if _prev_balance_global is None:
            debit, credit = classify_first_tx(parsed["description"], amount)
        else:
            # NEXT TX: use balance diff
            debit, credit = compute_debit_credit(_prev_balance_global, curr_balance)

        tx = {
            "date": parsed["date"],
            "description": parsed["description"],  # first line only
            "debit": debit,
            "credit": credit,
            "balance": round(curr_balance, 2),
            "page": page_num,
        }

        tx_list.append(tx)
        _prev_balance_global = curr_balance  # update continuity

    return tx_list
