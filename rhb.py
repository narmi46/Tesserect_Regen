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
    
    # Month name to number mapping
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Match lines starting with date pattern: DD Mon
        date_match = re.match(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.+)', line, re.IGNORECASE)
        
        if not date_match:
            i += 1
            continue
        
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).capitalize()
        month_num = month_map.get(month, '01')
        rest_of_line = date_match.group(3).strip()
        
        # Skip summary/header lines
        if any(skip in rest_of_line.upper() for skip in ['B/F BALANCE', 'C/F BALANCE', 'TOTAL COUNT']):
            i += 1
            continue
        
        # Collect description lines (description can span multiple lines)
        description_lines = [rest_of_line]
        
        # Look ahead for continuation lines (lines that don't start with a date)
        j = i + 1
        while j < len(lines):
            next_line = lines[j].strip()
            # If next line starts with a date or is empty, stop
            if not next_line or re.match(r'^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', next_line, re.IGNORECASE):
                break
            # If next line has numeric pattern at end (likely the amounts row), stop
            if re.search(r'\d+,?\d*\.?\d*\s*$', next_line):
                # This is likely the amounts line
                description_lines.append(next_line)
                j += 1
                break
            description_lines.append(next_line)
            j += 1
        
        # Join all description lines
        full_text = ' '.join(description_lines)
        
        # Extract numeric fields from the end
        # Pattern: Look for numbers with optional commas and decimals
        # Expected format: [Serial] [Debit] [Credit] Balance
        # Numbers can be: 1,000.00 or 1000.00 or 1,000 or 1000
        
        # Find all numbers in the line (including serial numbers like 0000004470)
        number_pattern = r'(\d+(?:,\d{3})*(?:\.\d{2})?)'
        numbers = re.findall(number_pattern, full_text)
        
        if len(numbers) < 1:
            i = j
            continue
        
        # Clean numbers (remove commas)
        numbers = [n.replace(',', '') for n in numbers]
        
        # The last number is always the balance
        balance = float(numbers[-1])
        
        # Initialize debit and credit
        debit = 0.0
        credit = 0.0
        
        # Determine description (everything except the numeric fields at the end)
        # Remove the numeric fields from the text to get clean description
        desc_text = full_text
        for num in numbers[-3:]:  # Remove last 3 numbers from description
            # Replace the number with empty string (but only once from the end)
            desc_text = re.sub(r'\b' + re.escape(num.replace('.', r'\.')) + r'\b\s*$', '', desc_text, count=1)
        
        description = ' '.join(desc_text.split()).strip()
        
        # Determine if transaction is debit or credit based on keywords
        desc_upper = description.upper()
        
        # Credit keywords
        credit_keywords = [
            'CR', 'CREDIT', 'DEPOSIT', 'INWARD', 'FUND TRF-CR', 
            'QR P2P CR', 'CASH DEPOSIT', 'CDT'
        ]
        
        # Debit keywords  
        debit_keywords = [
            'DR', 'DEBIT', 'WITHDRAWAL', 'FEES', 'FUND TRF-DR',
            'QR P2P DR', 'INSTANT TRF DR', 'MBK INSTANT TRF DR'
        ]
        
        # Check if it's clearly a credit or debit
        is_credit = any(kw in desc_upper for kw in credit_keywords)
        is_debit = any(kw in desc_upper for kw in debit_keywords)
        
        # Assign amount based on format
        if len(numbers) >= 4:
            # Format: serial debit credit balance
            try:
                debit = float(numbers[-3])
                credit = float(numbers[-2])
            except:
                pass
        elif len(numbers) == 3:
            # Format: serial amount balance
            amount = float(numbers[-2])
            if is_credit:
                credit = amount
            elif is_debit:
                debit = amount
            else:
                # Default: if no clear indicator, check description
                if ' DR' in desc_upper or desc_upper.endswith('DR'):
                    debit = amount
                else:
                    credit = amount
        elif len(numbers) == 2:
            # Format: amount balance
            amount = float(numbers[-2])
            if is_credit:
                credit = amount
            else:
                debit = amount
        
        # Format date as YYYY-MM-DD
        iso_date = f"{year}-{month_num}-{day}"
        
        # Only add if we have a valid description
        if description and description != '':
            transactions.append({
                "date": iso_date,
                "description": description,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
        
        i = j if j > i else i + 1
    
    return transactions
