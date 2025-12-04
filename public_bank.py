import regex as re

DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")
AMOUNT_BAL = re.compile(r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")
BAL_ONLY = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$", re.IGNORECASE)

# Keywords that ALWAYS start a real transaction (no date needed)
TX_KEYWORDS = [
    "TSFR", "DUITNOW", "GIRO", "JOMPAY", "RMT", "DR-ECP",
    "HANDLING", "FEE", "DEP", "RTN"
]

# Lines that should NEVER be merged into descriptions
IGNORE_PREFIXES = [
    "CLEAR WATER", "/ROC", "PVCWS", "2025", "IMEPS"
]

def parse_transactions_pbb(text, page, year="2025"):
    tx = []
    current_date = None
    prev_balance = None
    desc_accum = ""
    waiting_for_amount = False

    def is_ignored(line):
        return any(line.upper().startswith(p) for p in IGNORE_PREFIXES)

    def is_tx_start(line):
        return any(line.startswith(k) for k in TX_KEYWORDS)

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # Ignore detail/metadata lines completely
        if is_ignored(line):
            continue

        # (1) Balance B/F or C/F
        b = BAL_ONLY.match(line)
        if b:
            current_date = b.group("date")
            prev_balance = float(b.group("balance").replace(",", ""))
            desc_accum = ""
            waiting_for_amount = True
            continue

        # (2) Date line → always new transaction
        d = DATE_LINE.match(line)
        if d:
            current_date = d.group("date")
            desc_accum = d.group("rest")
            waiting_for_amount = True
            continue

        # (3) Detect amount + balance → finalize
        a = AMOUNT_BAL.search(line)
        if a and waiting_for_amount:
            amount = float(a.group("amount").replace(",", ""))
            balance = float(a.group("balance").replace(",", ""))

            # Determine debit/credit
            debit = amount if prev_balance is not None and balance < prev_balance else 0.0
            credit = amount if prev_balance is not None and balance > prev_balance else 0.0

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

        # (4) NEW FIX: detect new transaction WITHOUT date
        if is_tx_start(line) and not waiting_for_amount:
            desc_accum = line
            waiting_for_amount = True
            continue

        # (5) Otherwise → continuation line
        desc_accum += " " + line if desc_accum else line

    return tx
