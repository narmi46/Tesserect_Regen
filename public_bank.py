import regex as re

# ============================================================
# PUBLIC BANK (PBB) - ROBUST TRANSACTION PARSER
# Supports:
#   ✓ Debit only
#   ✓ Credit only
#   ✓ Debit + Credit
#   ✓ Description with numbers
#   ✓ Variable spacing from PDF extraction
# ============================================================

PATTERN_PBB = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+                               # date
    (?P<desc>.*?)\s+                                        # description
    (?:
        (?P<debit>\d{1,3}(?:,\d{3})*\.\d{2})\s+             # debit (optional)
    )?
    (?:
        (?P<credit>\d{1,3}(?:,\d{3})*\.\d{2})\s+            # credit (optional)
    )?
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$                 # balance (required)
    """,
    re.VERBOSE
)


def parse_line_pbb(line, page_num, default_year="2025"):
    """
    Parse a single PBB transaction line.
    """

    m = PATTERN_PBB.search(line)
    if not m:
        return None

    date_raw = m.group("date")
    desc = m.group("desc").strip()
    debit_raw = m.group("debit")
    credit_raw = m.group("credit")
    balance_raw = m.group("balance")

    # Convert date
    day, month = date_raw.split("/")
    full_date = f"{default_year}-{month}-{day}"

    # Convert numbers
    def to_float(v):
        return float(v.replace(",", "")) if v else 0.0

    debit = to_float(debit_raw)
    credit = to_float(credit_raw)
    balance = to_float(balance_raw)

    return {
        "date": full_date,
        "description": desc,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


def parse_transactions_pbb(text, page_num, default_year="2025"):
    """
    Parse multiple lines on a single PDF page.
    """

    tx_list = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        tx = parse_line_pbb(line, page_num, default_year)
        if tx:
            tx_list.append(tx)

    return tx_list


# ============================================================
# Example usage:
# ============================================================
if __name__ == "__main__":

    sample_text = """
    02/05 DEP-ECP 125453        1,411.99       2,780.16
    05/05 DEP-ECP 173743        1,418.32       5,234.14
    17/05 DUITNOW TRSF CR 213251 MAZAA SDN BHD        1,000.00   6,384.56
    """

    results = parse_transactions_pbb(sample_text, page_num=1)
    for r in results:
        print(r)
