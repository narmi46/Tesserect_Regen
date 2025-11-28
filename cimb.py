import regex as re

# =========================================================
# CIMB PATTERNS
# =========================================================

# 1. FULL ROW (Date + Description + Ref + Withdrawal/Deposit + Balance)
PATTERN_CIMB_FULL = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2}/\d{4})\s+
    (?P<desc>.+?)\s+
    (?P<ref>[A-Z0-9]+)\s+
    (?P<withdraw>\d{1,3}(?:,\d{3})*\.\d{2}|-)\s+
    (?P<deposit>\d{1,3}(?:,\d{3})*\.\d{2}|-)\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """,
    re.VERBOSE
)

# 2. CONTINUATION LINES (part of description)
PATTERN_CIMB_CONT = re.compile(
    r"^(?!\d{2}/\d{2}/\d{4})(?!Opening Balance)(?!CLOSING)(?!Page)(?P<desc>.+)$"
)

# 3. OPENING / CLOSING BALANCE
PATTERN_CIMB_BALANCE_ONLY = re.compile(
    r"""
    ^(?P<label>Opening Balance|CLOSING BALANCE.*)\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """,
    re.VERBOSE | re.IGNORECASE
)


# =========================================================
# PARSER FUNCTION
# =========================================================
def parse_transactions_cimb(text: str, page_num: int):
    tx_list = []
    buffer_desc = None
    buffer_date = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # ---------------------------------------------------
        # Case A — Opening/Closing balance (ignore as TX)
        # ---------------------------------------------------
        m_bal = PATTERN_CIMB_BALANCE_ONLY.match(line)
        if m_bal:
            buffer_desc = None
            buffer_date = None
            continue

        # ---------------------------------------------------
        # Case B — Main Transaction Row
        # ---------------------------------------------------
        m = PATTERN_CIMB_FULL.match(line)
        if m:
            buffer_date = m.group("date")
            buffer_desc = m.group("desc")

            # numeric conversion
            withdraw_raw = m.group("withdraw")
            deposit_raw = m.group("deposit")

            withdraw = float(withdraw_raw.replace(",", "")) if withdraw_raw != "-" else 0.0
            deposit  = float(deposit_raw.replace(",", "")) if deposit_raw != "-" else 0.0
            balance  = float(m.group("balance").replace(",", ""))

            tx_list.append({
                "date": buffer_date,
                "description": buffer_desc,
                "ref_no": m.group("ref"),
                "debit": withdraw,
                "credit": deposit,
                "balance": balance,
                "page": page_num
            })

            continue

        # ---------------------------------------------------
        # Case C — Continuation lines (part of description)
        # ---------------------------------------------------
        m2 = PATTERN_CIMB_CONT.match(line)
        if m2 and buffer_desc:
            # Append extra description lines (multi-line descriptions)
            tx_list[-1]["description"] += " " + m2.group("desc")
            continue

    return tx_list
