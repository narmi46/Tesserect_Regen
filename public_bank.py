import regex as re

# Detect a date at the start (dd/mm)
DATE_PREFIX = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")

# Detect lines containing only amount + balance
AMOUNT_BAL_ONLY = re.compile(
    r"^(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

# Detect full row without date (description + amount + balance)
DESC_AMOUNT_BAL = re.compile(
    r"^(?P<desc>.+?)\s+(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

# Detect rows like "05/06 Balance B/F 298,754.25"
BALANCE_ONLY = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<desc>Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$",
    re.IGNORECASE
)

def parse_transactions_pbb(text: str, page_num: int, default_year="2025"):
    tx_list = []

    current_date = None
    prev_balance = None
    pending_desc = ""   # store multi-line description

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # ------------------------------------------
        # 1. Balance B/F / C/F lines
        # ------------------------------------------
        m_bal = BALANCE_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")
            prev_balance = float(m_bal.group("balance").replace(",", ""))
            pending_desc = ""
            continue

        # ------------------------------------------
        # 2. Lines that start with a date
        # ------------------------------------------
        m_date = DATE_PREFIX.match(line)
        if m_date:
            current_date = m_date.group("date")
            desc_part = m_date.group("rest")
            pending_desc = ""  # reset

            # Does this line already contain amount + balance?
            m_full = DESC_AMOUNT_BAL.match(desc_part)
            if m_full:
                desc = m_full.group("desc")
                amount = float(m_full.group("amount").replace(",", ""))
                balance = float(m_full.group("balance").replace(",", ""))

                # Determine debit or credit using BALANCE COMPARISON
                if prev_balance is not None and balance < prev_balance:
                    debit, credit = amount, 0.0
                else:
                    debit, credit = 0.0, amount

                prev_balance = balance

                dd, mm = current_date.split("/")
                iso = f"{default_year}-{mm}-{dd}"

                tx_list.append({
                    "date": iso,
                    "description": desc,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                    "page": page_num
                })
            else:
                # Description continues to next lines
                pending_desc = desc_part

            continue

        # ------------------------------------------
        # 3. A line with ONLY amount + balance
        # (This completes a multi-line description)
        # ------------------------------------------
        m_amt_bal = AMOUNT_BAL_ONLY.match(line)
        if m_amt_bal and pending_desc:
            amount = float(m_amt_bal.group("amount").replace(",", ""))
            balance = float(m_amt_bal.group("balance").replace(",", ""))

            # Debit or credit?
            if prev_balance is not None and balance < prev_balance:
                debit, credit = amount, 0.0
            else:
                debit, credit = 0.0, amount

            prev_balance = balance

            dd, mm = current_date.split("/")
            iso = f"{default_year}-{mm}-{dd}"

            tx_list.append({
                "date": iso,
                "description": pending_desc.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            pending_desc = ""  # clear
            continue

        # ------------------------------------------
        # 4. Full description + amount + balance but NO DATE
        # ------------------------------------------
        m_desc_amt = DESC_AMOUNT_BAL.match(line)
        if m_desc_amt and current_date:
            desc = m_desc_amt.group("desc")
            amount = float(m_desc_amt.group("amount").replace(",", ""))
            balance = float(m_desc_amt.group("balance").replace(",", ""))

            if prev_balance is not None and balance < prev_balance:
                debit, credit = amount, 0.0
            else:
                debit, credit = 0.0, amount

            prev_balance = balance

            dd, mm = current_date.split("/")
            iso = f"{default_year}-{mm}-{dd}"

            tx_list.append({
                "date": iso,
                "description": desc.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            pending_desc = ""
            continue

        # ------------------------------------------
        # 5. Otherwise, this is a continuation description line
        # ------------------------------------------
        pending_desc += " " + line if pending_desc else line

    return tx_list
