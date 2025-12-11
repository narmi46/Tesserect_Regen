import fitz
import re

DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
AMOUNT_RE = re.compile(r"\d[\d,]*\.\d{2}")

def parse_bank_islam(pdf_data):
    """
    pdf_data can be:
    - raw PDF bytes (recommended)
    - file path (string)
    """

    # Decide how to open PDF
    if isinstance(pdf_data, (bytes, bytearray)):
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    elif isinstance(pdf_data, str):
        doc = fitz.open(pdf_data)
    else:
        raise TypeError(f"Bank Islam parser expected bytes or file path, got {type(pdf_data)}")

    transactions = []
    current = None

    for page in doc:
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

        for blk in blocks:
            text = blk[4].strip()

            # Detect start of new transaction
            dmatch = DATE_RE.search(text)

            if dmatch:
                if current:
                    transactions.append(current)

                date_raw = dmatch.group(1)
                dd, mm, yyyy = date_raw.split("/")
                if len(yyyy) == 2:
                    yyyy = "20" + yyyy
                date_fmt = f"{yyyy}-{mm}-{dd}"

                amts = [float(a.replace(",", "")) for a in AMOUNT_RE.findall(text)]

                debit = credit = balance = 0.0
                if len(amts) >= 3:
                    debit, credit, balance = amts[-3:]
                elif len(amts) == 2:
                    credit, balance = amts
                elif len(amts) == 1:
                    balance = amts[0]

                desc = text.replace(date_raw, "")
                for amt in AMOUNT_RE.findall(text):
                    desc = desc.replace(amt, "")
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
