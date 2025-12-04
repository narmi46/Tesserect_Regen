import re

def parse_float(val):
    if not val:
        return 0.0
    clean = str(val).replace(",", "").strip()
    try:
        return float(clean)
    except:
        return 0.0

def split_row_text(text):
    """
    Public Bank rows are like:
    '05/06 RMT CR 256347 AT CPC 80,000.00 298,831.79'
    
    This splits into:
    date, desc, amount, balance
    """
    parts = text.split()
    if len(parts) < 2:
        return None, None, None, None

    # Detect date if present
    if re.match(r"^\d{2}/\d{2}$", parts[0]):
        date = parts[0]
        body = parts[1:]
    else:
        date = None
        body = parts

    # Find last two numeric fields = amount + balance
    nums = [i for i, p in enumerate(body) if re.match(r"^\d{1,3}(?:,\d{3})*\.\d{2}$", p)]
    
    if len(nums) >= 2:
        amt_index = nums[-2]
        bal_index = nums[-1]
        amount = parse_float(body[amt_index])
        balance = parse_float(body[bal_index])
        desc = " ".join(body[:amt_index])
        return date, desc, amount, balance

    # If no numbers → continuation line
    return None, text, None, None

def parse_transactions_pbb(page, page_num, source_file):
    """
    Public Bank version of your CIMB parser.
    Still uses extract_table(), but processes each row manually.
    """
    tx_list = []
    table = page.extract_table()

    if not table:
        return tx_list

    current_date = None
    prev_balance = None
    desc_accum = ""

    for row in table:
        if not row or not row[0]:
            continue

        text = row[0].strip()
        if not text:
            continue

        date, desc, amount, balance = split_row_text(text)

        # A. New transaction row (has amount & balance)
        if amount is not None and balance is not None:

            # If date missing, inherit last date
            if date:
                current_date = date

            # Determine debit or credit using balance comparison
            if prev_balance is not None and balance < prev_balance:
                debit = amount
                credit = 0.0
            else:
                debit = 0.0
                credit = amount

            prev_balance = balance

            tx_list.append({
                "date": current_date,
                "description": (desc_accum + " " + desc).strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num,
                "source_file": source_file
            })

            # reset continuation accumulator
            desc_accum = ""

        # B. Continuation line (no amount/balance)
        else:
            # If its a date row with no numbers → update date
            if date:
                current_date = date
            else:
                # append this description fragment
                desc_accum += " " + desc if desc_accum else desc

    return tx_list
