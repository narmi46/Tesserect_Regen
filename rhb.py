import regex as re
from datetime import datetime

def parse_transactions_rhb(text, page_num, year=2024):
    """
    Parses RHB Bank transactions from standard tabular format.
    Handles both 2-digit and 4-digit year formats.
    """
    transactions = []
    
    # Split text into lines
    lines = text.split('\n')
    
    # Pattern to match transaction lines
    # Format: DD MMM Description ... Serial_No Debit Credit Balance
    # Example: 07 Mar CDT CASH DEPOSIT 0000004470 1,000.00 1,000.00
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Match lines starting with date pattern: DD Mon
        date_match = re.match(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', line, re.IGNORECASE)
        
        if not date_match:
            continue
        
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).capitalize()
        
        # Convert month name to number
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        month_num = month_map.get(month, '01')
        
        # Extract the rest of the line after date
        rest_of_line = line[date_match.end():].strip()
        
        # Split by whitespace to get fields
        parts = rest_of_line.split()
        
        if len(parts) < 2:
            continue
        
        # Find numeric fields (serial number, debit, credit, balance)
        # They typically appear at the end of the line
        numeric_fields = []
        description_parts = []
        
        for part in parts:
            # Check if this looks like a number (with or without commas)
            clean_part = part.replace(',', '')
            if re.match(r'^\d+\.?\d*$', clean_part) or part.startswith('0000'):
                numeric_fields.append(part)
            else:
                description_parts.append(part)
        
        # We need at least: serial_no, and balance (minimum)
        # Full format: serial_no, debit, credit, balance
        if len(numeric_fields) < 1:
            continue
        
        # Parse numeric fields
        try:
            # Last field is always balance
            balance_str = numeric_fields[-1].replace(',', '')
            balance = float(balance_str) if balance_str else 0.0
            
            # Handle negative balances (trailing minus sign)
            if len(numeric_fields) > 0 and numeric_fields[-1].endswith('-'):
                balance = -float(numeric_fields[-1][:-1].replace(',', ''))
            
            # If we have 4 numeric fields: serial, debit, credit, balance
            # If we have 3 numeric fields: serial, amount, balance (need to determine if debit or credit)
            # If we have 2 numeric fields: amount, balance
            
            debit = 0.0
            credit = 0.0
            
            if len(numeric_fields) >= 4:
                # Format: serial_no debit credit balance
                debit_str = numeric_fields[-3].replace(',', '')
                credit_str = numeric_fields[-2].replace(',', '')
                
                debit = float(debit_str) if debit_str and debit_str != '-' else 0.0
                credit = float(credit_str) if credit_str and credit_str != '-' else 0.0
                
            elif len(numeric_fields) == 3:
                # Format: serial_no amount balance
                # Determine if debit or credit based on description or balance change
                amount_str = numeric_fields[-2].replace(',', '')
                amount = float(amount_str) if amount_str else 0.0
                
                # Common credit keywords
                credit_keywords = ['CR', 'DEPOSIT', 'INWARD', 'FUND TRF-CR', 'QR P2P CR']
                debit_keywords = ['DR', 'WITHDRAWAL', 'FEES', 'FUND TRF-DR', 'QR P2P DR']
                
                desc_upper = ' '.join(description_parts).upper()
                
                if any(kw in desc_upper for kw in credit_keywords):
                    credit = amount
                elif any(kw in desc_upper for kw in debit_keywords):
                    debit = amount
                else:
                    # Default: if description contains "DR", it's debit, else credit
                    if ' DR' in desc_upper or desc_upper.endswith('DR'):
                        debit = amount
                    else:
                        credit = amount
            
            elif len(numeric_fields) == 2:
                # Format: amount balance (no serial number)
                amount_str = numeric_fields[0].replace(',', '')
                amount = float(amount_str) if amount_str else 0.0
                
                desc_upper = ' '.join(description_parts).upper()
                credit_keywords = ['CR', 'DEPOSIT', 'INWARD', 'FUND TRF-CR', 'QR P2P CR']
                
                if any(kw in desc_upper for kw in credit_keywords):
                    credit = amount
                else:
                    debit = amount
            
            # Build description
            description = ' '.join(description_parts)
            
            # Skip summary lines
            if 'TOTAL COUNT' in description.upper() or 'C/F BALANCE' in description.upper() or 'B/F BALANCE' in description.upper():
                continue
            
            # Format date as YYYY-MM-DD
            iso_date = f"{year}-{month_num}-{day}"
            
            transactions.append({
                "date": iso_date,
                "description": description,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
            
        except (ValueError, IndexError) as e:
            # Skip lines that can't be parsed
            continue
    
    return transactions
