import regex as re

def parse_transactions_cimb(text: str, page_num: int, default_year="2025"):
    tx_list = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    current_date = None
    buffer_desc = []
    year = default_year

    # Detect year in header
    m = re.search(r"20\d{2}", text)
    if m:
        year = m.group(0)

    for line in lines:

        # -----------------------------------------
        # 1. Detect date rows like: 30/06/2024
        # -----------------------------------------
        m_date = re.match(r"^(\d{2}/\d{2})(?:/(\d{4}))?$", line)
        if m_date:
            # If year missing, insert detected year
            ddmm = m_date.group(1)
            yyyy = m_date.group(2) or year
            current_date = f"{ddmm}/{yyyy}"

            # clear buffer for next description
            buffer_desc = []
            continue

        # -----------------------------------------
        # 2. Identify amount line:
        #    xxxx.xx   and   balance xxxx.xx
        # -----------------------------------------
        m_amt = re.match(
            r"^(?P<ref>\d{6,})\s+"
            r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+"
            r"(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$",
            line
        )
        if m_amt and current_date:
            ref = m_amt.group("ref")
            amount = float(m_amt.group("amount").replace(",", ""))
            balance = float(m_amt.group("balance").replace(",", ""))

            # DESCRIPTION = all buffered lines joined
            description = " ".join(buffer_desc).strip()

            # Determine credit/debit using balance movement (like your PBB logic)
            # But since pdf shows deposits under "deposit column", 
            # CIMB already places deposit as positive, withdrawal negative.
            # So we infer credit vs debit based on typical pattern:
            # If description contains TR IBG or REMITTANCE CR → Credit
            # If contains TR TO SAVINGS, OTHER TRANSFER → Debit
            desc_upper = description.upper()
            if any(k in desc_upper for k in ["REMITTANCE", "CR", "I-FUNDS", "FROM"]):
                credit = amount
                debit = 0.0
            else:
                # default assume debit
                debit = amount
                credit = 0.0

            # Format ISO date
            dd, mm, yyyy = current_date.split("/")
            iso = f"{yyyy}-{mm}-{dd}"

            tx_list.append({
                "date": iso,
                "description": description,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

            # reset buffer
            buffer_desc = []
            continue

        # -----------------------------------------
        # 3. Otherwise accumulate description lines
        # -----------------------------------------
        if current_date:
            buffer_desc.append(line)

    return tx_list
