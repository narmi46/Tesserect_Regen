import re

IGNORE_PATTERNS = [
    r"^CONTINUE NEXT PAGE",
    r"^You can perform",
    r"^For more information",
    r"^Statement of Account",
    r"^Page / Halaman",
    r"^CIMB BANK",
    r"^\(Protected by",
    r"^Date Description",
    r"^Tarikh Diskripsi",
    r"^\(RM\)",
    r"^Opening Balance",
    r"^Account No",
    r"^Branch / Cawangan",
    r"^Current Account Transaction Details",
    r"^Cheque / Ref No",
    r"^Withdrawal",
    r"^Deposits",
    r"^Balance",
    r"^No of Withdrawal",
    r"^Bil Pengeluaran",
    r"^No of Deposits",
    r"^Bil Deposit",
    r"^Total Withdrawal",
    r"^Jumlah Pengeluaran",
    r"^Total Deposits",
    r"^Jumlah Deposit",
    r"^CLOSING BALANCE",
    r"^End of Statement",
]

def is_ignored(line):
    return any(re.search(p, line) for p in IGNORE_PATTERNS)

# Extract raw row structure only:
# DATE  DESCRIPTION  REFNO  AMOUNT  BALANCE
ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{5,20})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
)

def parse_transactions_cimb(text, page_num, source_file):

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    raw_rows = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if is_ignored(line):
            i += 1
            continue

        m = ROW.match(line)
        if m:
            date, desc, ref_no, amount, balance = m.groups()

            amount_f = float(amount.replace(",", ""))
            balance_f = float(balance.replace(",", ""))

            # Capture multi-line description
            j = i + 1
            extra = []
            while j < len(lines):
                nl = lines[j]

                if ROW.match(nl): break
                if is_ignored(nl): break
                if re.match(r"\d{2}/\d{2}/\d{4}", nl): break

                extra.append(nl)
                j += 1

            full_desc = desc + " " + " ".join(extra)
            full_desc = re.sub(r"\s+", " ", full_desc).strip()

            raw_rows.append({
                "date": date.replace("/", "-"),
                "description": full_desc,
                "ref_no": ref_no,
                "amount": amount_f,
                "balance": balance_f,
                "page": page_num,
                "source_file": source_file
            })

            i = j
            continue

        i += 1

    # ---------------------------------------------------
    # DEBIT / CREDIT CLASSIFICATION (your new rule)
    # ---------------------------------------------------
    final_rows = []

    for idx in range(len(raw_rows)):
        current = raw_rows[idx]

        # get next balance if exists
        if idx < len(raw_rows) - 1:
            next_balance = raw_rows[idx + 1]["balance"]
        else:
            # last row = no change
            next_balance = current["balance"]

        delta = next_balance - current["balance"]

        if delta > 0:
            debit = 0.0
            credit = abs(delta)
        elif delta < 0:
            debit = abs(delta)
            credit = 0.0
        else:
            debit = 0.0
            credit = 0.0

        final_rows.append({
            "date": current["date"],
            "description": current["description"],
            "ref_no": current["ref_no"],
            "debit": debit,
            "credit": credit,
            "balance": current["balance"],
            "page": current["page"],
            "source_file": current["source_file"]
        })

    return final_rows
