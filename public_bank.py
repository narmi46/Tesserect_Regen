import fitz  # PyMuPDF
import re
from datetime import datetime

def parse_transactions_rhb(pdf_path_or_page, page_num, year=2024):
    """
    Parses RHB Bank transactions using PyMuPDF for better text extraction.
    
    Args:
        pdf_path_or_page: Either a file path string or a fitz.Page object
        page_num: Page number for reference
        year: Year for the transactions
    """
    transactions = []
    
    # Month mapping
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    
    # Get the page object
    if isinstance(pdf_path_or_page, str):
        doc = fitz.open(pdf_path_or_page)
        page = doc[page_num - 1]
    else:
        page = pdf_path_or_page
    
    # Extract text with layout preservation
    text = page.get_text("text")
    lines = text.split('\n')
    
    # Also extract structured text for better parsing
    blocks = page.get_text("dict")["blocks"]
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Match transaction line: DD Mon DESCRIPTION...
        date_match = re.match(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.+)', line, re.IGNORECASE)
        
        if not date_match:
            i += 1
            continue
        
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).capitalize()
        month_num = month_map.get(month, '01')
        rest = date_match.group(3).strip()
        
        # Skip control lines
        if any(skip in rest for skip in ['B/F BALANCE', 'C/F BALANCE', 'Total Count']):
            i += 1
            continue
        
        # Parse the rest of the line
        # RHB Format: DESCRIPTION SERIAL DEBIT CREDIT BALANCE
        # OR: DESCRIPTION SERIAL AMOUNT BALANCE
        
        # Split into parts
        parts = rest.split()
        
        # Find all numeric values (amounts with optional commas and decimals)
        numbers = []
        desc_parts = []
        
        for part in parts:
            # Check if this is a number
            clean = part.replace(',', '')
            if re.match(r'^\d+(\.\d{2})?$', clean):
                numbers.append(float(clean))
            else:
                desc_parts.append(part)
        
        if len(numbers) < 1:
            i += 1
            continue
        
        # Get balance (always last number)
        balance = numbers[-1]
        
        # Build description
        description = ' '.join(desc_parts)
        
        # Look ahead for continuation lines
        j = i + 1
        continuation_lines = []
        while j < len(lines) and j < i + 10:
            next_line = lines[j].strip()
            
            # Stop if we hit another date line
            if re.match(r'^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', next_line, re.IGNORECASE):
                break
            
            # Stop on empty lines
            if not next_line:
                j += 1
                continue
            
            # Stop on table headers
            if any(h in next_line for h in ['Date', 'Tarikh', 'Description', 'Debit', 'Credit', 'Balance', '---']):
                break
            
            # Stop if this line is all numbers (shouldn't happen but safety check)
            if re.match(r'^[\d,.\s]+$', next_line):
                j += 1
                continue
            
            # Add as continuation
            continuation_lines.append(next_line)
            j += 1
        
        # Combine description with continuations
        if continuation_lines:
            full_desc = description + ' ' + ' '.join(continuation_lines)
        else:
            full_desc = description
        
        full_desc = ' '.join(full_desc.split()).strip()
        
        # Determine debit/credit
        debit = 0.0
        credit = 0.0
        
        # Analyze based on number of amounts found
        if len(numbers) >= 4:
            # Format: serial, debit, credit, balance
            debit = numbers[-3]
            credit = numbers[-2]
        elif len(numbers) >= 3:
            # Format: serial, amount, balance
            amount = numbers[-2]
            
            # Determine type based on keywords
            upper_desc = full_desc.upper()
            if any(kw in upper_desc for kw in ['CR', 'CREDIT', 'DEPOSIT', 'INWARD', 'CDT', 'P2P CR']):
                credit = amount
            elif any(kw in upper_desc for kw in ['DR', 'DEBIT', 'WITHDRAWAL', 'FEES', 'TRF DR']):
                debit = amount
            else:
                # Default logic
                if 'TRF DR' in upper_desc or upper_desc.endswith(' DR'):
                    debit = amount
                else:
                    credit = amount
        elif len(numbers) == 2:
            # Format: amount, balance
            amount = numbers[-2]
            upper_desc = full_desc.upper()
            
            if any(kw in upper_desc for kw in ['CR', 'CREDIT', 'DEPOSIT', 'INWARD']):
                credit = amount
            else:
                debit = amount
        
        # Format date
        iso_date = f"{year}-{month_num}-{day}"
        
        # Add transaction
        if full_desc:
            transactions.append({
                "date": iso_date,
                "description": full_desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
        
        # Move to next transaction
        i = j if j > i else i + 1
    
    return transactions
