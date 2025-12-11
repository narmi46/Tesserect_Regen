import regex as re

# ============================================================
# MONTH MAP
# ============================================================

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03",
    "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09",
    "Oct": "10", "Nov": "11", "Dec": "12"
}

# ============================================================
# INTERNAL STATE (PERSISTS ACROSS PAGES)
# ============================================================

_prev_balance_global = None

# ============================================================
# SIMPLE DESCRIPTION CLEANER
# ============================================================

def fix_description(desc):
    if not desc:
        return desc
    return " ".join(desc.split())


# ============================================================
# BALANCE → DEBIT / CREDIT LOGIC
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    if prev_balance is None:
        return 0.0, 0.0

    diff = round(curr_balance - prev_balance, 2)

    if diff > 0:
        return 0.0, diff   # credit
    elif diff < 0:
        return abs(diff), 0.0   # debit
    return 0.0, 0.0


# ============================================================
# FIRST TRANSACTION SCAN METHOD
# ============================================================

def classify_first_tx(desc, amount):
    s = re.sub(r"\s+", "", desc or "").upper()
    if (
        "DEPOSIT" in s or
        "CDT" in s or
        "INWARD" in s or
        s.endswith("CR")
    ):
        return 0.0, amount
    return amount, 0.0


# ============================================================
# HELPERS FOR BALANCE-ONLY LINES (OPENING/CLOSING/BF/CF)
# ============================================================

BALANCE_KEYWORDS = [
    "OPENING BALANCE",
    "CLOSING BALANCE",
    "B/F BALANCE",
    "C/F BALANCE",
    "BAL B/F",
    "BAL B/F.",
    "BAL C/F",
    "BAL C/F.",
    "BALANCE B/F",
    "BALANCE C/F",
]

def is_balance_description(desc: str) -> bool:
    if not desc:
        return False
    s = desc.upper()
    return any(k in s for k in BALANCE_KEYWORDS)


# ============================================================
# REGEX PATTERNS FOR ALL RHB FORMATS
# ============================================================

# -------- FORMAT A (Old RHB PDF: 3 March 2024) --------
PATTERN_TX_A = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"
    r"(.+?)\s+"
    r"(\d{4,20})\s+"
    r"([0-9,]+\.\d{2})\s+"
    r"([0-9,]+\.\d{2})"
)

# -------- B/F & C/F BALANCE LINE (plain) --------
PATTERN_BF_CF = re.compile(
    r"^(\d{1,2}[A-Za-z]{3})\s+"
    r"(B/F BALANCE|C/F BALANCE)\s+"
    r"([0-9,]+\.\d{2})"
    r"(?:\s*(CR|DR))?$"
)

# -------- FORMAT B (Internet banking after export) --------
PATTERN_TX_B = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"
    r"(\d{3})\s+"
    r"(.+?)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2})([+-])"
)

# -------- FORMAT C (New Islamic PDF: Jan 2025) --------
PATTERN_TX_C = re.compile(
    r"^(\d{1,2})\s+([A-Za-z]{3})\s+"
    r"(.+?)\s+"
    r"(\d{4,20})\s+"
    r"([0-9,]+\.\d{2})\s+"
    r"([0-9,]+\.\d{2})"
)


# ============================================================
# PARSE A SINGLE LINE (ORDER: BF_CF → C → A → B)
# ============================================================

def parse_line_rhb(line, page_num, year=2025):
    line = line.strip()
    if not line:
        return None

    # -------- 1) PLAIN B/F or C/F BALANCE LINES --------
    m_bf = PATTERN_BF_CF.match(line)
    if m_bf:
        date_raw, bf_type, bal_raw, cr_dr = m_bf.groups()
        day = date_raw[:-3]
        mon = date_raw[-3:]
        date_fmt = f"{year}-{MONTH_MAP.get(mon, '01')}-{day.zfill(2)}"

        bal = float(bal_raw.replace(",", ""))
        if cr_dr == "DR":
            bal = -bal

        return {
            "type": "bf_cf",
            "date": date_fmt,
            "balance": bal,
            "bf_type": bf_type,
            "page": page_num,
        }

    # -------- 2) FORMAT C (New Islamic PDF) --------
    mC = PATTERN_TX_C.match(line)
    if mC:
        day, mon, desc, serial, amt1, amt2 = mC.groups()
        desc_clean = fix_description(desc)
        date_fmt = f"{year}-{MONTH_MAP.get(mon, '01')}-{day.zfill(2)}"
        bal = float(amt2.replace(",", ""))

        # If description is an opening/closing/BF/CF balance, treat as balance row only
        if is_balance_description(desc_clean):
            return {
                "type": "bf_cf",
                "date": date_fmt,
                "balance": bal,
                "bf_type": desc_clean,
                "page": page_num,
            }

        return {
            "type": "tx",
            "date": date_fmt,
            "description": desc_clean,
            "amount_raw": float(amt1.replace(",", "")),
            "balance": bal,
            "page": page_num,
        }

    # -------- 3) FORMAT A (Old PDF) --------
    mA = PATTERN_TX_A.match(line)
    if mA:
        day, mon, desc, serial, amt1, amt2 = mA.groups()
        desc_clean = fix_description(desc)
        date_fmt = f"{year}-{MONTH_MAP.get(mon, '01')}-{day.zfill(2)}"
        bal = float(amt2.replace(",", ""))

        if is_balance_description(desc_clean):
            return {
                "type": "bf_cf",
                "date": date_fmt,
                "balance": bal,
                "bf_type": desc_clean,
                "page": page_num,
            }

        return {
            "type": "tx",
            "date": date_fmt,
            "description": desc_clean,
            "amount_raw": float(amt1.replace(",", "")),
            "balance": bal,
            "page": page_num,
        }

    # -------- 4) FORMAT B (Online Export) --------
    mB = PATTERN_TX_B.match(line)  # IMPORTANT: match(), not search()
    if mB:
        date_raw, branch, desc, dr_raw, cr_raw, bal_raw, sign = mB.groups()
        dd, mm, yyyy = date_raw.split("-")
        date_fmt = f"{yyyy}-{mm}-{dd}"

        desc_clean = fix_description(desc)
        bal = float(bal_raw.replace(",", ""))
        if sign == "-":
            bal = -bal

        # Handle "OPENING BALANCE" / "CLOSING BALANCE" in Internet export
        if is_balance_description(desc_clean):
            return {
                "type": "bf_cf",
                "date": date_fmt,
                "balance": bal,
                "bf_type": desc_clean,
                "page": page_num,
            }

        debit = float(dr_raw.replace(",", "")) if dr_raw != "-" else 0.0
        credit = float(cr_raw.replace(",", "")) if cr_raw != "-" else 0.0

        return {
            "type": "tx",
            "date": date_fmt,
            "description": f"{branch} {desc_clean}",
            "amount_raw": debit + credit,
            "balance": bal,
            "page": page_num,
        }

    return None


# ============================================================
# MAIN PARSER
# ============================================================

def parse_transactions_rhb(text, page_num, year=2025):
    global _prev_balance_global

    # Reset when starting a new statement
    if page_num == 1:
        _prev_balance_global = None

    tx_list = []

    for raw_line in text.splitlines():
        parsed = parse_line_rhb(raw_line, page_num, year)
        if not parsed:
            continue

        # -------- Handle OPENING/CLOSING/BF/CF (balance-only) --------
        if parsed["type"] == "bf_cf":
            # Seed or sync the running balance
            _prev_balance_global = parsed["balance"]
            # IMPORTANT: we DO NOT add this as a transaction row
            continue

        # -------- Handle REAL transactions only --------
        curr_balance = parsed["balance"]
        amount = parsed["amount_raw"]

        # First TX of statement (no previous balance captured yet)
        if _prev_balance_global is None:
            debit, credit = classify_first_tx(parsed["description"], amount)
        else:
            debit, credit = compute_debit_credit(_prev_balance_global, curr_balance)

        tx_list.append({
            "date": parsed["date"],
            "description": parsed["description"],
            "debit": debit,
            "credit": credit,
            "balance": curr_balance,
            "page": page_num,
        })

        _prev_balance_global = curr_balance

    return tx_list
