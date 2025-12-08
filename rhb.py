import regex as re
from datetime import datetime

def parse_transactions_rhb(text, page_num):
    """
    Parses RHB bank statement text using a stateful approach to handle
    multi-line descriptions and missing dates on page breaks.
    """
    lines = text.splitlines()
    transactions = []
    
    # Configuration
    current_year = "2024" # Set this to the statement year or pass it as an arg if possible
    skip_keywords = [
        'QRPayment', 'FundTransfer', 'pay', 'DuitQRP2PTransfer', 
        'TotalCount', 'IMPORTANT', 'AZLAN', 'Page', 'Statement Period',
        'Member of PIDM', 'All information', 'Kindly advise', 'Segala maklumat'
    ]
    
    # State variables
    last_valid_date = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines or obvious headers
        if not line or "Balance" in line and "Description" in line:
            i += 1
            continue

        # -------------------------------------------------------
        # 1. Attempt to find a Date (Start of new transaction)
        # -------------------------------------------------------
        # Pattern: Start of line -> 1-2 digits -> 3 letters (e.g., "7 Mar", "07Mar")
        date_match = re.match(r'^(\d{1,2})\s?([A-Za-z]{3})\s+(.+)', line)
        
        is_transaction_line = False
        current_date_str = None
        rest_of_line = ""

        if date_match:
            # We found a line starting with a date
            day = date_match.group(1)
            month_str = date_match.group(2)
            rest_of_line = date_match.group(3)
            
            try:
                # Parse date
                date_obj = datetime.strptime(f"{day} {month_str} {current_year}", "%d %b %Y")
                current_date_str = date_obj.strftime("%Y-%m-%d")
                last_valid_date = current_date_str
                is_transaction_line = True
            except ValueError:
                # False positive (e.g. text that looks like a date)
                is_transaction_line = False
        
        # -------------------------------------------------------
        # 2. Fallback: Check if line is a "Dateless" Transaction
        #    (Common at start of new pages or grouped dates)
        # -------------------------------------------------------
        elif last_valid_date:
            # Heuristic: Check for a 10-digit Serial Number in the line
            # This distinguishes a transaction line from a beneficiary description line
            if re.search(r'\s\d{10}\s', line):
                current_date_str = last_valid_date
                rest_of_line = line
                is_transaction_line = True

        # -------------------------------------------------------
        # 3. Process Transaction
        # -------------------------------------------------------
        if is_transaction_line and current_date_str:
            parts = rest_of_line.split()
            
            # Locate Serial Number (10 digits) to split Description vs Amounts
            serial_idx = -1
            for idx, part in enumerate(parts):
                # RHB serials are typically 10 digits
                if len(part) == 10 and part.isdigit():
                    serial_idx = idx
                    break
            
            debit = 0.0
            credit = 0.0
            balance = 0.0
            description_main = ""

            if serial_idx != -1:
                # Everything before serial is description
                description_main = ' '.join(parts[:serial_idx])
                
                # Everything after serial involves amounts
                # Structure usually: [Debit?, Credit?, Balance]
                amount_parts = parts[serial_idx + 1:]
                
                if amount_parts:
                    # The last item is usually the balance
                    balance_str = amount_parts[-1].replace(',', '')
                    try:
                        balance = float(balance_str)
                    except ValueError:
                        balance = 0.0
                    
                    # Items between serial and balance are the transaction amount
                    val_parts = amount_parts[:-1]
                    if val_parts:
                        amount_val = float(val_parts[0].replace(',', ''))
                        
                        # Logic to determine Debit vs Credit
                        # If the description contains "CR" or "DEPOSIT", it's usually Credit.
                        # However, RHB formatting is tricky. 
                        # A robust way is usually position, but text extraction kills position.
                        # We rely on keywords or the fact that debits usually come first in column order, 
                        # but here we just have a stream.
                        
                        # Heuristics for CR (Money In)
                        is_credit = False
                        if 'DEPOSIT' in description_main.upper(): is_credit = True
                        if 'TRF CR' in description_main.upper(): is_credit = True
                        if 'P2P CR' in description_main.upper(): is_credit = True
                        
                        if is_credit:
                            credit = amount_val
                        else:
                            debit = amount_val
            else:
                # No serial found (e.g. B/F Balance)
                # Assume the line ends with balance
                if len(parts) > 1:
                    description_main = ' '.join(parts[:-1])
                    try:
                        balance = float(parts[-1].replace(',', ''))
                    except ValueError:
                        balance = 0.0

            # ---------------------------------------------------
            # 4. Lookahead for Beneficiary / Extra Description
            # ---------------------------------------------------
            extra_desc = []
            j = i + 1
            while j < min(i + 6, len(lines)):
                next_line = lines[j].strip()
                
                # STOP if next line looks like a new date
                if re.match(r'^(\d{1,2})\s?([A-Za-z]{3})\s+', next_line):
                    break
                
                # STOP if next line has a serial number (likely a new dateless transaction)
                if re.search(r'\s\d{10}\s', next_line):
                    break

                # STOP if footer garbage
                if any(k in next_line for k in ['PIDM', 'All information', 'Page', 'Statement Period', 'rhbgroup']):
                    j += 1
                    continue
                
                # Skip technical codes
                if re.match(r'^[A-Z0-9]{15,}$', next_line):
                    j += 1
                    continue

                # It's likely valid description text
                extra_desc.append(next_line)
                j += 1
            
            # Combine description
            full_desc = description_main
            if extra_desc:
                # Filter out noise from extra_desc
                clean_extra = [x for x in extra_desc if x not in skip_keywords]
                if clean_extra:
                    full_desc += " | " + " ".join(clean_extra[:2])

            transactions.append({
                "date": current_date_str,
                "description": full_desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
            
            # Advance main loop past the beneficiary lines we just consumed
            # (Note: strictly we just processed them as description, so we shouldn't re-process them as main lines)
            # However, since they don't match date/serial patterns, the main loop would just skip them anyway.
            # But let's be safe.
            i = j - 1

        i += 1

    return transactions
