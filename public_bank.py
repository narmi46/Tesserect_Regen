import regex as re

# Pattern with date + description + amount + balance
PATTERN_WITH_DATE = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+
    (?P<desc>.+?)\s+
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """, re.VERBOSE
)

# Pattern no-date (continuation)
PATTERN_NO_DATE = re.compile(
    r"""
    ^(?P<desc>.+?)\s+
    (?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """, re.VERBOSE
)

# Balance B/F and C/F (date + balance only)
PATTERN_BAL_ONLY = re.compile(
    r"""
    ^(?P<date>\d{2}/\d{2})\s+
    (?P<desc>Balance.*)\s+
    (?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$
    """, re.VERBOSE | re.IGNORECASE
)

def parse_transactions_pbb(text: str, page_num: int, default_year="2025"):
    tx_list = []
    current_date = None
    prev_balance = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # Balance only rows
        m_bal = PATTERN_BAL_ONLY.match(line)
        if m_bal:
            current_date = m_bal.group("date")
            prev_balance = float(m_bal.group("balance").replace(",", ""))
            continue

        # With date row
        m1 = PATTERN_WITH_DATE.match(line)
        if m1:
            current_date = m1.group("date")
            desc = m1.group("desc").strip()
            amount = float(m1.group("amount").replace(",", ""))
            balance = float(m1.group("balance").replace(",", ""))

            # Determine debit/credit via balance difference
            if prev_balance is not None:
                if balance < prev_balance:
                    debit, credit = amount, 0.0
                else:
                    debit, credit = 0.0, amount
            else:
                debit, credit = 0.0, amount   # fallback

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
            continue

        # No date row
        if current_date:
            m2 = PATTERN_NO_DATE.match(line)
            if m2:
                desc = m2.group("desc").strip()
                amount = float(m2.group("amount").replace(",", ""))
                balance = float(m2.group("balance").replace(",", ""))

                # Determine debit/credit
                if prev_balance is not None:
                    if balance < prev_balance:
                        debit, credit = amount, 0.0
                    else:
                        debit, credit = 0.0, amount
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

    return tx_list
