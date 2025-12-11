import re

# Detect amount + balance anywhere in the line
AMOUNT_BAL = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})"
)

# Detect date at beginning of line
DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<desc>.*)$")

# Balance B/F (start-of-page)
BAL_ONLY = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+Balance.*?(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})",
    re.IGNORECASE,
)

def parse_simple(text, page, year="2025"):
    tx = []
    prev_balance = None
    current_date = None
    pending_desc = None  # store ONLY THE FIRST LINE OF A TRANSACTION

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # ---------------------------
        # Balance B/F
        # ---------------------------
        m_bal = BAL_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")
            prev_balance = float(m_bal.group("balance").replace(",", ""))
            pending_desc = None
            continue

        # ---------------------------
        # Detect a date → start a new transaction description
        # ---------------------------
        m_date = DATE_LINE.match(line)
        if m_date:
            current_date = m_date.group("date")
            pending_desc = m_date.group("desc").strip()   # store only 1st line
            continue

        # ---------------------------
        # Detect an amount + balance line
        # ---------------------------
        m_amt = AMOUNT_BAL.search(line)
        if not m_amt:
            continue  # ignore everything else

        amount = float(m_amt.group("amount").replace(",", ""))
        balance = float(m_amt.group("balance").replace(",", ""))

        # If description was not started by date line → use this line as desc
        desc = pending_desc if pending_desc else line.replace(m_amt.group(0), "").strip()

        # Determine debit or credit
        debit = credit = 0.0
        if prev_balance is not None:
            if balance < prev_balance:
                debit = amount
            elif balance > prev_balance:
                credit = amount
        else:
            # first entry fallback
            debit = 0
            credit = amount

        # Format ISO date
        if current_date:
            dd, mm = current_date.split("/")
            iso = f"{year}-{mm}-{dd}"
        else:
            iso = f"{year}-01-01"

        tx.append({
            "date": iso,
            "description": desc,
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "page": page,
            "source_file": "statement.pdf"
        })

        # Reset
        prev_balance = balance
        pending_desc = None

    return tx
