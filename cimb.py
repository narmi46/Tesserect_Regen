import regex as re

# DATE line: "30/05/2024 SOMETHING"
PATTERN_DATE = re.compile(r"^(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<desc>.+)$")

# FINAL NUMERIC LINE: "993830651126 380.00 212,954.99"
PATTERN_NUMERIC = re.compile(
    r"^(?P<ref>[A-Z0-9]+)\s+"
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+"
    r"(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

def parse_transactions_cimb(text: str, page_num: int):
    tx_list = []
    current_date = None
    desc_lines = []
    prev_balance = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # A) DATE LINE (start new transaction)
        m_date = PATTERN_DATE.match(line)
        if m_date:
            # If previous transaction exists but incomplete → ignore
            current_date = m_date.group("date")
            desc_lines = [m_date.group("desc")]
            continue

        # B) NUMERIC LINE (final line of a transaction)
        m_num = PATTERN_NUMERIC.match(line)
        if m_num and current_date:
            ref = m_num.group("ref")
            amount = float(m_num.group("amount").replace(",", ""))
            balance = float(m_num.group("balance").replace(",", ""))

            # Determine debit/credit using balance difference
            if prev_balance is None:
                debit, credit = 0.0, amount
            else:
                if balance < prev_balance:
                    debit, credit = amount, 0.0
                else:
                    debit, credit = 0.0, amount

            prev_balance = balance

            tx_list.append({
                "date": current_date,
                "description": " ".join(desc_lines),
                "ref_no": ref,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            # Reset for next transaction
            current_date = None
            desc_lines = []
            continue

        # C) DESCRIPTION CONTINUATION LINES
        if current_date:
            desc_lines.append(line)

    return tx_list
