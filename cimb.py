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
    vals = re.findall(MONEY_RE, text)
    return [float(v.replace(",", "")) for v in vals]


def extract_date(text):
    m = re.search(DATE_RE, text)
    return m.group(1).replace("/", "-") if m else ""


def extract_ref_no(text, money_strings):
    temp = text
    for m in money_strings:
        temp = temp.replace(m, "")

    matches = re.findall(r"\b(\d{5,20})\b", temp)
    if not matches:
        return ""
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
# FIXED MAIN FUNCTION
# -----------------------------------------------------------

def parse_transactions_cimb(text, page_num, source_file):

    # remove garbage lines
    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    lines = [l for l in raw_lines if not is_ignored(l)]

    rows = []
    buffer = ""

    # -----------------------------------------------------------
    # ✔ FIX 1: improved merging logic
    # -----------------------------------------------------------
    for line in lines:

        has_date = bool(re.search(DATE_RE, line))
        has_money = bool(re.search(MONEY_RE, line))

        # new transaction begins
        if has_date:
            if buffer:
                rows.append(buffer)
            buffer = line

        else:
            # continuation line: always append
            buffer += " " + line

        # ✔ FIX 2: if buffer now has ≥2 money amounts → complete row
        if len(re.findall(MONEY_RE, buffer)) >= 2 and has_date is False:
            rows.append(buffer)
            buffer = ""

    if buffer:
        rows.append(buffer)

    # -----------------------------------------------------------
    # Parse rows into structured data
    # -----------------------------------------------------------

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

        # ✔ FIX 3: allow rows with only 1 money value (e.g. JOMPAY partial OCR)
        money_strings = re.findall(MONEY_RE, row)
        if len(money_strings) < 1:
            continue

        money_vals = [float(m.replace(",", "")) for m in money_strings]

        # ✔ FIX 4: if only one money value, treat it as amount
        if len(money_vals) == 1:
            amount = money_vals[0]
            balance = prev_balance - amount  # fallback guess
        else:
            amount = money_vals[-2]
            balance = money_vals[-1]

        date_str = extract_date(row)
        ref_no = extract_ref_no(row, money_strings)
        description = clean_description(row, date_str, ref_no, money_strings)

        # -----------------------------------------------------------
        # ✔ FIX 5: more reliable debit/credit direction logic
        # -----------------------------------------------------------
        debit = credit = 0.0

        if prev_balance is not None and len(money_vals) >= 2:
            if abs(prev_balance - amount - balance) < 0.02:
                debit = amount
            elif abs(prev_balance + amount - balance) < 0.02:
                credit = amount
            else:
                # fallback by keywords
                upper = description.upper()
                if "TR TO" in upper or "DUITNOW TO" in upper or "JOMPAY" in upper:
                    debit = amount
                else:
                    credit = amount
        else:
            # first page fallback
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
