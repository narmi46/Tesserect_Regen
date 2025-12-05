import re
from datetime import datetime

# ============================================================
# ROBUST RHB PARSER (Fixes Empty Output)
# ============================================================

# UPDATED PATTERN:
# 1. \s* inside quotes allows for newlines/spaces around the data.
# 2. [\s\S]*? handles multi-line descriptions.
# 3. We use verbose mode (re.X) for readability.

PATTERN_RHB_BLOCK = re.compile(r"""
    "\s*(\d{2}\s[A-Za-z]{3})\s*"   # Group 1: Date (Matches "07 Mar\n")
    \s*,\s* # Separator: Comma (ignoring surrounding space)
    "([\s\S]*?)"                   # Group 2: Description (Greedy match inside quotes)
    .*?                            # Ignore middle columns (Cheque, Debit, Credit)
    "\s*([0-9,]+\.\d{2})\s*"       # Group 3: Balance (Matches "1,000.00\n")
""", re.VERBOSE | re.DOTALL)

def parse_transactions_rhb(text, page_num, year="2024"):
    tx_list = []
    
    # scan the entire text block for matches
    for match in PATTERN_RHB_BLOCK.finditer(text):
        date_raw, desc_raw, balance_raw = match.groups()

        # --- 1. CLEAN & FORMAT DATE ---
        # Strip newlines/spaces from the captured date (e.g., "07 Mar\n" -> "07 Mar")
        clean_date_str = date_raw.strip()
        try:
            dt_obj = datetime.strptime(f"{clean_date_str} {year}", "%d %b %Y")
            full_date = dt_obj.strftime("%Y-%m-%d")
        except ValueError:
            full_date = clean_date_str

        # --- 2. CLEAN DESCRIPTION ---
        # Collapse multiple lines into one line
        description = desc_raw.replace('\n', ' ').replace('\r', '').strip()
        # Remove multiple spaces to make it neat
        description = re.sub(r'\s+', ' ', description)

        # --- 3. CLEAN BALANCE ---
        # Remove commas and whitespace
        clean_balance = balance_raw.replace(',', '').strip()
        try:
            balance = float(clean_balance)
        except ValueError:
            balance = 0.0

        tx_list.append({
            "date": full_date,
            "description": description,
            "balance": balance,
            "page": page_num
        })

    return tx_list

# ============================================================
# TEST WITH DATA FROM YOUR FILE (Source 22)
# ============================================================

# This replicates exactly how the text appears in your Source 22
raw_text_sample = """
"07 Mar
","CDT CASH DEPOSIT
","0000004470
",,"1,000.00
","1,000.00
"
"09 Mar
","DUITNOW QR P2P CR
 RHBQR000000
 ASPIYAH BINTI DARTO SUMIJO
 QR Payment","0000007440
",,"540.00
","1,528.00
"
"""

# Run Parser
transactions = parse_transactions_rhb(raw_text_sample, page_num=1)

# Check Output
if not transactions:
    print("No transactions found! Check regex pattern.")
else:
    print(f"{'DATE':<12} | {'BALANCE':<10} | {'DESCRIPTION'}")
    print("-" * 80)
    for tx in transactions:
        print(f"{tx['date']:<12} | {tx['balance']:<10.2f} | {tx['description'][:40]}...")
