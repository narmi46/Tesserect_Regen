import regex as re

# ============================================================
# RHB STATEMENT PARSER (GLUED-TEXT FORMAT)
# Uses BALANCE CHANGE to determine DEBIT / CREDIT accurately.
# ============================================================

# Known tokens to split glued descriptions (e.g., DUITNOWQRP2PCR)
KNOWN_TOKENS = [
    "CDT", "CASH", "DEPOSIT",
    "ANNUAL", "FEES",
    "DUITNOW", "QR", "P2P", "CR", "DR",
    "RPP", "INWARD", "INST", "TRF",
    "MBK", "INSTANT",
    "MYDEBIT", "FUND", "MB", "ATM"
]

def split_tokens_glued(text):
    """
    Splits glued text like DUITNOWQRP2PCR -> DUITNOW QR P2P CR
    """
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
            s = s[0+1:]
    
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

    # Add space between letters & digits
    desc = re.sub(r"([A-Za-z])(\d)", r"\1 \2", desc)
    desc = re.sub(r"(\d)([A-Za-z])", r"\1 \2", desc)

    # Normalize spacing
    return " ".join(desc.split())


# ============================================================
# BALANCE-BASED DEBIT/CREDIT LOGIC (CORRECT METHOD)
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    """
    Determines debit/credit based solely on balance movement.
    """
    if prev_balance is None:
        return 0.0, 0.0  # First B/F row

    if curr_balance < prev_balance:
        return prev_balance - curr_balance, 0.0  # Debit

    if curr_balance > prev_balance:
        return 0.0, curr_balance - prev_balance  # Credit

    return 0.0, 0.0  # No change


# ============================================================
# REGEX TO MATCH GLUED RHB TRANSACTION LINES
# ============================================================

PATTERN_RHB = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"         # e.g. 07Mar
    r"(.+?)\s+"                           # description (glued)
    r"(\d{6,12})\s+"                       # serial no.
    r"([0-9,]+\.\d{2})\s+"                 # amount 1 (ignored for debit/credit)
    r"([0-9,]+\.\d{2})$"                   # amount 2 = balance
)


def parse_line_rhb(line, page_num, year=2024):
    """
    Parses ONE glued RHB line and returns intermediate data.
    Final debit/credit will be computed after reading balance.
    """
    m = PATTERN_RHB.match(line)
    if not m:
        return None

    day, month, desc_raw, serial, amt1, amt2 = m.groups()

    date_fmt = f"{year}-{month}-{day}"

    desc_clean = fix_description(desc_raw)

    balance = float(amt2.replace(",", ""))

    return {
        "date": date_fmt,
        "description": desc_clean,
        "serial": serial,
        "raw_amount": float(amt1.replace(",", "")),  # not used for debit/credit
        "balance": balance,
        "page": page_num,
    }


# ============================================================
# FULL TRANSACTION PARSER FOR A PAGE OR MULTIPLE PAGES
# ============================================================

def parse_transactions_rhb(text, page_num, year=2024):
    tx_list = []
    prev_balance = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        tx = parse_line_rhb(line, page_num, year)
        if tx:
            curr_balance = tx["balance"]

            # Compute debit/credit **correctly**
            debit, credit = compute_debit_credit(prev_balance, curr_balance)

            # Replace raw amount logic with correct balance-change logic
            tx["debit"] = debit
            tx["credit"] = credit

            tx_list.append(tx)

            prev_balance = curr_balance  # Update for next row

    return tx_list


# ============================================================
# EXAMPLE USAGE
# ============================================================

sample_text = """
07Mar CDTCASHDEPOSIT 0000004470 1,000.00 1,000.00
08Mar ANNUALFEES 0000004960 12.00 988.00
09Mar DUITNOWQRP2PCRRHBQR000000 0000007440 540.00 1,528.00
09Mar RPPINWARDINSTTRFCR 0000001310 1,280.00 2,808.00
09Mar MBKINSTANTTRFDRKVTJEWELLERSSDN.B 0000000926 2,800.00 8.00
"""

if __name__ == "__main__":
    parsed = parse_transactions_rhb(sample_text, page_num=1)
    for p in parsed:
        print(p)
