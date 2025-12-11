import re

# ----------------------------
# REGEX
# ----------------------------

# Date at start
DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")

# Amount + balance ANYWHERE in the line
AMOUNT_BAL = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})"
)

# Balance B/F and C/F
BAL_ONLY = re.compile(
    r"^(?P<date>\d{2}/\d{2}).*Balance.*?(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})",
    re.IGNORECASE,
)

# Transaction keyword starters (must match PBB)
TX_STARTERS = (
    "DEP", "DR-", "CR", "GIRO", "DUITNOW", "HANDLING", "CHRG", "CHARGE",
    "RMT", "JOMPAY", "TSFR", "TRANSFER", "PAYMENT"
)

IGNORE_PREFIXES = [
    "CLEAR WATER", "/ROC", "PVCWS", "PUBLIC BANK", "DATE", "NO.",
    "URUS NIAGA", "PAGE", "MUKA", "TEL:", "2025", "IMEPS"
]

# ----------------------------
# MAIN
# ----------------------------

def parse_transactions_pbb(text, page, year="2025"):
    tx = []

    prev_balance = None
    current_date = None
    pending_desc = None   # Only keep the FIRST line of a transaction

    def ignored(line):
        u = line.upper()
        return any(u.startswith(p) for p in IGNORE_PREFIXES)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or ignored(line):
            continue

        # ----------------------------
        # CASE 1 — Balance B/F or C/F
        # ----------------------------
        m_bal = BAL_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")
            prev_balance = float(m_bal.group("balance").replace(",", ""))
            pending_desc = None
            continue

        # ----------------------------
        # CASE 2 — DATE line
        # ----------------------------
        m_date = DATE_LINE.match(line)
        if m_date:
            current_date = m_date.group("date")
            pending_desc = m_date.group("rest").strip()
            # Still continue because the *same line* may contain amount+balance
            # We do NOT "continue" here so the amount detector still runs

        # ----------------------------
        # CASE 3 — Amount + Balance line → THIS is the REAL transaction row
        # ----------------------------
        m_amt = AMOUNT_BAL.search(line)
        if m_amt:
            amount = float(m_amt.group("amount").replace(",", ""))
            balance = float(m_amt.group("balance").replace(",", ""))

            # If no description captured earlier:
            # Either this line starts with a keyword OR use this line (minus numbers)
            if pending_desc:
                desc = pending_desc
            else:
                # Remove the numeric part
                desc = line.replace(m_amt.group(0), "").strip()

            # ----------------------------
            # DETERMINE DEBIT / CREDIT from balance movement ONLY
            # ----------------------------
            debit = credit = 0.0

            if prev_balance is not None:
                diff = balance - prev_balance
                if diff > 0:
                    credit = diff
                elif diff < 0:
                    debit = -diff
            else:
                # First tx, fallback
                credit = amount

            # ----------------------------
            # Date formatting
            # ----------------------------
            if current_date:
                dd, mm = current_date.split("/")
                iso = f"{year}-{mm}-{dd}"
            else:
                iso = f"{year}-01-01"

            tx.append({
                "date": iso,
                "description": desc,
                "debit": round(debit, 2),
                "credit": round(credit, 2),
                "balance": balance,
                "page": page,
                "source_file": "statement.pdf"
            })

            prev_balance = balance
            pending_desc = None
            continue

        # ----------------------------
        # CASE 4 — A line starting with a transaction keyword
        #         but NO date on this line.
        #         (e.g. "DEP-ECP 234003 14.35 13,744.33")
        # ----------------------------
        if any(line.startswith(k) for k in TX_STARTERS):
            # store first line as description
            pending_desc = line
            # do NOT continue — amount+balance may be on next line
            continue

        # Other random continuation lines → safely ignored
        # (IMEPS, GHL, CIM, etc.)

    return tx
