import re
from datetime import datetime

# ============================================================
# MODIFIED RHB PARSER (For CSV-style Text Block)
# ============================================================

# This regex is designed for the specific format in your file:
# "Date","Description (multi-line)", ... ,"Balance"
# It uses [\s\S]*? to capture descriptions that span multiple lines.
# References: [cite: 22, 38]
PATTERN_RHB_BLOCK = re.compile(
    r'"(\d{2}\s[A-Za-z]{3})",'       # Group 1: Date (e.g., "07 Mar")
    r'"([\s\S]*?)",'                 # Group 2: Description (greedy, captures newlines)
    r'.*?'                           # Non-greedy match for middle columns (Cheque, Debit, Credit)
    r'"(-?[\d,]+\.\d{2})"'           # Group 3: Balance (e.g., "1,528.00")
)

def parse_transactions_rhb(text, page_num, year="2024"):
    """
    Parses the RHB statement text block (CSV format).
    Args:
        text (str): The raw text content of the page.
        page_num (int): The current page number.
        year (str): The statement year (default "2024" based on source ).
    """
    tx_list = []
    
    # We use finditer on the whole text because descriptions contain newlines
    for match in PATTERN_RHB_BLOCK.finditer(text):
        date_raw, desc_raw, balance_raw = match.groups()

        # 1. Format Date: "07 Mar" -> "2024-03-07"
        try:
            # Parse "07 Mar"
            dt_obj = datetime.strptime(f"{date_raw} {year}", "%d %b %Y")
            full_date = dt_obj.strftime("%Y-%m-%d")
        except ValueError:
            full_date = date_raw # Fallback if parsing fails

        # 2. Clean Description
        # Remove newlines and extra spaces caused by the PDF layout 
        description = desc_raw.replace('\n', ' ').replace('  ', ' ').strip()

        # 3. Format Balance
        # Remove commas and convert to float
        balance = float(balance_raw.replace(",", ""))

        # 4. Construct Object
        # Note: Debit/Credit are set to 0.0 because the current regex 
        # focuses only on Date, Desc, and Balance as requested.
        tx_list.append({
            "date": full_date,
            "description": description,
            "debit": 0.0,   # Placeholder
            "credit": 0.0,  # Placeholder
            "balance": balance,
            "page": page_num,
        })

    return tx_list

# ============================================================
# EXAMPLE USAGE
# ============================================================

# Sample raw text from your Source 22
raw_text_sample = """
"07 Mar","CDT CASH DEPOSIT","0000004470",,"1,000.00","1,000.00"
"08 Mar","ANNUAL FEES
 DCARD I FEE","0000004960","12.00",,"988.00"
"09 Mar","DUITNOW QR P2P CR
 RHBQR000000
 ASPIYAH BINTI DARTO SUMIJO
 QR Payment","0000007440",,"540.00","1,528.00"
"""

# Run the parser
transactions = parse_transactions_rhb(raw_text_sample, page_num=1)

# Print results
print(f"{'DATE':<12} | {'BALANCE':<10} | {'DESCRIPTION'}")
print("-" * 60)
for tx in transactions:
    print(f"{tx['date']:<12} | {tx['balance']:<10.2f} | {tx['description'][:30]}...")
