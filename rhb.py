import regex as re

# ============================================================
# RHB STATEMENT PARSER (GLUED-TEXT FORMAT)
# No opening/closing rows in output.
# Debit/Credit from balance movement between parsed rows only.
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
    
    out = []
    buf = ""
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
# BALANCE-BASED DEBIT/CREDIT (INTRA-MONTH ONLY)
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    """
    Determine debit/credit based on movement **between parsed rows only**.
    First parsed row will have no movement (0, 0).
    """
    if prev_balance is None:
        return 0.0, 0.0  # first parsed row

    if curr_balance < prev_balance:
        return prev_balance - curr_balance, 0.0  # Debit

    if curr_balance > prev_balance:
        return 0.0, curr_balance - prev_balance  # Credit

    return 0.0, 0.0


# ============================================================
# REGEX
# ============================================================

MONTH_MAP = {
    "Jan": "-01-", "Feb": "-02-", "Mar": "-03-",
    "Apr": "-04-", "May": "-05-", "Jun": "-06-",
    "Jul": "-07-", "Aug": "-08-", "Sep": "-09-",
    "Oct": "-10-", "Nov": "-11-", "Dec": "-12-"
}

PATTERN_RHB = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"       # 07Mar
    r"(.+?)\s+"                         # description (glued)
    r"(\d{6,12})\s+"                    # serial
    r"([0-9,]+\.\d{2})\s+"              # amount1 (ignored)
    r"([0-9,]+\.\d{2})$"                # amount2 = balance
)

def parse_line_rhb(line, page_num, year=2024):
    m = PATTERN_RHB.match(line)
    if not m:
        return None

    day, mon, desc_raw, serial, amt1, amt2 = m.groups()

    month_num = MONTH_MAP.get(mon, "-01-")
    date_fmt = f"{year}{month_num}{day.zfill(2)}"

    desc_clean = fix_description(desc_raw)
    balance = float(amt2.replace(",", ""))

    return {
        "date": date_fmt,
        "description": desc_clean,
        "serial": serial,
        "raw_amount": float(amt1.replace(",", "")),  # info only
        "balance": balance,
        "page": page_num,
    }


# ============================================================
# PAGE PARSER (NO OPENING/CLOSING ROWS)
# ============================================================

def parse_transactions_rhb(text, page_num, year=2024):
    """
    Parses a glued-text page into **only real transactions**:
    - No B/F BALANCE row
    - No C/F BALANCE row
    - First parsed tx will have debit=credit=0 (no previous balance known)
    """
    tx_list = []
    prev_balance = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        tx = parse_line_rhb(line, page_num, year)
        if not tx:
            # this also naturally skips B/F BALANCE & C/F BALANCE
            continue

        curr_balance = tx["balance"]
        debit, credit = compute_debit_credit(prev_balance, curr_balance)

        tx["debit"] = debit
        tx["credit"] = credit

        tx_list.append(tx)
        prev_balance = curr_balance

    return tx_list


# ============================================================
# EXAMPLE
# ============================================================

sample_text = """
07May ATMWITHDRAWAL 0000001552 1,500.00 2,004.40
07May ATMWITHDRAWAL 0000001553 1,500.00 504.40
07May RPPINWARDINSTTRFCR 0000001943 602.00 1,106.40
"""

if __name__ == "__main__":
    parsed = parse_transactions_rhb(sample_text, page_num=1)
    for p in parsed:
        print(p)
