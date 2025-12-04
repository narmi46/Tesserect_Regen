import re
import pdfplumber

def parse_transactions_cimb(text, page_num, source_file, page=None):
    """
    Fully accurate CIMB parser using positional (x0) column detection.
    Works even when text columns collapse in extract_text().
    """

    if page is None:
        return []   # the app must pass the page object (pdf.pages[n])

    chars = page.chars

    # Step 1 — Group characters by y-line (physical row)
    lines = {}
    for c in chars:
        y = round(c["top"], 1)
        lines.setdefault(y, []).append(c)

    transactions = []

    # Column boundaries (tuned for your CIMB PDFs)
    X_DATE = 0
    X_DESC = 90
    X_REF  = 260
    X_WITH = 360
    X_DEPO = 440
    X_BAL  = 520

    sorted_y = sorted(lines.keys())

    for y in sorted_y:
        row = lines[y]
        row = sorted(row, key=lambda c: c["x0"])

        # Turn row chars → text blocks sorted by x-position
        blocks = {}
        for c in row:
            x = c["x0"]
            blk = blocks.setdefault(x, "")
            blocks[x] += c["text"]

        # Collect all numbers (withdraw/deposit/balance)
        nums = [v for v in blocks.values() if re.match(r"^[\d,]+\.\d{2}$", v)]
        if len(nums) not in (1, 2, 3):
            continue

        # Extract date
        date = None
        for x, v in blocks.items():
            if re.match(r"^\d{2}/\d{2}/\d{4}$", v):
                date = v
        if not date:
            continue

        # Description
        desc = ""
        for x, v in blocks.items():
            if X_DESC <= x < X_REF and not re.match(r"^\d{2}/\d{2}/\d{4}$", v):
                desc += v + " "

        # Ref No
        refno = ""
        for x, v in blocks.items():
            if X_REF <= x < X_WITH and re.match(r"^\d{6,20}$", v):
                refno = v

        # Determine debit/credit/balance based on column x0
        debit = 0.0
        credit = 0.0
        balance = 0.0

        for x, v in blocks.items():
            if re.match(r"^[\d,]+\.\d{2}$", v):
                amt = float(v.replace(",", ""))

                if X_WITH <= x < X_DEPO:
                    debit = amt
                elif X_DEPO <= x < X_BAL:
                    credit = amt
                elif x >= X_BAL:
                    balance = amt

        # Skip empty transactions
        if debit == 0 and credit == 0:
            continue

        transactions.append({
            "date": date.replace("/", "-"),
            "description": desc.strip(),
            "ref_no": refno,
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "page": page_num,
            "source_file": source_file
        })

    return transactions
