import regex as re

# Detect a date at the start (dd/mm)
DATE_PREFIX = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")

# Detect lines containing only amount + balance
AMT_BAL_LINE = re.compile(
    r"^(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

# Detect lines containing description + amount + balance (no date)
DESC_AMT_BAL = re.compile(
    r"^(?P<desc>.+?)\s+(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

# Detect Balance B/F or C/F, which contains date + description + balance only
BALANCE_ONLY = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<desc>Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$",
    re.IGNORECASE,
)

def parse_transactions_pbb(text: str, page_num: int, default_year="2025"):
    tx_list = []

    current_date = None
    prev_balance = None
    pending_desc = ""   # store multi-line description until amount appears

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # -----------------------------
        # 1. Balance only rows (B/F or C/F)
        # -----------------------------
        m_bal = BALANCE_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")
            prev_balance = float(m_bal.group("balance").replace(",", ""))
            pending_desc = ""
            continue

        # -----------------------------
        # 2. A new line starting with a date
        # -----------------------------
        m_date = DATE_PREFIX.match(line)
        if m_date:
            # Save any pending description (rare case)
            pending_desc = ""
            current_date = m_date.group("date")
            desc_part = m_date.group("rest")

            # Does this line include amount + balance?
            m_full = DESC_AMT_BAL.match(desc_part)
            if m_full:
                desc = m_full.group("desc")
                amount = float(m_full.group("amount").replace(",", ""))
                balance = float(m_full.group("balance").replace(",", ""))

                # Determine debit/credit
                if prev_balance is not None and balance < prev_balance:
                    debit, credit = amount, 0.0
                else:
                    debit, credit = 0.0, amount

                prev_balance = balance

                # Convert date
                dd, mm = current_date.split("/")
                iso_date = f"{default_year}-{mm}-{dd}"

                tx_list.append({
                    "date": iso_date,
                    "description": desc,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                    "page": page_num
                })
            else:
                # This date-row has no amount; start accumulating description
                pending_desc = desc_part
            continue

        # -----------------------------
        # 3. Detect lines with amount + balance, completing a multi-line record
        # -----------------------------
        m_amtbal = AMT_BAL_LINE.match(line)
        if m_amtbal and pending_desc:
            amount = float(m_amtbal.group("amount").replace(",", ""))
            balance = float(m_amtbal.group("balance").replace(",", ""))

            # Determine debit/credit
            if prev_balance is not None and balance < prev_balance:
                debit, credit = amount, 0.0
            else:
                debit, credit = 0.0, amount

            prev_balance = balance

            dd, mm = current_date.split("/")
            iso_date = f"{default_year}-{mm}-{dd}"

            tx_list.append({
                "date": iso_date,
                "description": pending_desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            pending_desc = ""
            continue

        # -----------------------------
        # 4. Detect full no-date 1-line rows (desc + amount + balance)
        # -----------------------------
        m_desc_amt = DESC_AMT_BAL.match(line)
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
            iso_date = f"{default_year}-{mm}-{dd}"

            tx_list.append({
                "date": iso_date,
                "description": desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
            pending_desc = ""
            continue

        # -----------------------------
        # 5. Otherwise, treat this as continuation of a multi-line description
        # -----------------------------
        pending_desc += " " + line if pending_desc else line

    return tx_list
