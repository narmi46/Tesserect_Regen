import fitz
import re

DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
AMOUNT_RE = re.compile(r"\d[\d,]*\.\d{2}")

def clean_amount(value):
    if not value:
        return 0.0
    return float(value.replace(",", "").strip())


def parse_bank_islam_pymupdf(path):
    doc = fitz.open(path)
    transactions = []
    current = None

    for page in doc:
        blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text, block_no)
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # sort by y then x

        for b in blocks:
            text = b[4].strip()

            # Try find date in block
            dmatch = DATE_RE.search(text)

            if dmatch:
                # Flush previous row
                if current:
                    transactions.append(current)

                date_raw = dmatch.group(1)
                dd, mm, yyyy = date_raw.split("/")
                if len(yyyy) == 2:
                    yyyy = "20" + yyyy
                date_fmt = f"{yyyy}-{mm}-{dd}"

                # Extract amounts from rightmost side
                amounts = AMOUNT_RE.findall(text)
                amounts = [clean_amount(a) for a in amounts]

                debit = credit = balance = 0.0
                if len(amounts) >= 3:
                    debit, credit, balance = amounts[-3:]
                elif len(amounts) == 2:
                    # debit/credit missing (detect automatically)
                    if "DR" in text.upper():
                        debit, balance = amounts
                    else:
                        credit, balance = amounts
                elif len(amounts) == 1:
                    balance = amounts[0]

                # Remove date + amounts → description
                desc = text
                desc = desc.replace(date_raw, "")
                for a in AMOUNT_RE.findall(text):
                    desc = desc.replace(a, "")
                desc = " ".join(desc.split()).strip()

                current = {
                    "date": date_fmt,
                    "description": desc,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance
                }

            else:
                # Continuation of description
                if current:
                    current["description"] += " " + text

    # Add last row
    if current:
        transactions.append(current)

    return transactions
