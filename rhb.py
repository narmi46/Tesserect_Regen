# rhb.py (fixed for app.py compatibility)
import regex as re

# ============================================================
# INTERNAL STATE (PERSISTS ACROSS PAGES)
# ============================================================

# This persists between calls from app.py
_prev_balance_global = None


# ============================================================
# TOKEN SPLITTING
# ============================================================

KNOWN_TOKENS = [
    "CDT", "CASH", "DEPOSIT",
    "ANNUAL", "FEES",
    "DUITNOW", "QR", "P2P", "CR", "DR",
    "RPP", "INWARD", "INST", "TRF",
    "MBK", "INSTANT",
    "MYDEBIT", "FUND", "MB", "ATM",
    "WITHDRAWAL", "PAYMENT", "TRANSFER"
]

def split_tokens_glued(text):
    s = text
    result = []

    while s:
        matched = False
        for tok in sorted(KNOWN_TOKENS, key=len, reverse=True):
            if s.startswith(tok):
                result.append(tok)
                s = s[len(tok) :]
                matched = True
                break
        if not matched:
            result.append(s[0])
            s = s[1:]

    out, buf = [], ""
    for p in result:
        if p in KNOWN_TOKENS:
            if buf:
                out.append(buf)
                buf = ""
            out.append(p)
        else:
            buf += p
    if buf:
        out.append(buf)

    return " ".join(out)


def fix_description(desc):
    if not desc:
        return desc

    desc = split_tokens_glued(desc)
    desc = re.sub(r"([A-Za-z])(\d)", r"\1 \2", desc)
    desc = re.sub(r"(\d)([A-Za-z])", r"\1 \2", desc)

    return " ".join(desc.split())


# ============================================================
# BALANCE → DEBIT / CREDIT LOGIC
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    if prev_balance is None:
        return 0.0, 0.0

    if curr_balance < prev_balance:
        return round(prev_balance - curr_balance, 2), 0.0

    if curr_balance > prev_balance:
        return 0.0, round(curr_balance - prev_balance, 2)

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

    # B/F + C/F first
    m_bf = PATTERN_BF_CF.match(line)
    if m_bf:
        day, mon, kind, bal = m_bf.groups()
        date_fmt = f"{year}{MONTH_MAP.get(mon,'-01-')}{day.zfill(2)}"
        return {
            "type": "bf_cf",
            "kind": kind,
            "balance": float(bal.replace(",", "")),
            "date": date_fmt,
            "page": page_num,
        }

    # Then normal TX
    m = PATTERN_TX.match(line)
    if not m:
        return None

    day, mon, desc_raw, serial, amt1, amt2 = m.groups()
    date_fmt = f"{year}{MONTH_MAP.get(mon,'-01-')}{day.zfill(2)}"

    desc_clean = fix_description(desc_raw)

    return {
        "type": "tx",
        "date": date_fmt,
        "description": desc_clean,
        "serial": serial,
        "raw_amount": float(amt1.replace(",", "")),
        "balance": float(amt2.replace(",", "")),
        "page": page_num,
    }


# ============================================================
# MAIN: parse_transactions_rhb() — MUST RETURN ONLY A LIST
# ============================================================

def parse_transactions_rhb(text, page_num, year=2025):
    """
    REQUIRED BY YOUR APP:
    - Accept (text, page_num)
    - Return LIST ONLY
    - Maintain balance continuity internally
    """
    global _prev_balance_global

    tx_list = []

    for raw_line in text.splitlines():
        parsed = parse_line_rhb(raw_line, page_num, year)
        if not parsed:
            continue

        # -----------------------
        # Handle B/F & C/F rows
        # -----------------------
        if parsed["type"] == "bf_cf":
            # If B/F → this page's starting balance
            if parsed["kind"] == "B/F BALANCE":
                _prev_balance_global = parsed["balance"]

            # If C/F → update closing balance but DO NOT emit row
            elif parsed["kind"] == "C/F BALANCE":
                _prev_balance_global = parsed["balance"]

            continue

        # ---------------------------------
        # Normal transaction
        # ---------------------------------

        curr_balance = parsed["balance"]
        debit, credit = compute_debit_credit(_prev_balance_global, curr_balance)

        tx = {
            "date": parsed["date"],
            "description": parsed["description"],
            "debit": debit,
            "credit": credit,
            "balance": round(curr_balance, 2),
            "page": page_num,
        }

        tx_list.append(tx)

        # Update continuity
        _prev_balance_global = curr_balance

    return tx_list  # ✔ app.py expects ONLY a list
