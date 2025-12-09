# bank_islam.py
import re

def clean_amount(value):
    if not value or value == "-":
        return 0.0
    return float(value.replace(",", ""))


def parse_bank_islam(pdf):
    """
    Parses Bank Islam statements using pdfplumber table extraction.
    Returns a list of transaction dicts.
    """
    transactions = []

    for page in pdf.pages:
        tables = page.extract_tables()

        if not tables:
            continue

        for table in tables:
            # Skip malformed tables
            if not table or len(table) < 2:
                continue

            header = table[0]  # We skip header row

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

                if not date_raw or "Total" in str(no):
                    continue

                # Normalize date format
                if re.match(r"\d{2}/\d{2}/\d{4}", date_raw):
                    dd, mm, yyyy = date_raw.split("/")
                    date_fmt = f"{yyyy}-{mm}-{dd}"
                else:
                    date_fmt = date_raw

                description = " ".join(str(desc).split())

                debit = clean_amount(debit_raw)
                credit = clean_amount(credit_raw)
                balance = clean_amount(balance_raw)

                transactions.append({
                    "date": date_fmt,
                    "description": description,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                })

    return transactions
