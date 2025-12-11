import re

# ---------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------

# Date at start of line: "05/06 ..."
DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")

# Amount + balance ANYWHERE in the line
AMOUNT_BAL = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})"
)

# Any "Balance ..." line with a date
BAL_ONLY = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+.*Balance.*?(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$",
    re.IGNORECASE,
)

# Metadata/Header lines to ignore
IGNORE_PREFIXES = [
    "CLEAR WATER", "/ROC", "PVCWS", "2025", "IMEPS",
    "PUBLIC BANK", "PAGE", "TEL:", "MUKA SURAT", "TARIKH",
    "DATE", "NO.", "URUS NIAGA",
]

def parse_transactions_pbb(text, page, year="2025"):
    tx = []
    prev_balance = None
    current_date = None
    first_desc_line = None  # only the first line of the transaction

    def is_ignored(line: str) -> bool:
        u = line.upper()
        return any(u.startswith(p) for p in IGNORE_PREFIXES)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or is_ignored(line):
            continue

        # -----------------------------------------
        # 1) Balance-only lines (no transaction row)
        # -----------------------------------------
        m_bal = BAL_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")
            prev_balance = float(m_bal.group("balance").replace(",", ""))
            first_desc_line = None
            continue

        # -----------------------------------------
        # 2) Date line (may or may not also have amount)
        #    IMPORTANT: do NOT "continue" here. We still
        #    want to check the same line for amount+balance.
        # -----------------------------------------
        m_date = DATE_LINE.match(line)
        if m_date:
            current_date = m_date.group("date")
            # FIRST line of description for this date
            first_desc_line = m_date.group("rest").strip()

        # -----------------------------------------
        # 3) Amount + balance line (this is the real
        #    transaction line we care about)
        # -----------------------------------------
        m_amt = AMOUNT_BAL.search(line)
        if not m_amt:
            # no amount, no need to do anything else on this line
            continue

        stated_amount = float(m_amt.group("amount").replace(",", ""))
        new_balance = float(m_amt.group("balance").replace(",", ""))

        # Description:
        # - If we already captured a first_desc_line for this date, use that.
        # - Otherwise, use this line text minus the numeric part.
        if first_desc_line:
            desc = first_desc_line
        else:
            desc = line.replace(m_amt.group(0), "").strip()

        # -----------------------------------------
        # 4) Compute debit / credit from BALANCE ONLY
        # -----------------------------------------
        debit = credit = 0.0

        if prev_balance is not None:
            diff = round(new_balance - prev_balance, 2)

            if diff > 0:
                credit = abs(diff)
            elif diff < 0:
                debit = abs(diff)
            # if diff == 0: no movement (unlikely)
        else:
            # first transaction on statement/page –
            # fall back to stated amount as credit
            credit = stated_amount

        # -----------------------------------------
        # 5) Date to ISO format
        # -----------------------------------------
        if current_date:
            dd, mm = current_date.split("/")
            iso_date = f"{year}-{mm}-{dd}"
        else:
            iso_date = f"{year}-01-01"

        # -----------------------------------------
        # 6) Append transaction row
        # -----------------------------------------
        tx.append({
            "date": iso_date,
            "description": desc,
            "debit": debit,
            "credit": credit,
            "balance": new_balance,
            "page": page,
            "source_file": "test.pdf",  # or your real filename
        })

        # update state for next row
        prev_balance = new_balance
        # we only want the FIRST line per transaction; clear so
        # a new transaction on same date won't reuse old desc
        first_desc_line = None

    return tx
