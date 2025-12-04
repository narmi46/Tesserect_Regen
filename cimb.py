import re

# -----------------------------------------------------------
# Utility patterns
# -----------------------------------------------------------

IGNORE_PATTERNS = [
    r"^CONTINUE NEXT PAGE",
    r"^You can perform",
    r"^For more information",
    r"^Statement of Account",
    r"^Page / Halaman",
    r"^CIMB BANK",
    r"^\(Protected by",
    r"^Date",
    r"^Tarikh",
    r"^Description",
    r"^Diskripsi",
    r"^\(RM\)",
    r"^Account No",
    r"^Branch / Cawangan",
    r"^Current Account Transaction Details",
    r"^Cheque / Ref No",
    r"^Withdrawal",
    r"^Deposits",
    r"^Balance",
    r"^No of Withdrawal",
    r"^No of Deposits",
    r"^Total Withdrawal",
    r"^Total Deposits",
    r"^CLOSING BALANCE",
    r"^End of Statement",
    r'^"',  # avoid raw OCR quotes
]

DATE_RE = r"^(\d{2}/\d{2}/\d{4})"
MONEY_RE = r"\d{1,3}(?:,\d{3})*\.\d{2}"


def is_ignored(line):
    return any(re.match(p, line) for p in IGNORE_PATTERNS)


def extract_money(text):
    """Return ONLY proper two-decimal money values."""
    vals = re.findall(MONEY_RE, text)
    return [float(v.replace(",", "")) for v in vals]


def extract_date(text):
    m = re.search(DATE_RE, text)
    if not m:
        return ""
    return m.group(1).replace("/", "-")


def extract_ref_no(text, money_strings):
    temp = text
    for m in money_strings:
        temp = temp.replace(m, "")

    matches = re.findall(r"\b(\d{5,20})\b", temp)
    if not matches:
        return ""
    # choose the longest and rightmost
    return sorted(matches, key=lambda x: (len(x), temp.rfind(x)))[-1]


def clean_description(text, date_str, ref, money_strings):
    d = text
    if date_str:
        d = d.replace(date_str.replace("-", "/"), "")
    if ref:
        d = d.replace(ref, "")
    for m in money_strings:
        d = d.replace(m, "")

    d = re.sub(r"\s+", " ", d).strip()
    return d


# -----------------------------------------------------------
# MAIN FUNCTION (compatible with app.py)
# -----------------------------------------------------------

def parse_transactions_cimb(text, page_num, source_file):
    """
    MUST return ONLY a LIST OF DICTS.
    Fully compatible with your app.py.
    """

    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    lines = [l for l in raw_lines if not is_ignored(l)]

    rows = []
    buffer = ""

    # Step 1: Merge broken lines
    for line in lines:

        if "Opening Balance" in line:
            if buffer:
                rows.append(buffer)
                buffer = ""
            rows.append(line)
            continue

        if re.search(DATE_RE, line):
            if buffer:
                rows.append(buffer)
            buffer = line
        else:
            buffer += " " + line

    if buffer:
        rows.append(buffer)

    # Step 2: Parse rows
    tx_list = []
    prev_balance = None

    for row in rows:

        # Opening balance
        if "Opening Balance" in row:
            money = extract_money(row)
            if not money:
                continue

            bal = money[-1]
            prev_balance = bal

            tx_list.append({
                "date": "",
                "description": "OPENING BALANCE",
                "ref_no": "",
                "debit": 0.0,
                "credit": 0.0,
                "balance": bal,
                "page": page_num,
                "source_file": source_file,
            })
            continue

        money_strings = re.findall(MONEY_RE, row)
        if len(money_strings) < 2:
            continue

        money_vals = [float(m.replace(",", "")) for m in money_strings]
        amount = money_vals[-2]
        balance = money_vals[-1]

        date_str = extract_date(row)
        ref_no = extract_ref_no(row, money_strings)
        description = clean_description(row, date_str, ref_no, money_strings)

        # Debit vs Credit decision
        debit = credit = 0.0

        if prev_balance is not None:
            if abs(prev_balance - amount - balance) < 0.01:
                debit = amount
            elif abs(prev_balance + amount - balance) < 0.01:
                credit = amount
            else:
                # fallback logic
                upper = description.upper()
                if "TR TO" in upper or "DUITNOW TO" in upper or "JOMPAY" in upper:
                    debit = amount
                else:
                    credit = amount
        else:
            # First page
            if "TR TO" in description.upper():
                debit = amount
            else:
                credit = amount

        prev_balance = balance

        tx_list.append({
            "date": date_str,
            "description": description,
            "ref_no": ref_no,
            "debit": round(debit, 2),
            "credit": round(credit, 2),
            "balance": round(balance, 2),
            "page": page_num,
            "source_file": source_file,
        })

    return tx_list
