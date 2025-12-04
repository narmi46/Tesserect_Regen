import regex as re

DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")
AMOUNT_BAL = re.compile(r"^.*?(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")
BAL_ONLY = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")

def parse_transactions_pbb(text, page, default_year="2025"):
    tx = []
    current_date = None
    prev_balance = None
    desc_accum = ""  # accumulate description until amount+balance found

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # -------------------------
        # Balance B/F or C/F
        # -------------------------
        b = BAL_ONLY.match(line)
        if b:
            current_date = b.group("date")
            prev_balance = float(b.group("balance").replace(",", ""))
            desc_accum = ""
            continue

        # -------------------------
        # Date line → new transaction starts
        # -------------------------
        d = DATE_LINE.match(line)
        if d:
            # If previous description not flushed, flush it WITHOUT amount (edge case)
            desc_accum = ""      
            current_date = d.group("date")
            desc_accum = d.group("rest")
            continue

        # -------------------------
        # Check if this line has amount + balance
        # -------------------------
        amt = AMOUNT_BAL.search(line)
        if amt:
            # Found a completed transaction
            amount = float(amt.group("amount").replace(",", ""))
            balance = float(amt.group("balance").replace(",", ""))

            # Remove amount+balance part from description
            clean_desc = desc_accum.strip()

            # Determine debit or credit
            if prev_balance and balance < prev_balance:
                debit, credit = amount, 0.0
            else:
                debit, credit = 0.0, amount

            prev_balance = balance

            # Format date
            dd, mm = current_date.split("/")
            iso = f"{default_year}-{mm}-{dd}"

            tx.append({
                "date": iso,
                "description": clean_desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page
            })

            desc_accum = ""  # reset after finishing transaction
            continue

        # -------------------------
        # Otherwise, this is continuation of description lines
        # -------------------------
        desc_accum += " " + line if desc_accum else line

    return tx
