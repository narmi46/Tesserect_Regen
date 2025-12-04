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


ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{5,20})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
)

def parse_transactions_cimb(text, page_num, source_file):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # Extract raw rows first (no debit/credit yet)
    raw = []
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

            # Capture multi-line descriptions
            j = i + 1
            extra_desc = []
            while j < len(lines):
                nl = lines[j]
                if ROW.match(nl):
                    break
                if is_ignored(nl):
                    break
                if re.match(r"\d{2}/\d{2}/\d{4}", nl):
                    break

                extra_desc.append(nl)
                j += 1

            full_desc = desc + " " + " ".join(extra_desc)
            full_desc = re.sub(r"\s+", " ", full_desc).strip()

            raw.append({
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

    # NOW assign debit/credit using NEXT balance
    for idx in range(len(raw)):
        current = raw[idx]

        if idx < len(raw) - 1:
            next_balance = raw[idx + 1]["balance"]
        else:
            # Last transaction on statement:
            next_balance = current["balance"]  # no movement
       
        delta = next_balance - current["balance"]
        
        if abs(delta - current["amount"]) < 0.01:
            current["debit"] = 0.0
            current["credit"] = current["amount"]
        elif abs(delta + current["amount"]) < 0.01:
            current["debit"] = current["amount"]
            current["credit"] = 0.0
        else:
            # Fallback (rare cases)
            if current["amount"] > 0:
                current["credit"] = current["amount"]
                current["debit"] = 0.0
            else:
                current["debit"] = abs(current["amount"])
                current["credit"] = 0.0

        del current["amount"]  # not needed anymore

    return raw
