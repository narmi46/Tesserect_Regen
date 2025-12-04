import re
import pdfplumber

def parse_transactions_cimb(text, page_num, source_file):

    # 1. Split into lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    tx_list = []

    # Pattern for: Date Description Ref Debit Credit Balance
    row_regex = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{6,20})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
    )

    # Pattern for rows with only: Date Description Ref Amount Balance
    collapsed_regex = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{6,20})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
    )

    i = 0
    while i < len(lines):
        line = lines[i]

        m = row_regex.match(line) or collapsed_regex.match(line)
        if m:
            date, desc, refno, amt1, amt2 = m.groups()

            amount1 = float(amt1.replace(",", ""))
            amount2 = float(amt2.replace(",", ""))

            # Decide debit/credit:
            if amount1 > amount2:
                debit = amount1
                credit = 0.0
                balance = amount2
            else:
                debit = 0.0
                credit = amount1
                balance = amount2

            # Capture multi-line description
            j = i + 1
            desc_extra = []
            while j < len(lines) and not re.match(r"\d{2}/\d{2}/\d{4}", lines[j]):
                desc_extra.append(lines[j])
                j += 1

            full_desc = desc + " " + " ".join(desc_extra)
            full_desc = re.sub(r"\s+", " ", full_desc).strip()

            tx_list.append({
                "date": date.replace("/", "-"),
                "description": full_desc,
                "ref_no": refno,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num,
                "source_file": source_file
            })

            i = j
            continue

        i += 1

    return tx_list
