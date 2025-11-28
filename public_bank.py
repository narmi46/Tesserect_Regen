import regex as re

PATTERN_PBB = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+
    (?P<desc>.*?)\s+
    (?:
        (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+
    )?
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """,
    re.VERBOSE
)

def parse_line_pbb(line, page_num, default_year="2025"):
    m = PATTERN_PBB.search(line)
    if not m:
        return None

    date_raw = m.group("date")
    desc = m.group("desc").strip()
    amount_raw = m.group("amount")
    balance_raw = m.group("balance")

    # ----- SKIP BALANCE FORWARD LINES -----
    if desc.lower() in ["balance b/f", "balance from last statement"]:
        return None

    # Convert date
    day, month = date_raw.split("/")
    full_date = f"{default_year}-{month}-{day}"

    # Convert numbers
    to_float = lambda v: float(v.replace(",", "")) if v else 0.0
    amount = to_float(amount_raw)
    balance = to_float(balance_raw)

    # ----- CREDIT DETECTION -----
    is_credit = (
        " CR" in desc or
        desc.endswith("CR") or
        "TRSF" in desc or
        "CREDIT" in desc.upper()
    )

    debit = 0.0
    credit = 0.0

    if is_credit:
        credit = amount
    else:
        debit = amount

    return {
        "date": full_date,
        "description": desc,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }

def parse_transactions_pbb(text, page_num, default_year="2025"):
    tx_list = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        tx = parse_line_pbb(line, page_num, default_year)
        if tx:
            tx_list.append(tx)

    return tx_list
