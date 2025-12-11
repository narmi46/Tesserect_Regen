import re

# ---------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------
# Matches date at start of line: "05/06 ..."
DATE_LINE = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.*)$")

# Matches amount + balance at end of line: "1,200.00 45,000.00"
AMOUNT_BAL = re.compile(r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$")

# Matches "Balance B/F" lines (updates tracking, but does not create a transaction row)
BAL_ONLY = re.compile(r"^(?P<date>\d{2}/\d{2})\s+(Balance.*)\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$", re.IGNORECASE)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
# Keywords that indicate the start of a transaction
TX_KEYWORDS = [
    "TSFR", "DUITNOW", "GIRO", "JOMPAY", "RMT", "DR-ECP",
    "HANDLING", "FEE", "DEP", "RTN", "PROFIT", "AUTOMATED",
    "CHARGES", "DEBIT", "CREDIT"
]

# Metadata/Header lines to ignore
IGNORE_PREFIXES = [
    "CLEAR WATER", "/ROC", "PVCWS", "2025", "IMEPS", 
    "PUBLIC BANK", "PAGE", "TEL:", "MUKA SURAT", "TARIKH", 
    "DATE", "NO.", "URUS NIAGA"
]

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

        # 1. Check for Amounts FIRST
        amount_match = AMOUNT_BAL.search(line)
        has_amount = bool(amount_match)
        
        # 2. Check for Start of New Transaction (Date or Keyword)
        date_match = DATE_LINE.match(line)
        keyword_match = is_tx_start(line)
        is_new_start = date_match or keyword_match
        
        # 3. SPECIAL CASE: Balance B/F (Update tracking only)
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
        
        # CASE A: Line HAS amounts
        if has_amount:
            # Extract numbers
            amount = float(amount_match.group("amount").replace(",", ""))
            balance = float(amount_match.group("balance").replace(",", ""))
            
            # Identify if this is a NEW single-line transaction or Continuation
            if is_new_start:
                if date_match:
                    current_date = date_match.group("date")
                    line_desc = date_match.group("rest")
                else:
                    # Remove amount from line to get clean description
                    line_desc = line.replace(amount_match.group(0), "").strip()
                
                final_desc = line_desc
            else:
                # Merge with accumulated description
                final_desc = desc_accum + " " + line.replace(amount_match.group(0), "").strip()

            # Determine Debit vs Credit
            debit = 0.0
            credit = 0.0
            
            if prev_balance is not None:
                if balance < prev_balance:
                    debit = amount
                elif balance > prev_balance:
                    credit = amount
            else:
                # Fallback if first item on page
                if "CR" in final_desc.upper() or "DEP" in final_desc.upper():
                    credit = amount
                else:
                    debit = amount

            # Date Formatting
            if current_date:
                dd, mm = current_date.split("/")
                iso = f"{year}-{mm}-{dd}"
            else:
                iso = f"{year}-01-01"

            # APPEND TO LIST IMMEDIATELY (Preserves Order)
            tx.append({
                "date": iso,
                "description": final_desc.strip(),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page,
                "source_file": "test.pdf"
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

        # CASE C: Continuation text
        elif waiting_for_amount:
            desc_accum += " " + line

    # No sorting is applied. 
    # The list 'tx' is returned exactly in the order the lines were processed.
    return tx
