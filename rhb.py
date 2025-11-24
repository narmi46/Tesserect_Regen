import regex as re

# ============================================================
# RHB BANK PATTERN
# ============================================================

# RHB sample from your PDF:
# 05-02-2025 061 CLEAR / / AUTODEBIT 00001550 27,286.00 - 770,138.57-
# 25-02-2025 980 CLEAR / 00009992 - 30,000.00 740,138.57-

PATTERN_RHB = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"               # date DD-MM-YYYY
    r"(\d{3})\s+"                           # branch code (e.g. 061)
    r"(.*?)\s+"                             # description (greedy, until DR/CR)
    r"([0-9,]+\.\d{2}|-)\s+"                # Debit or "-"
    r"([0-9,]+\.\d{2}|-)\s+"                # Credit or "-"
    r"([0-9,]+\.\d{2})-"                    # Balance (ends with "-")
)

def parse_line_rhb(line, page_num):
    m = PATTERN_RHB.search(line)
    if not m:
        return None

    date_raw, branch, desc, dr_raw, cr_raw, balance_raw = m.groups()

    # Date convert: dd-mm-yyyy → yyyy-mm-dd
    d, m_, y = date_raw.split("-")
    full_date = f"{y}-{m_}-{d}"

    # Debit / Credit
    debit = float(dr_raw.replace(",", "")) if dr_raw != "-" else 0.0
    credit = float(cr_raw.replace(",", "")) if cr_raw != "-" else 0.0

    # Balance (RHB prints trailing "-")
    balance = float(balance_raw.replace(",", ""))

    description = f"{branch} {desc.strip()}"

    return {
        "date": full_date,
        "description": description,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


def parse_transactions_rhb(text, page_num):
    tx_list = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        tx = parse_line_rhb(line, page_num)
        if tx:
            tx_list.append(tx)

    return tx_list
