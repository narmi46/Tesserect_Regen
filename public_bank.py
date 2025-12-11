import re

# ---------------------------------------------------------
# Simple Regex Patterns
# ---------------------------------------------------------
# Match: "DD/MM" followed by amounts and description on SAME line
TRANSACTION_LINE = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+"
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+"
    r"(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})"
    r"(?P<desc>.*?)$"
)

# Match Balance B/F lines (to track balance)
BALANCE_BF = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+Balance\s+B/F\s+"
    r"(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$",
    re.IGNORECASE
)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
IGNORE_KEYWORDS = [
    "TARIKH", "DATE", "TRANSACTION", "DEBIT", "CREDIT", "BALANCE",
    "PAGE", "MUKA SURAT", "PUBLIC BANK", "STATEMENT", "PENYATA",
    "PROTECTED", "DILINDUNGI", "TEL:", "SUMMARY", "RINGKASAN"
]

# ---------------------------------------------------------
# Main Parser - SIMPLE VERSION
# ---------------------------------------------------------
def parse_transactions_pbb(text, page, year="2025"):
    """
    Simple parser: Only extract lines with date + amounts.
    Calculate debit/credit from balance changes only.
    """
    tx = []
    lines = text.splitlines()
    
    prev_balance = None
    
    for line in lines:
        line = line.strip()
        
        # Skip empty or header lines
        if not line or len(line) < 10:
            continue
        
        # Skip header/footer lines
        if any(keyword in line.upper() for keyword in IGNORE_KEYWORDS):
            continue
        
        # Check for Balance B/F (update tracker only, no transaction)
        bal_bf = BALANCE_BF.match(line)
        if bal_bf:
            prev_balance = float(bal_bf.group("balance").replace(",", ""))
            continue
        
        # Try to match transaction line
        match = TRANSACTION_LINE.match(line)
        if not match:
            continue
        
        # Extract data
        date_str = match.group("date")
        amount = float(match.group("amount").replace(",", ""))
        balance = float(match.group("balance").replace(",", ""))
        desc = match.group("desc").strip()
        
        # Calculate debit/credit from balance change
        debit = 0.0
        credit = 0.0
        
        if prev_balance is not None:
            balance_change = balance - prev_balance
            
            if balance_change > 0:
                # Balance increased = Credit (money in)
                credit = amount
            elif balance_change < 0:
                # Balance decreased = Debit (money out)
                debit = amount
            else:
                # No change (rare case)
                credit = amount
        else:
            # First transaction on page - use heuristics
            if "DR-" in desc.upper() or "CHRG" in desc.upper():
                debit = amount
            else:
                credit = amount
        
        # Format date
        dd, mm = date_str.split("/")
        iso_date = f"{year}-{mm}-{dd}"
        
        # Create transaction
        tx.append({
            "date": iso_date,
            "description": desc,
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "page": page,
            "source_file": ""  # Set by app.py
        })
        
        # Update previous balance
        prev_balance = balance
    
    return tx
