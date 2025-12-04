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

# Detect ANY numeric group on a line
NUMBER = r"([\d,]+\.\d{2})"

def parse_transactions_cimb(text, page_num, source_file):

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    cleaned = []
    buffer = ""

    # ----------------------------------------------
    # 1️⃣ MERGE SPLIT LINES INTO COMPLETE ROW BLOCKS
    # ----------------------------------------------
    for line in lines:

        if is_ignored(line):
            continue

        # Start of new transaction
        if re.match(r"\d{2}/\d{2}/\d{4}", line):
            if buffer:
                cleaned.append(buffer.strip())
            buffer = line
        else:
            buffer += " " + line

    if buffer:
        cleaned.append(buffer.strip())

    # Now "cleaned" contains FULL reconstructed rows

    final = []
    i = 0

    # ----------------------------------------------
    # 2️⃣ EXTRACT COLUMNS SAFELY
    # ----------------------------------------------
    for row in cleaned:

        # Find ALL numeric values in the row
        nums = re.findall(NUMBER, row)

        if len(nums) < 2:
            # Cannot be a valid row
            continue

        amount = float(nums[-2].replace(",", ""))
        balance = float(nums[-1].replace(",", ""))

        # Extract REFNO (middle digits)
        refno_match = re.search(r"(\d{5,20})", row)
        if not refno_match:
            continue

        ref_no = refno_match.group(1)

        # Extract date
        date_match = re.match(r"(\d{2}/\d{2}/\d{4})", row)
        if not date_match:
            continue

        date = date_match.group(1).replace("/", "-")

        # Extract description = everything between date and refno
        temp = row.replace(date_match.group(1), "")
        temp = temp.replace(ref_no, "")
        # Remove numbers we know
        temp = temp.replace(nums[-1], "").replace(nums[-2], "")

        description = " ".join(temp.split()).strip()

        final.append({
            "date": date,
            "description": description,
            "ref_no": ref_no,
            "amount": amount,
            "balance": balance,
            "page": page_num,
            "source_file": source_file
        })

    return final
