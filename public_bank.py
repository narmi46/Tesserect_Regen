import regex as re

# REGEX DEFINITIONS
DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")
AMOUNT_BAL = re.compile(r"^(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")
DESC_AMT_BAL = re.compile(r"^(?P<desc>.+?)\s+(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")
BALANCE_ONLY = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<desc>Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$",
    re.IGNORECASE
)

def parse_transactions_pbb(text, page_num, default_year="2025"):
    tx = []
    current_date = None
    prev_balance = None
    pending_desc = ""     # accumulate description until amount+balance appears

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # -----------------------------------------------------
        # 1. Balance B/F or C/F
        # -----------------------------------------------------
        m_bal = BALANCE_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")
            prev_balance = float(m_bal.group("balance").replace(",", ""))
            pending_desc = ""
            continue

        # -----------------------------------------------------
        # 2. New row that starts with a date
        # -----------------------------------------------------
        m_date = DATE_LINE.match(line)
        if m_date:
            current_date = m_date.group("date")
            body = m_date.group("rest")
            pending_desc = ""

            # case: date + desc + amount + balance all in one line
            m_full = DESC_AMT_BAL.match(body)
            if m_full:
                desc = m_full.group("desc")
                amount = float(m_full.group("amount").replace(",", ""))
                balance = float(m_full.group("balance").replace(",", ""))

                debit = amount if prev_balance and balance < prev_balance else 0.0
                credit = amount if prev_balance and balance > prev_balance else 0.0
                prev_balance = balance

                dd, mm = current_date.split("/")
                iso = f"{default_year}-{mm}-{dd}"

                tx.append({
                    "date": iso,
                    "description": desc.strip(),
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                    "page": page_num
                })
            else:
                # incomplete → continue on next lines
                pending_desc = body
            continue

        # -----------------------------------------------------
        # 3. Amount + balance only → completes multi-line record
        # -----------------------------------------------------
        m_amt = AMOUNT_BAL.match(line)
        if m_amt and pending_desc:
            amount = float(m_amt.group("amount").replace(",", ""))
            balance = float(m_amt.group("balance").replace(",", ""))

            debit = amount if prev_balance and balance < prev_balance else 0.0
            credit = amount if prev_balance and balance > prev_balance else 0.0
            prev_balance = balance

            dd, mm = current_date.split("/")
            iso = f"{default_year}-{mm}-{dd}"

            tx.append({
                "date": iso,
                "description": pending_desc.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            pending_desc = ""
            continue

        # -----------------------------------------------------
        # 4. Full row without date (desc + amount + balance)
        # -----------------------------------------------------
        m_desc_amt = DESC_AMT_BAL.match(line)
        if m_desc_amt and current_date:
            desc = m_desc_amt.group("desc")
            amount = float(m_desc_amt.group("amount").replace(",", ""))
            balance = float(m_desc_amt.group("balance").replace(",", ""))

            debit = amount if prev_balance and balance < prev_balance else 0.0
            credit = amount if prev_balance and balance > prev_balance else 0.0
            prev_balance = balance

            dd, mm = current_date.split("/")
            iso = f"{default_year}-{mm}-{dd}"

            tx.append({
                "date": iso,
                "description": desc.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            pending_desc = ""
            continue

        # -----------------------------------------------------
        # 5. Otherwise treat as continuation of description
        # -----------------------------------------------------
        pending_desc += " " + line if pending_desc else line

    return tx
