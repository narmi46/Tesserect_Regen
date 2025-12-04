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


# Recognize basic CIMB row:
# DATE  DESCRIPTION  REFNO  AMOUNT  BALANCE
BASIC_ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{6,20})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
)

def parse_transactions_cimb(text, page_num, source_file):

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    tx_list = []

    previous_balance = None
    i = 0

    while i < len(lines):

        line = lines[i]

        # Skip non-transaction rows
        if is_ignored(line):
            i += 1
            continue

        m = BASIC_ROW.match(line)
        if m:
            date, desc, ref_no, amount, balance = m.groups()

            amount_f = float(amount.replace(",", ""))
            balance_f = float(balance.replace(",", ""))

            # Determine debit/credit using balance direction
            # If balance goes UP from previous balance → CREDIT
            # If balance goes DOWN → DEBIT

            if previous_balance is None:
                # First transaction on the page: infer from context
                # Typically CIMB lists newest → oldest OR oldest → newest
                debit = amount_f
                credit = 0.0
            else:
                if balance_f > previous_balance:
                    credit = amount_f
                    debit = 0.0
                else:
                    debit = amount_f
                    credit = 0.0

            previous_balance = balance_f

            # Attach multiline description if exists
            j = i + 1
            extra_desc = []

            while j < len(lines):
                nl = lines[j]

                if BASIC_ROW.match(nl):
                    break
                if is_ignored(nl):
                    break
                if re.match(r"\d{2}/\d{2}/\d{4}", nl):
                    break

                extra_desc.append(nl.strip())
                j += 1

            full_desc = desc + " " + " ".join(extra_desc)
            full_desc = re.sub(r"\s+", " ", full_desc).strip()

            tx_list.append({
                "date": date.replace("/", "-"),
                "description": full_desc,
                "ref_no": ref_no,
                "debit": debit,
                "credit": credit,
                "balance": balance_f,
                "page": page_num,
                "source_file": source_file
            })

            i = j
            continue

        i += 1

    return tx_list
