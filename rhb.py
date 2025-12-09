import regex as re

# ============================================================
# INTERNAL STATE (PERSISTS ACROSS PAGES, BUT NOT ACROSS STATEMENTS)
# ============================================================

_prev_balance_global = None


# ============================================================
# SIMPLE DESCRIPTION CLEANER (FIRST LINE ONLY)
# ============================================================

def fix_description(desc):
    if not desc:
        return desc
    # just normalize spaces
    return " ".join(desc.split())


# ============================================================
# BALANCE → DEBIT / CREDIT LOGIC
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    if prev_balance is None:
        # first usable row → no debit/credit inferred
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
# REGEX PATTERNS
# ============================================================

MONTH_MAP = {
    "Jan": "-01-", "Feb": "-02-", "Mar": "-03-",
    "Apr": "-04-", "May": "-05-", "Jun": "-06-",
    "Jul": "-07-", "Aug": "-08-", "Sep": "-09-",
    "Oct": "-10-", "Nov": "-11-", "Dec": "-12-"
}

# One-line transaction: date + desc(first line only) + serial + amount + balance
PATTERN_TX = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"      # day + month
    r"(.+?)\s+"                        # description (first line)
    r"(\d{6,12})\s+"                   # serial
    r"([0-9,]+\.\d{2})\s+"             # amount
    r"([0-9,]+\.\d{2})$"               # balance
)

PATTERN_BF_CF = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"
    r"(B/F BALANCE|C/F BALANCE)\s+"
    r"([0-9,]+\.\d{2})$"
)


# ============================================================
# LINE PARSER
# ============================================================

def parse_line_rhb(line, page_num, year=2025):
    line = line.strip()
    if not line:
        return None

    # B/F or C/F row
    m_bf = PATTERN_BF_CF.match(line)
    if m_bf:
        day, mon, kind, bal = m_bf.groups()
        date_fmt = f"{year}{MONTH_MAP.get(mon, '-01-')}{day.zfill(2)}"
        return {
            "type": "bf_cf",
            "kind": kind,
            "balance": float(bal.replace(",", "")),
            "date": date_fmt,
            "page": page_num,
        }

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
# MAIN: parse_transactions_rhb() — RETURN LIST ONLY
# ============================================================

def parse_transactions_rhb(text, page_num, year=2025):
    """
    - Accepts (text, page_num, year)
    - Returns LIST ONLY
    - Maintains balance continuity ACROSS PAGES of same statement
    - Resets continuity automatically when page_num == 1
    """
    global _prev_balance_global

    # 🔑 IMPORTANT FIX:
    # New statement usually starts at page 1 → reset previous balance
    if page_num == 1:
        _prev_balance_global = None

    tx_list = []

    for raw_line in text.splitlines():
        parsed = parse_line_rhb(raw_line, page_num, year)
        if not parsed:
            continue

        # Handle B/F & C/F lines: update internal balance but DO NOT emit
        if parsed["type"] == "bf_cf":
            _prev_balance_global = parsed["balance"]
            continue

        # Normal transaction
        curr_balance = parsed["balance"]
        debit, credit = compute_debit_credit(_prev_balance_global, curr_balance)

        tx_list.append({
            "date": parsed["date"],
            "description": parsed["description"],  # first line only
            "debit": debit,
            "credit": credit,
            "balance": curr_balance,
            "page": page_num,
        })

        _prev_balance_global = curr_balance

    return tx_list
