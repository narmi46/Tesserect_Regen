import regex as re

def parse_bank_islam_line(line):
    """
    Parse one transaction line from Bank Islam PDF.
    Expected Example:
    13/03/2025 16:00:26 INV/2501/2 177 1590 IBG TRANSFER TO CA 801 9999947 801 4,200.00 59,342.10
    """

    line = line.strip()
    if not line:
        return None

    # Main regex pattern for Bank Islam
    PATTERN_BI = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+"         # Date
        r"(\d{2}:\d{2}:\d{2})\s+"         # Time
        r"(\S+)\s+"                       # Customer/EFT No (ignored)
        r"(\d{3,4})\s+"                   # Transaction Code
        r"(.+?)\s+"                       # Description (lazy)
        r"(\d+)\s+(\d+)\s+(\d+)\s+"       # Branch / Ref / Branch (ignored)
        r"([0-9,]+\.\d{2}|-)\s+"          # Debit
        r"([0-9,]+\.\d{2}|-)"             # Balance OR Credit depending on position
    )

    match = PATTERN_BI.search(line)
    if not match:
        return None

    (
        date_raw, time_raw, customer_ref, code,
        desc, br1, br2, br3, amount_raw, balance_raw
    ) = match.groups()

    # Convert date to YYYY-MM-DD
    dd, mm, yyyy = date_raw.split("/")
    date_fmt = f"{yyyy}-{mm}-{dd}"

    # Debit or Credit?
    amount = amount_raw.replace(",", "")
    amount_val = float(amount) if amount != "-" else 0.0

    # Determine credit or debit from code
    # IBG TRANSFER TO CA → credit normally
    desc_u = desc.upper()

    if "TRANSFER" in desc_u and "TO CA" in desc_u:
        debit = 0.0
        credit = amount_val
    elif "PROFIT PAID" in desc_u:
        debit = 0.0
        credit = amount_val
    else:
        # Service charge, DD CASA - DR, CMS SERVICE CHARGE → debit
        debit = amount_val
        credit = 0.0

    # Balance
    balance = float(balance_raw.replace(",", "")) if balance_raw != "-" else 0.0

    return {
        "date": date_fmt,
        "description": desc.strip(),
        "debit": debit,
        "credit": credit,
        "balance": balance,
    }


def parse_bank_islam(text):
    """
    Parses the entire Bank Islam statement text.
    """
    tx_list = []

    for line in text.splitlines():
        tx = parse_bank_islam_line(line)
        if tx:
            tx_list.append(tx)

    return tx_list
