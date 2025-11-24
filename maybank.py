import regex as re

# --------------------------------------
# MTASB PATTERN
# Example: "01/05 TRANSFER TO A/C 320.00+ 43,906.52"
# --------------------------------------

PATTERN_MTASB = re.compile(
    r"(\d{2}/\d{2})\s+"
    r"(.+?)\s+"
    r"([0-9,]+\.\d{2})([+-])\s+"
    r"([0-9,]+\.\d{2})"
)


def parse_line_mtasb(line, page_num, default_year="2025"):
    m = PATTERN_MTASB.search(line)
    if not m:
        return None

    date_raw, desc, amount_raw, sign, balance_raw = m.groups()
    day, month = date_raw.split("/")
    year = default_year

    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    credit = amount if sign == "+" else 0.0
    debit = amount if sign == "-" else 0.0

    full_date = f"{year}-{month}-{day}"

    return {
        "date": full_date,
        "description": desc,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


def parse_transactions_mtasb(text, page_num, default_year="2025"):
    tx_list = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        tx = parse_line_mtasb(line, page_num, default_year)
        if tx:
            tx_list.append(tx)

    return tx_list


# --------------------------------------
# MAYBANK (MBB) PATTERN
# Example: "01 Apr 2025 CMS - DR CORP CHG 78.00 - 71,229.76"
# --------------------------------------

PATTERN_MBB = re.compile(
    r"(\d{2})\s+([A-Za-z]{3})\s+(\d{4})\s+"
    r"(.+?)\s+"
    r"([0-9,]+\.\d{2})\s+([+-])\s+"
    r"([0-9,]+\.\d{2})"
)

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def parse_line_mbb(line, page_num):
    m = PATTERN_MBB.search(line)
    if not m:
        return None

    day, mon, year, desc, amount_raw, sign, balance_raw = m.groups()

    month = MONTH_MAP.get(mon.title(), "01")
    amount = float(amount_raw.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    credit = amount if sign == "+" else 0.0
    debit = amount if sign == "-" else 0.0

    full_date = f"{year}-{month}-{day}"

    return {
        "date": full_date,
        "description": desc,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


def parse_transactions_mbb(text, page_num):
    tx_list = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        tx = parse_line_mbb(line, page_num)
        if tx:
            tx_list.append(tx)

    return tx_list
