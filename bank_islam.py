import fitz
import re

def parse_bank_islam(path):
    # Allow both filename & bytes
    if isinstance(path, (bytes, bytearray)):
        doc = fitz.open(stream=path, filetype="pdf")
    else:
        doc = fitz.open(path)

    transactions = []
    current = None
    DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
    AMOUNT_RE = re.compile(r"\d[\d,]*\.\d{2}")

    for page in doc:
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

        for blk in blocks:
            text = blk[4].strip()
            dmatch = DATE_RE.search(text)

            if dmatch:
                if current:
                    transactions.append(current)

                date_raw = dmatch.group(1)
                dd, mm, yyyy = date_raw.split("/")
                if len(yyyy) == 2:
                    yyyy = "20" + yyyy
                date_fmt = f"{yyyy}-{mm}-{dd}"

                amounts = [a.replace(",", "") for a in AMOUNT_RE.findall(text)]
                amounts = [float(a) for a in amounts]

                debit = credit = balance = 0.0
                if len(amounts) >= 3:
                    debit, credit, balance = amounts[-3:]
                elif len(amounts) == 2:
                    credit, balance = amounts
                elif len(amounts) == 1:
                    balance = amounts[0]

                desc = text.replace(date_raw, "")
                for a in AMOUNT_RE.findall(text):
                    desc = desc.replace(a, "")
                desc = " ".join(desc.split())

                current = {
                    "date": date_fmt,
                    "description": desc,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                }
            else:
                if current:
                    current["description"] += " " + text

    if current:
        transactions.append(current)

    return transactions
