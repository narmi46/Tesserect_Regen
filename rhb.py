import fitz  # PyMuPDF
import re

def parse_transactions_rhb(fitz_page, page_num, year=2024):
    """
    Parses RHB Bank transactions using PyMuPDF for reliable text extraction.
    
    Args:
        fitz_page: A fitz.Page object (PyMuPDF page)
        page_num: Page number for reference
        year: Year for the transactions (default 2024)
    
    Returns:
        List of transaction dictionaries
    """
    transactions = []
    
    # Month mapping
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    
    # Extract text
    text = fitz_page.get_text("text")
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Match transaction line: DD Mon DESCRIPTION...
        # Example: "07 Mar CDT CASH DEPOSIT 0000004470 1,000.00 1,000.00"
        date_match = re.match(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.+)', line, re.IGNORECASE)
        
        if not date_match:
            i += 1
            continue
        
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).capitalize()
        month_num = month_map.get(month, '01')
        rest = date_match.group(3).strip()
        
        # Skip control/summary lines
        skip_keywords = ['B/F BALANCE', 'C/F BALANCE', 'Total Count', 'TOTAL COUNT']
        if any(skip in rest for skip in skip_keywords):
            i += 1
            continue
        
        # Parse the rest of the line
        # Split into parts
        parts = rest.split()
        
        # Extract numbers (amounts with optional commas and decimals)
        numbers = []
        desc_parts = []
        
        for part in parts:
            # Remove commas and check if it's a number
            clean = part.replace(',', '')
            if re.match(r'^\d+(\.\d{2})?$', clean):
                numbers.append(float(clean))
            else:
                desc_parts.append(part)
        
        # Must have at least a balance
        if len(numbers) < 1:
            i += 1
            continue
        
        # Last number is always the balance
        balance = numbers[-1]
        
        # Build description from non-numeric parts
        description = ' '.join(desc_parts)
        
        # Look ahead for continuation lines (multi-line descriptions)
        j = i + 1
        continuation_lines = []
        
        while j < len(lines) and j < i + 10:  # Look max 10 lines ahead
            next_line = lines[j].strip()
            
            # Stop if we hit another transaction (starts with date)
            if re.match(r'^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', next_line, re.IGNORECASE):
                break
            
            # Skip empty lines
            if not next_line:
                j += 1
                continue
            
            # Stop on table headers or separators
            headers = ['Date', 'Tarikh', 'Description', 'Diskripsi', 'Cheque', 'Debit', 'Credit', 'Balance', 'Baki', '---']
            if any(h in next_line for h in headers):
                break
            
            # Stop if line is all numbers
            if re.match(r'^[\d,.\s]+$', next_line):
                j += 1
                continue
            
            # Add as continuation line
            continuation_lines.append(next_line)
            j += 1
        
        # Combine main description with continuation lines
        if continuation_lines:
            full_desc = description + ' ' + ' '.join(continuation_lines)
        else:
            full_desc = description
        
        # Clean up whitespace
        full_desc = ' '.join(full_desc.split()).strip()
        
        # Determine debit vs credit
        debit = 0.0
        credit = 0.0
        
        # Based on how many numbers we found
        if len(numbers) >= 4:
            # Format: serial, debit, credit, balance
            debit = numbers[-3]
            credit = numbers[-2]
            
        elif len(numbers) >= 3:
            # Format: serial, amount, balance
            amount = numbers[-2]
            
            # Determine type based on keywords in description
            upper_desc = full_desc.upper()
            
            # Credit indicators
            credit_keywords = ['CR', 'CREDIT', 'DEPOSIT', 'INWARD', 'CDT', 'P2P CR', 'FUND TRF-CR', 'FUND TRF CR']
            # Debit indicators
            debit_keywords = ['DR', 'DEBIT', 'WITHDRAWAL', 'FEES', 'TRF DR', 'P2P DR', 'FUND TRF-DR', 'FUND TRF DR']
            
            if any(kw in upper_desc for kw in credit_keywords):
                credit = amount
            elif any(kw in upper_desc for kw in debit_keywords):
                debit = amount
            else:
                # Fallback: check if description ends with DR
                if upper_desc.endswith(' DR') or 'TRF DR' in upper_desc:
                    debit = amount
                else:
                    credit = amount
                    
        elif len(numbers) == 2:
            # Format: amount, balance (no serial number)
            amount = numbers[-2]
            upper_desc = full_desc.upper()
            
            # Determine based on keywords
            if any(kw in upper_desc for kw in ['CR', 'CREDIT', 'DEPOSIT', 'INWARD']):
                credit = amount
            else:
                debit = amount
        
        # Format date as YYYY-MM-DD
        iso_date = f"{year}-{month_num}-{day}"
        
        # Add transaction if description is valid
        if full_desc and full_desc != '':
            transactions.append({
                "date": iso_date,
                "description": full_desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
        
        # Move index to after continuation lines
        i = j if j > i else i + 1
    
    return transactions
