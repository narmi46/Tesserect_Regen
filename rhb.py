import regex as re
from datetime import datetime

def parse_transactions_rhb(text, page_num, year=2024):
    """
    Parses RHB Bank transactions from the actual PDF format.
    
    Format example from PDF:
    07 Mar CDT CASH DEPOSIT 0000004470 1,000.00 1,000.00
    09 Mar DUITNOW QR P2P CR 0000007440 540.00 1,528.00
    RHBQR000000
    ASPIYAH BINTI DARTO SUMIJO
    QR Payment
    """
    transactions = []
    
    # Split text into lines
    lines = text.split('\n')
    
    # Month name to number mapping
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Match the exact RHB format: DD Mon DESCRIPTION SERIAL AMOUNT BALANCE
        # Pattern: starts with 1-2 digits, space, 3-letter month
        date_pattern = r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.+)'
        date_match = re.match(date_pattern, line, re.IGNORECASE)
        
        if not date_match:
            i += 1
            continue
        
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).capitalize()
        month_num = month_map.get(month, '01')
        rest_of_line = date_match.group(3).strip()
        
        # Skip summary/control lines
        skip_keywords = ['B/F BALANCE', 'C/F BALANCE', 'TOTAL COUNT', 'Total Count']
        if any(keyword in rest_of_line for keyword in skip_keywords):
            i += 1
            continue
        
        # Parse the rest of the line
        # Format: DESCRIPTION SERIAL_NUMBER DEBIT CREDIT BALANCE
        # Numbers at the end are: serial (10 digits), debit, credit, balance
        # Example: "CDT CASH DEPOSIT 0000004470 1,000.00 1,000.00"
        
        # Extract all numbers (including serial numbers and amounts)
        # Pattern matches: 10-digit numbers (serial) and decimal amounts
        parts = rest_of_line.split()
        
        # Find numeric values - looking for pattern like: 0000004470 1,000.00 1,000.00
        numeric_parts = []
        desc_parts = []
        
        for part in parts:
            clean_part = part.replace(',', '')
            # Check if it's a number (serial number or amount)
            if re.match(r'^\d+(\.\d{2})?$', clean_part):
                numeric_parts.append(clean_part)
            else:
                desc_parts.append(part)
        
        if len(numeric_parts) < 1:
            i += 1
            continue
        
        # Last number is balance
        balance = float(numeric_parts[-1])
        
        # Determine debit/credit based on number of numeric fields
        debit = 0.0
        credit = 0.0
        description = ' '.join(desc_parts)
        
        # RHB format analysis:
        # - If 3+ numbers: serial, amount, balance (OR serial, debit, credit, balance)
        # - If 2 numbers: amount, balance
        
        if len(numeric_parts) >= 3:
            # Could be: serial, debit, credit, balance OR serial, amount, balance
            if len(numeric_parts) >= 4:
                # serial, debit, credit, balance
                debit = float(numeric_parts[-3])
                credit = float(numeric_parts[-2])
            else:
                # serial, amount, balance - need to determine debit vs credit
                amount = float(numeric_parts[-2])
                
                # Check description for CR or DR keywords
                desc_upper = description.upper()
                if 'CR' in desc_upper or 'DEPOSIT' in desc_upper or 'INWARD' in desc_upper:
                    credit = amount
                elif 'DR' in desc_upper or 'WITHDRAWAL' in desc_upper or 'FEES' in desc_upper:
                    debit = amount
                else:
                    # Default logic: if description contains TRF DR or ends with DR = debit
                    if 'TRF DR' in desc_upper or desc_upper.endswith(' DR'):
                        debit = amount
                    else:
                        credit = amount
        
        elif len(numeric_parts) == 2:
            # amount, balance
            amount = float(numeric_parts[-2])
            desc_upper = description.upper()
            
            if 'CR' in desc_upper or 'DEPOSIT' in desc_upper or 'INWARD' in desc_upper:
                credit = amount
            else:
                debit = amount
        
        # Collect additional description lines (lines after the main line that don't start with a date)
        j = i + 1
        additional_desc = []
        while j < len(lines) and j < i + 5:  # Look ahead max 5 lines
            next_line = lines[j].strip()
            # Stop if we hit another transaction (starts with date)
            if re.match(r'^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', next_line, re.IGNORECASE):
                break
            # Stop if empty line
            if not next_line:
                j += 1
                continue
            # Stop if it's a header or table separator
            if any(kw in next_line for kw in ['Date', 'Tarikh', 'Description', 'Diskripsi', 'Cheque', 'Debit', 'Credit', 'Balance', '---']):
                break
            # Add to description if it looks like descriptive text (not numbers)
            if not re.match(r'^[\d,.\s]+$', next_line):
                additional_desc.append(next_line)
            j += 1
        
        # Combine main description with additional lines
        if additional_desc:
            full_description = f"{description} {' '.join(additional_desc)}"
        else:
            full_description = description
        
        # Clean up description
        full_description = ' '.join(full_description.split())
        
        # Format date as YYYY-MM-DD
        iso_date = f"{year}-{month_num}-{day}"
        
        # Only add valid transactions
        if full_description and full_description != '':
            transactions.append({
                "date": iso_date,
                "description": full_description,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
        
        # Move to next line after the additional description lines
        i = j if j > i else i + 1
    
    return transactions
