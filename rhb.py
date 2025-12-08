import regex as re

# ============================================================
# RHB STATEMENT PARSER — COMBINED VERSION
# Supports:
# 1) New no-space format (your Colab logic)
# 2) Old structured format (regex pattern_rhb)
# Auto-detects best parser.
# ============================================================

# ------------------------------
# OLD REGEX PATTERN PARSER
# ------------------------------

PATTERN_RHB = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"                       # date
    r"(\d{3})\s+"                                   # branch
    r"(.+?)\s+"                                     # description
    r"([0-9,]+\.\d{2}|-)\s+"                        # debit
    r"([0-9,]+\.\d{2}|-)\s+"                        # credit
    r"([0-9,]+\.\d{2})([+-])"                       # balance + sign
)

def parse_line_rhb_regex(line, page_num, source_file):
    m = PATTERN_RHB.search(line)
    if not m:
        return None

    date_raw, branch, desc, dr_raw, cr_raw, balance_raw, sign = m.groups()

    # Convert DD-MM-YYYY → YYYY-MM-DD
    d, m_, y = date_raw.split("-")
    full_date = f"{y}-{m_}-{d}"

    debit = float(dr_raw.replace(",", "")) if dr_raw != "-" else 0.0
    credit = float(cr_raw.replace(",", "")) if cr_raw != "-" else 0.0

    balance = float(balance_raw.replace(",", ""))
    if sign == "-":
        balance = -balance

    description = f"{branch} {desc.strip()}"

    return {
        "date": full_date,
        "description": description,
        "serial_no": "",
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "beneficiary": "",
        "page": page_num,
        "source_file": source_file,
    }


def parse_transactions_rhb_regex(text, page_num, source_file):
    tx_list = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        tx = parse_line_rhb_regex(line, page_num, source_file)
        if tx:
            tx_list.append(tx)

    return tx_list


# ------------------------------
# NEW NO-SPACE FORMAT PARSER (from Colab Option A)
# ------------------------------

DATE_PATTERN = re.compile(r"^(\d{1,2})([A-Za-z]{3})\s+(.*)$")


def parse_transactions_rhb_v2(text, page_num, source_file):
    tx_list = []
    lines = text.split("\n")

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        m = DATE_PATTERN.match(line)
        if not m:
            continue

        day, month, rest = m.groups()
        date_std = f"{day}-{month}"

        parts = rest.split()
        if len(parts) < 2:
            continue

        # Serial no detection
        serial_no = ""
        serial_index = -1
        for idx, token in enumerate(parts):
            if token.isdigit() and len(token) == 10:
                serial_no = token
                serial_index = idx
                break

        # Opening/closing balances (no serial)
        if serial_index == -1:
            desc = " ".join(parts[:-1]).strip()
            bal = parts[-1].replace(",", "")

            if bal.replace(".", "", 1).isdigit():
                balance = float(bal)
            else:
                balance = 0.0

            tx_list.append({
                "date": date_std,
                "description": desc,
                "serial_no": "",
                "debit": 0.0,
                "credit": 0.0,
                "balance": balance,
                "beneficiary": "",
                "page": page_num,
                "source_file": source_file
            })
            continue

        # Description
        description = " ".join(parts[:serial_index]).strip()

        # Amount + balance
        bal = parts[-1].replace(",", "")
        amount_part = parts[serial_index + 1:-1]

        debit = credit = 0.0
        if amount_part:
            amt = amount_part[0].replace(",", "")
            if "CR" in description.upper() or "DEPOSIT" in description.upper():
                credit = float(amt)
            else:
                debit = float(amt)

        balance = float(bal) if bal.replace(".", "", 1).isdigit() else 0.0

        # beneficiary lines (2 lines max)
        bene_lines = []
        for j in range(i + 1, min(i + 6, len(lines))):
            nxt = lines[j].strip()
            if not nxt:
                break
            if DATE_PATTERN.match(nxt):
                break
            if re.match(r"^[A-Z0-9]{12,}$", nxt):
                continue
            if nxt in ("QRPayment", "FundTransfer", "DuitQRP2PTransfer", "pay"):
                continue
            bene_lines.append(nxt)

        beneficiary = " | ".join(bene_lines[:2])

        tx_list.append({
            "date": date_std,
            "description": description,
            "serial_no": serial_no,
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "beneficiary": beneficiary,
            "page": page_num,
            "source_file": source_file
        })

    return tx_list


# ------------------------------
# MASTER DISPATCHER
# ------------------------------

def parse_transactions_rhb(text, page_num, source_file="RHB Statement"):
    """
    Main public function.
    Tries new 'no-space' parser first.
    If 0 results → falls back to old regex parser.
    """

    # Try new parser first
    tx_v2 = parse_transactions_rhb_v2(text, page_num, source_file)
    if tx_v2:
        return tx_v2

    # Otherwise fallback
    tx_regex = parse_transactions_rhb_regex(text, page_num, source_file)
    return tx_regex
