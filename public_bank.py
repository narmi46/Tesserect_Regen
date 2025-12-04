import regex as re

# ---------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------
# Matches date at start of line: "05/06 ..."
DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")

# Matches amount + balance at end of line: "1,200.00 45,000.00"
AMOUNT_BAL = re.compile(r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")

# Matches specific "Balance B/F" lines
BAL_ONLY = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$", re.IGNORECASE)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
TX_KEYWORDS = [
    "TSFR", "DUITNOW", "GIRO", "JOMPAY", "RMT", "DR-ECP",
    "HANDLING", "FEE", "DEP", "RTN", "PROFIT"
]

IGNORE_PREFIXES = ["CLEAR WATER", "/ROC", "PVCWS", "2025", "IMEPS", "PUBLIC BANK", "PAGE", "TEL:"]

# ---------------------------------------------------------
# Main Logic
# ---------------------------------------------------------
def parse_transactions_pbb(text, page, year="2025"):
    tx = []
    current_date = None
    prev_balance = None
    
    # State holders
    desc_accum = ""
    waiting_for_amount = False
    
    def is_ignored(line):
        return any(line.upper().startswith(p) for p in IGNORE_PREFIXES)

    def is_tx_start(line):
        return any(line.startswith(k) for k in TX_KEYWORDS)

    lines = text.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line or is_ignored(line):
            continue

        # 1. Check for Amounts FIRST (independent of state)
        amount_match = AMOUNT_BAL.search(line)
        has_amount = bool(amount_match)
        
        # 2. Check for Start of New Transaction (Date or Keyword)
        date_match = DATE_LINE.match(line)
        keyword_match = is_tx_start(line)
        is_new_start = date_match or keyword_match
        
        # 3. SPECIAL CASE: Balance B/F (Update balance, don't capture tx)
        bal_match = BAL_ONLY.match(line)
        if bal_match:
            current_date = bal_match.group("date")
            prev_balance = float(bal_match.group("balance").replace(",", ""))
            desc_accum = ""
            waiting_for_amount = False 
            continue

        # -------------------------------------------------------
        # LOGIC BRANCHING
        # -------------------------------------------------------
        
        # CASE A: This line HAS amounts
        if has_amount:
            # Extract numbers
            amount = float(amount_match.group("amount").replace(",", ""))
            balance = float(amount_match.group("balance").replace(",", ""))
            
            # If this line ALSO looks like a start, it overrides any waiting state
            if is_new_start:
                if date_match:
                    current_date = date_match.group("date")
                    line_desc = date_match.group("rest")
                else:
                    # Remove the amount text from description to keep it clean
                    line_desc = line.replace(amount_match.group(0), "").strip()
                
                final_desc = line_desc
            else:
                # It's the amount for the PREVIOUSLY started transaction
                final_desc = desc_accum + " " + line.replace(amount_match.group(0), "").strip()

            # Save Transaction
            debit = amount if prev_balance is not None and balance < prev_balance else 0.0
            credit = amount if prev_balance is not None and balance > prev_balance else 0.0
            
            # Date Handling
            if current_date:
                dd, mm = current_date.split("/")
                iso = f"{year}-{mm}-{dd}"
            else:
                iso = f"{year}-01-01" # Fallback if header missing

            tx.append({
                "date": iso,
                "description": final_desc.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page
            })
            
            # Reset State
            prev_balance = balance
            desc_accum = ""
            waiting_for_amount = False

        # CASE B: No amounts, but STARTS a new transaction
        elif is_new_start:
            if date_match:
                current_date = date_match.group("date")
                desc_accum = date_match.group("rest")
            else:
                desc_accum = line
            
            waiting_for_amount = True

        # CASE C: Continuation of text
        elif waiting_for_amount:
            desc_accum += " " + line

    return tx
