import regex as re

# ============================================================
# RHB BANK STATEMENT PARSER
# ============================================================
#
# Example rows from your RHB PDF:
#
# 05-02-2025 061 CLEAR / / AUTODEBIT 00001550 27,286.00 - 770,138.57-
# 25-02-2025 980 CLEAR / 00009992 - 30,000.00 740,138.57-
#
# The last value ALWAYS ends with "-" for overdraft balance.
#
# Columns are:
#   Date (DD-MM-YYYY)
#   Branch Code (3 digits)
#   Description (text)
#   Debit (or "-")
#   Credit (or "-")
#   Balance (like 770,138.57-)
#
# ============================================================

PATTERN_RHB = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"               # date: 05-02-2025
    r"(\d{3})\s+"                           # branch: 061
    r"(.*?)\s+"                             # description until DR/CR
    r"([0-9,]+\.\d{2}|-)\s+"                # debit or '-'
    r"([0-9,]+\.\d{2}|-)\s+"                # credit or '-'
    r"([0-9,]+\.\d{2})-"                    # balance (minus sign separate)
)


def parse_line_rhb(line, page_num):
    """
    Parse a single line of RHB bank statement.

    Handles overdraft balances like: 813,527.71-
    Converts them to negative floats.
    """

    m = PATTERN_RHB.search(line)
    if not m:
        return None

    date_raw, branch, desc, dr_raw, cr_raw, balance_raw = m.groups()

    # Convert date: DD-MM-YYYY → YYYY-MM-DD
    day, month, year = date_raw.split("-")
    full_date = f"{year}-{month}-{day}"

    # Debit / Credit parsing
    debit = float(dr_raw.replace(",", "")) if dr_raw != "-" else 0.0
    credit = float(cr_raw.replace(",", "")) if cr_raw != "-" else 0.0

    # ------------------------------
    # Handle overdraft (negative balance)
    # ------------------------------
    #
    # The regex captures "770,138.57" but the actual line ends with:
    # "770,138.57-"
    #
    # A trailing "-" ALWAYS means balance is NEGATIVE.
    #

    is_negative = line.strip().endswith("-")

    balance = float(balance_raw.replace(",", ""))
    if is_negative:
        balance = -balance

    # Combine branch and description for readability
    description = f"{branch} {desc.strip()}"

    return {
        "date": full_date,
        "description": description,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "page": page_num,
    }


def parse_transactions_rhb(text, page_num):
    """
    Parse all transactions within a block of text for RHB.
    """
    tx_list = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        tx = parse_line_rhb(line, page_num)
        if tx:
            tx_list.append(tx)

    return tx_list
