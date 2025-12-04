import regex as re

DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")
AMOUNT_BAL = re.compile(r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")
BAL_ONLY = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$", re.IGNORECASE)

# Keywords that signal ALWAYS a new transaction (no date required)
NEW_TX_KEYWORDS = [
    "TSFR", "DUITNOW", "GIRO", "JOMPAY", "RMT", "DR-ECP",
    "HANDLING", "FEE", "DEP", "RTN"
]

def parse_transactions_pbb(text, page, year="2025"):
    tx = []
    current_date = None
    prev_balance = None
    desc_accum = ""
    waiting_for_amount = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 1. Balance only (B/F or C/F)
        b = BAL_ONLY.match(line)
        if b:
            current_date = b.group("date")
            prev_balance = float(b.group("balance").replace(",", ""))
            desc_accum = ""
            waiting_for_amount = True
            continue

        # 2. Date line → start new transaction
        d = DATE_LINE.match(line)
        if d:
            current_date = d.group("date")
            desc_accum = d.group("rest")
            waiting_for_amount = True
            continue

        # 3. Detect amount+balance → finalize transaction
        a = AMOUNT_BAL.search(line)
        if a and waiting_for_amount:
            amount = float(a.group("amount").replace(",", ""))
            balance = float(a.group("balance").replace(",", ""))

            # Determine debit/credit
            if prev_balance is not None and balance < prev_balance:
                debit, credit = amount, 0.0
            else:
                debit, credit = 0.0, amount

            prev_balance = balance

            dd, mm = current_date.split("/")
            iso = f"{year}-{mm}-{dd}"

            tx.append({
                "date": iso,
                "description": desc_accum.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page
            })

            desc_accum = ""
            waiting_for_amount = False
            continue

        # 4. Detect new transaction WITHOUT date
        if any(line.startswith(k) for k in NEW_TX_KEYWORDS):
            # Flush previous if it had no amount (edge case)
            desc_accum = line
            waiting_for_amount = True
            continue

        # 5. Otherwise → continuation line
        desc_accum += " " + line if desc_accum else line

    return tx
