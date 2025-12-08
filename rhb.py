import regex as re
from datetime import datetime

def parse_transactions_rhb(text, page_num):
    """
    Parses RHB bank statement text, handling formats where spaces 
    between the date and other fields might be missing (e.g., '07Mar...').
    """
    lines = text.splitlines()
    transactions = []
    
    # Default year for date parsing (since the statement date format doesn't always include it)
    current_year = "2025" 

    skip_keywords = ['QRPayment', 'FundTransfer', 'pay', 'DuitQRP2PTransfer', 'TotalCount', 'IMPORTANT', 'AZLAN', 'Page']

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 1. Match Date Pattern: "07Mar" or "7Mar" followed by text
        # regex: Start -> 1-2 digits -> 3 letters -> space -> rest
        date_match = re.match(r'^(\d{1,2})([A-Za-z]{3})\s+(.+)', line)
        
        if date_match:
            day = date_match.group(1)
            month_str = date_match.group(2)
            rest = date_match.group(3)
            
            # Format Date: DD Mon -> YYYY-MM-DD (Assumes default year)
            try:
                date_obj = datetime.strptime(f"{day} {month_str} {current_year}", "%d %b %Y")
                full_date = date_obj.strftime("%Y-%m-%d")
            except ValueError:
                full_date = f"{day} {month_str}" # Fallback

            # 2. Parse the rest of the line (Description, Serial, Amount, Balance)
            parts = rest.split()
            
            # Logic: Find the Serial Number (usually 10 digits) to split Description and Amounts
            serial_idx = -1
            for idx, part in enumerate(parts):
                if len(part) == 10 and part.isdigit():
                    serial_idx = idx
                    break
            
            debit = 0.0
            credit = 0.0
            balance = 0.0
            description_main = ""

            if serial_idx != -1:
                # Case A: Standard Transaction with Serial No
                description_main = ' '.join(parts[:serial_idx])
                balance_str = parts[-1].replace(',', '')
                
                # The amount is usually between serial and balance
                amount_parts = parts[serial_idx + 1:-1]
                if amount_parts:
                    amount_val = float(amount_parts[0].replace(',', ''))
                    
                    # Determine Dr/Cr based on keywords
                    if 'CR' in description_main or 'DEPOSIT' in description_main.upper():
                        credit = amount_val
                    else:
                        debit = amount_val
                        
                balance = float(balance_str) if balance_str else 0.0
                
            else:
                # Case B: No Serial (e.g., Opening Balance, simple transfers)
                # Assume last item is balance
                if len(parts) > 1:
                    balance_str = parts[-1].replace(',', '')
                    description_main = ' '.join(parts[:-1])
                    try:
                        balance = float(balance_str)
                    except:
                        balance = 0.0

            # 3. Capture Beneficiary / Extra Details from subsequent lines
            beneficiary_lines = []
            j = i + 1
            while j < min(i + 5, len(lines)):
                next_line = lines[j].strip()
                
                # Stop if next line is a new date
                if re.match(r'^\d{1,2}[A-Za-z]{3}\s+', next_line):
                    break
                
                # Stop if empty or technical header
                if not next_line or any(k in next_line for k in skip_keywords) or re.match(r'^[A-Z0-9]{15,}$', next_line):
                    j += 1
                    continue

                beneficiary_lines.append(next_line)
                j += 1
            
            # Merge beneficiary info into description for the final output
            full_description = description_main
            if beneficiary_lines:
                full_description += " | " + " ".join(beneficiary_lines[:2])

            transactions.append({
                "date": full_date,
                "description": full_description,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })

        i += 1

    return transactions
