# bank_islam.py
import re

def clean_amount(value):
    if not value or value == "-":
        return 0.0
    return float(value.replace(",", ""))


def parse_bank_islam(pdf):
    """
    Parses Bank Islam statement using pdfplumber table extraction.
    Much more accurate than text regex.
    """
    transactions = []

    for page in pdf.pages:
        tables = page.extract_tables()

        if not tables:
            continue

        # Bank Islam tables usually contain headers like:
        # "Transaction Date", "Customer/EFT No", "Transaction Code", ...
        for table in tables:
            # Skip header row, find the actual data rows
            if not table or len(table) < 2:
                continue

            header = table[0]

            # Expected useful columns by index:
            # [0]=No.
            # [1]=Transaction Date
            # [2]=Customer/EFT No
            # [3]=Transaction Code
            # [4]=Description
            # [5]=Ref/Cheque No
            # [6]=Servicing Branch
            # [7]=Debit Amount
            # [8]=Credit Amount
            # [9]=Balance

            for row in table[1:]:
                if len(row) < 10:
                    continue

                (
                    no,
                    date_raw,
                    eft_no,
                    code,
                    desc,
                    ref_no,
                    branch,
                    debit_raw,
                    credit_raw,
                    balance_raw
                ) = row[:10]

                # Skip totals row
                if "Total" in str(no):
                    continue

                # Clean values
                description = " ".join(str(desc).split())
                debit = clean_amount(debit_raw)
                credit = clean_amount(credit_raw)
                balance = clean_amount(balance_raw)

                # Normalize date: 13/03/2025 → 2025-03-13
                if date_raw and re.match(r"\d{2}/\d{2}/\d{4}", date_raw):
                    dd, mm, yyyy = date_raw.split("/")
                    date_fmt = f"{yyyy}-{mm}-{dd}"
                else:
                    date_fmt = date_raw

                transactions.append({
                    "date": date_fmt,
                    "description": description,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                })

    return transactions
