import regex as re

# ============================================================
# Proper token splitting for glued descriptions
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
                s = s[len(tok):]
                matched = True
                break
        if not matched:
            result.append(s[0])
            s = s[1:]

    # merge non-tokens
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
# Debit/Credit calculation
# ============================================================

def compute_debit_credit(prev, curr):
    if prev is None:
        return 0.0, 0.0
    if curr < prev:
        return round(prev - curr, 2), 0.0
    if curr > prev:
        return 0.0, round(curr - prev, 2)
    return 0.0, 0.0


# ============================================================
# Regex for RHB transactions
# ============================================================

MONTH_MAP = {
    "Jan": "-01-", "Feb": "-02-", "Mar": "-03-",
    "Apr": "-04-", "May": "-05-", "Jun": "-06-",
    "Jul": "-07-", "Aug": "-08-", "Sep": "-09-",
    "Oct": "-10-", "Nov": "-11-", "Dec": "-12-"
}

# matches real transaction rows
PATTERN_RHB = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"
    r"(.+?)\s+"
    r"(\d{6,12})\s+"
    r"([0-9,]+\.\d{2})\s+"
    r"([0-9,]+\.\d{2})$"
)

# B/F and C/F detection
PATTERN_BF_CF = re.compile(r"^\d{1,2}[A-Za-z]{3}\s+(B/F BALANCE|C/F BALANCE)\s+([0-9,]+\.\d{2})$")


def parse_line_rhb(line, page_num, year=2024):
    # Detect B/F and C/F rows (for continuity)
    bf = PATTERN_BF_CF.match(line)
    if bf:
        desc, bal = bf.groups()
        return {"bf_cf": desc, "balance": float(bal.replace(",", ""))}

    m = PATTERN_RHB.match(line)
    if not m:
        return None

    day, mon, desc_raw, serial, amt1, amt2 = m.groups()
    date_fmt = f"{year}{MONTH_MAP.get(mon, '-01-')}{day.zfill(2)}"

    desc_clean = fix_description(desc_raw)

    return {
        "date": date_fmt,
        "description": desc_clean,
        "serial": serial,
        "raw_amount": float(amt1.replace(",", "")),
        "balance": float(amt2.replace(",", "")),
        "page": page_num
    }


# ============================================================
# Page parser with B/F & C/F logic
# ============================================================

def parse_transactions_rhb(text, page_num, prev_end_balance=None, year=2024):
    tx_list = []
    prev_balance = prev_end_balance  # from previous page

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        parsed = parse_line_rhb(line, page_num, year)
        if not parsed:
            continue

        # handle B/F BALANCE
        if "bf_cf" in parsed and parsed["bf_cf"] == "B/F BALANCE":
            prev_balance = parsed["balance"]
            continue

        # handle C/F BALANCE
        if "bf_cf" in parsed and parsed["bf_cf"] == "C/F BALANCE":
            # return this as new end balance
            return tx_list, parsed["balance"]

        # real transaction
        curr = parsed["balance"]
        debit, credit = compute_debit_credit(prev_balance, curr)

        parsed["debit"] = debit
        parsed["credit"] = credit

        tx_list.append(parsed)
        prev_balance = curr

    return tx_list, prev_balance
