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

    # RHB BALANCE: MUST HANDLE OVERDRAFT
    #
    # balance_raw is always captured WITHOUT the "-"
    # but the actual text has a trailing "-" meaning negative
    #
    # So detect "-" at the end of the original line
    #
    is_negative = line.strip().endswith("-")

    balance = float(balance_raw.replace(",", ""))
    if is_negative:
        balance = -balance

    description = f"{branch} {desc.strip()}"

    return {
        "date": full_date,
        "description": description,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }
