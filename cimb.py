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
    r"^Branch",
    r"^Current Account Transaction Details",
    r"^Cheque",
    r"^Withdrawal",
    r"^Deposits",
    r"^Balance",
    r"^No of Withdrawal",
    r"^No of Deposits",
    r"^Total Withdrawal",
    r"^Total Deposits",
    r"^CLOSING BALANCE",
    r"^End of Statement",
    r'^"',  # avoid stray OCR text
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
# MAIN FIXED FUNCTION
# -----------------------------------------------------------

def parse_transactions_cimb(text, page_num, source_file):

    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    lines = [l for l in raw_lines if not is_ignored(l)]

    rows = []
    buffer = ""

    # -----------------------------------------------------------
    # FIXED MERGING LOGIC – robust CIMB style
    # -----------------------------------------------------------
    for line in lines:

        has_date = bool(re.search(DATE_RE, line))
        has_money = bool(re.search(MONEY_RE, line))

        if has_date:
            if buffer:
                rows.append(buffer)
            buffer = line
        else:
            buffer += " " + line

        # transaction row complete once 2 money values appear
        if len(re.findall(MONEY_RE, buffer)) >= 2 and not has_date:
            rows.append(buffer)
            buffer = ""

    if buffer:
        rows.append(buffer)

    # -----------------------------------------------------------
    # Parse rows into transaction objects
    # -----------------------------------------------------------

    tx_list = []
    prev_balance = None

    for row in rows:

        # Opening Balance
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

        # Extract money values
        money_strings = re.findall(MONEY_RE, row)
        money_vals = [float(m.replace(",", "")) for m in money_strings]

        if len(money_vals) < 1:
            continue

        # If exactly 2 → amount and balance
        if len(money_vals) >= 2:
            amount = money_vals[-2]
            balance = money_vals[-1]
        else:
            # fallback for single value cases (rare)
            amount = money_vals[0]
            balance = prev_balance  # temp until next row fixes it

        date_str = extract_date(row)
        ref = extract_ref_no(row, money_strings)
        description = clean_description(row, date_str, ref, money_strings)

        # -----------------------------------------------------------
        # FIXED DEBIT/CREDIT LOGIC (BANK LOGIC)
        # -----------------------------------------------------------

        withdrawal = 0.0
        deposit = 0.0

        if prev_balance is not None:

            # withdrawal → decreases balance
            if abs(prev_balance - amount - balance) < 0.02:
                withdrawal = amount

            # deposit → increases balance
            elif abs(prev_balance + amount - balance) < 0.02:
                deposit = amount

            else:
                # fallback based on keywords
                upper = description.upper()

                if ("TR TO " in upper) or ("DUITNOW TO" in upper) or ("JOMPAY" in upper):
                    withdrawal = amount
                else:
                    deposit = amount

        else:
            # should not happen after opening balance
            deposit = amount

        prev_balance = balance

        tx_list.append({
            "date": date_str,
            "description": description,
            "ref_no": ref,
            "debit": round(withdrawal, 2),
            "credit": round(deposit, 2),
            "balance": round(balance, 2),
            "page": page_num,
            "source_file": source_file,
        })

    return tx_list
