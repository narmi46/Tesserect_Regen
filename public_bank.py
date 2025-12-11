import re

# ---------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------

# Matches date at start of line: "05/06 ..."
DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")

# Matches amount + balance ANYWHERE in line
AMOUNT_BAL = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})"
)

# Matches "Balance B/F"
BAL_ONLY = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$",
    re.IGNORECASE
)

# ---------------------------------------------------------
# Simplified Main Logic
# ---------------------------------------------------------

def parse_transactions_pbb(text, page, year="2025"):
    tx = []
    prev_balance = None
    current_date = None
    first_desc_line = None  # Only store the FIRST line of each transaction

    lines = text.splitlines()

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # -----------------------------------------
        # CASE 1: Balance B/F
        # -----------------------------------------
        bal_match = BAL_ONLY.match(line)
        if bal_match:
            current_date = bal_match.group("date")
            prev_balance = float(bal_match.group("balance").replace(",", ""))
            first_desc_line = None
            continue

        # -----------------------------------------
        # CASE 2: A new transaction STARTS (date line)
        # -----------------------------------------
        date_match = DATE_LINE.match(line)
        if date_match:
            current_date = date_match.group("date")
            first_desc_line = date_match.group("rest").strip()
            continue

        # -----------------------------------------
        # CASE 3: Amount + Balance line
        # -----------------------------------------
        amt_match = AMOUNT_BAL.search(line)
        if amt_match:
            amount = float(amt_match.group("amount").replace(",", ""))
            balance = float(amt_match.group("balance").replace(",", ""))

            # If no description was captured earlier (e.g. no date),
            # use this line without the numeric part
            if not first_desc_line:
                clean_desc = line.replace(amt_match.group(0), "").strip()
            else:
                clean_desc = first_desc_line

            # -----------------------------------------
            # Determine debit or credit using balance difference
            # -----------------------------------------
            debit = credit = 0.0
            if prev_balance is not None:
                if balance < prev_balance:
                    debit = amount
                elif balance > prev_balance:
                    credit = amount

            # -----------------------------------------
            # Convert date to ISO format
            # -----------------------------------------
            if current_date:
                dd, mm = current_date.split("/")
                iso_date = f"{year}-{mm}-{dd}"
            else:
                iso_date = f"{year}-01-01"

            # -----------------------------------------
            # Append transaction
            # -----------------------------------------
            tx.append({
                "date": iso_date,
                "description": clean_desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page,
                "source_file": "test.pdf"
            })

            # Reset for next transaction
            prev_balance = balance
            first_desc_line = None

            continue

        # -----------------------------------------
        # Ignore all other lines (IMEPS, TNG, CIM, GHL, etc.)
        # -----------------------------------------

    return tx
