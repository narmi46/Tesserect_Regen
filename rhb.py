import regex as re

# ============================================================
# RHB STATEMENT PARSER FOR GLUED-TEXT FORMAT (07MarCDTCASH...)
# Extracts ONLY the first description line (no multiline merge)
# ============================================================

# Known tokens used to split glued descriptions
KNOWN_TOKENS = [
    "CDT", "CASH", "DEPOSIT",
    "ANNUAL", "FEES",
    "DUITNOW", "QR", "P2P", "CR", "DR",
    "RPP", "INWARD", "INST", "TRF",
    "MBK", "INSTANT",
    "MYDEBIT"
]

def split_tokens_glued(text):
    """
    Splits glued text like DUITNOWQRP2PCR into tokens:
    → DUITNOW QR P2P CR
    """
    s = text
    result = []
    
    while s:
        matched = False
        # match longest token first
        for tok in sorted(KNOWN_TOKENS, key=len, reverse=True):
            if s.startswith(tok):
                result.append(tok)
                s = s[len(tok):]
                matched = True
                break
        if not matched:
            # add raw characters if unknown pattern
            result.append(s[0])
            s = s[1:]

    # reassemble into readable form
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

    # Token split
    desc = split_tokens_glued(desc)

    # Add spacing between letters & digits
    desc = re.sub(r"([A-Za-z])(\d)", r"\1 \2", desc)
    desc = re.sub(r"(\d)([A-Za-z])", r"\1 \2", desc)

    # Normalize spaces
    return " ".join(desc.split())


# ============================================================
# MAIN PARSER
# ============================================================

# Example line format (glued):
# 07Mar CDTCASHDEPOSIT 0000004470 1,000.00 1,000.00
PATTERN_RHB = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"               # date: 07Mar
    r"(.+?)\s+"                                 # description + serial + amounts
    r"(\d{6,12})\s+"                             # serial (6–12 digits)
    r"([0-9,]+\.\d{2})\s+"                       # amount 1
    r"([0-9,]+\.\d{2})$"                         # amount 2
)

def parse_line_rhb(line, page_num):
    m = PATTERN_RHB.match(line)
    if not m:
        return None

    day, month, desc_raw, serial, amt1, amt2 = m.groups()

    date_fmt = f"2025-{month}-{day}"  # You can adjust the year dynamically if needed

    desc_clean = fix_description(desc_raw)

    # Determine debit/credit automatically:
    # Rule:
    # - If amount1 > amount2 → debit
    # - If amount2 > amount1 → credit
    # - Bank statements usually follow this format
    a1 = float(amt1.replace(",", ""))
    a2 = float(amt2.replace(",", ""))

    debit = 0.0
    credit = 0.0

    if a1 > a2:
        debit = a1
        balance = a2
    else:
        credit = a1
        balance = a2

    return {
        "date": date_fmt,
        "description": desc_clean,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


def parse_transactions_rhb(text, page_num):
    tx_list = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        tx = parse_line_rhb(line, page_num)
        if tx:
            tx_list.append(tx)

    return tx_list
