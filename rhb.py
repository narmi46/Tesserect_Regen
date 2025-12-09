import regex as re

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
    return " ".join(desc.split())  # remove double spaces


# ============================================================
# BALANCE → DEBIT / CREDIT LOGIC (NORMAL TX)
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    if prev_balance is None:
        return 0.0, 0.0

    diff = round(curr_balance - prev_balance, 2)

    if diff > 0:
        return 0.0, diff  # credit
    elif diff < 0:
        return abs(diff), 0.0  # debit
    return 0.0, 0.0


# ============================================================
# FIRST TRANSACTION: SCAN METHOD
# ============================================================

def classify_first_tx(desc, amount):
    s = re.sub(r"\s+", "", desc or "").upper()

    if (
        "DEPOSIT" in s or
        "CDT" in s or
        "INWARD" in s or
        s.endswith("CR")
    ):
        return 0.0, amount  # CREDIT

    return amount, 0.0  # DEBIT


# ============================================================
# REGEX PATTERNS — FORMAT A (REAL RHB PDF FORMAT)
# ============================================================

MONTH_MAP = {
    "Jan": "-01-", "Feb": "-02-", "Mar": "-03-",
    "Apr": "-04-", "May": "-05-", "Jun": "-06-",
    "Jul": "-07-", "Aug": "-08-", "Sep": "-09-",
    "Oct": "-10-", "Nov": "-11-", "Dec": "-12-"
}

PATTERN_TX_A = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"       # 07 Mar
    r"(.+?)\s+"                         # description
    r"(\d{6,12})\s+"                    # serial
    r"([0-9,]+\.\d{2})\s+"              # amount
    r"([0-9,]+\.\d{2})$"                # balance
)

PATTERN_BF_CF = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+(B/F BALANCE|C/F BALANCE)\s+([0-9,]+\.\d{2})$"
)


# ============================================================
# REGEX PATTERN — FORMAT B (RARE RHB INTERNET EXPORT)
# ============================================================

PATTERN_TX_B = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"           # 31-03-2024
    r"(\d{3})\s+"                       # branch
    r"(.+?)\s+"                         # description
    r"([0-9,]+\.\d{2}|-)\s+"            # debit
    r"([0-9,]+\.\d{2}|-)\s+"            # credit
    r"([0-9,]+\.\d{2})([+-])"           # balance with +/-
)


# ============================================================
# PARSE SINGLE LINE — TRY FORMAT A FIRST
# ============================================================

def parse_line_rhb(line, page_num, year=2025):

    line = line.strip()
    if not line:
        return None

    # ---------- FORMAT A (REAL PDF FORMAT) ----------
    mA = PATTERN_TX_A.match(line)
    if mA:
        day, mon, desc_raw, serial, amt1, amt2 = mA.groups()
        date_fmt = f"{year}{MONTH_MAP.get(mon, '-01-')}{day.zfill(2)}"

        return {
            "type": "tx",
            "date": date_fmt,
            "description": fix_description(desc_raw),
            "amount_raw": float(amt1.replace(",", "")),
            "balance": float(amt2.replace(",", "")),
            "page": page_num,
        }

    # ---------- B/F or C/F ----------
    mBF = PATTERN_BF_CF.match(line)
    if mBF:
        return {"type": "bf_cf"}

    # ---------- FORMAT B ----------
    mB = PATTERN_TX_B.search(line)
    if mB:
        date_raw, branch, desc, dr_raw, cr_raw, balance_raw, sign = mB.groups()

        # convert date dd-mm-yyyy → yyyy-mm-dd
        dd, mm, yyyy = date_raw.split("-")
        date_fmt = f"{yyyy}-{mm}-{dd}"

        debit = float(dr_raw.replace(",", "")) if dr_raw != "-" else 0.0
        credit = float(cr_raw.replace(",", "")) if cr_raw != "-" else 0.0

        balance = float(balance_raw.replace(",", ""))
        if sign == "-":
            balance = -balance

        description = f"{branch} {desc.strip()}"

        return {
            "type": "tx",
            "date": date_fmt,
            "description": description,
            "amount_raw": debit + credit,
            "balance": balance,
            "page": page_num,
        }

    return None


# ============================================================
# MAIN PARSER
# ============================================================

def parse_transactions_rhb(text, page_num, year=2025):
    global _prev_balance_global

    # NEW STATEMENT → RESET BALANCE
    if page_num == 1:
        _prev_balance_global = None

    tx_list = []

    for raw_line in text.splitlines():
        parsed = parse_line_rhb(raw_line.strip(), page_num, year)
        if not parsed:
            continue

        # Skip B/F and C/F
        if parsed["type"] == "bf_cf":
            continue

        curr_balance = parsed["balance"]
        amount = parsed["amount_raw"]

        # FIRST transaction uses scan method
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
