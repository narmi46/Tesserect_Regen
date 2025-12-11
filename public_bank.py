import fitz  # PyMuPDF
import re

# ---------------------------------------------------------
# PyMuPDF-based Public Bank Parser
# ---------------------------------------------------------

def parse_transactions_pbb(pdf_path_or_obj, page_num, year="2025"):
    """
    Parse Public Bank statement using PyMuPDF table detection.
    
    Args:
        pdf_path_or_obj: Either file path string or fitz.Document object
        page_num: Page number to parse (1-indexed)
        year: Default year for dates
    
    Returns:
        List of transaction dictionaries
    """
    
    # Open PDF if path provided
    if isinstance(pdf_path_or_obj, str):
        doc = fitz.open(pdf_path_or_obj)
        should_close = True
    else:
        doc = pdf_path_or_obj
        should_close = False
    
    try:
        page = doc[page_num - 1]  # PyMuPDF uses 0-index
        
        # Extract table with column detection
        tables = page.find_tables()
        
        if not tables or len(tables.tables) == 0:
            # Fallback: manual text extraction
            return parse_by_text_blocks(page, page_num, year)
        
        # Use first table found
        table = tables[0]
        
        transactions = []
        prev_balance = None
        
        for row in table.extract():
            # Skip empty rows
            if not row or len(row) < 4:
                continue
            
            # Expected columns: DATE | TRANSACTION | DEBIT | CREDIT | BALANCE
            # But Public Bank format is: DATE | TRANSACTION | DEBIT/CREDIT | BALANCE
            
            date_str = str(row[0]).strip()
            desc = str(row[1]).strip() if len(row) > 1 else ""
            
            # Last column is balance
            balance_str = str(row[-1]).strip()
            
            # Second-to-last might be amount
            amount_str = str(row[-2]).strip() if len(row) >= 3 else ""
            
            # Validate date format DD/MM
            if not re.match(r'^\d{2}/\d{2}$', date_str):
                # Check if it's "Balance B/F"
                if "balance" in date_str.lower() and "b/f" in desc.lower():
                    try:
                        prev_balance = parse_amount(balance_str)
                    except:
                        pass
                continue
            
            # Skip header rows
            if "TARIKH" in desc.upper() or "DATE" in desc.upper():
                continue
            
            # Parse amounts
            try:
                balance = parse_amount(balance_str)
            except:
                continue  # Skip if balance can't be parsed
            
            try:
                amount = parse_amount(amount_str)
            except:
                # Sometimes amount is in description
                amount_match = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2})', desc)
                if amount_match:
                    amount = parse_amount(amount_match.group(1))
                else:
                    continue  # Skip if no amount found
            
            # Calculate debit/credit from balance change
            debit = 0.0
            credit = 0.0
            
            if prev_balance is not None:
                if balance > prev_balance:
                    credit = amount  # Balance increased = money in
                elif balance < prev_balance:
                    debit = amount   # Balance decreased = money out
                else:
                    credit = amount  # No change (rare)
            else:
                # First transaction - use heuristics
                if "DR-" in desc.upper() or "CHRG" in desc.upper() or "PYMT" in desc.upper():
                    debit = amount
                else:
                    credit = amount
            
            # Format date
            dd, mm = date_str.split("/")
            iso_date = f"{year}-{mm}-{dd}"
            
            # Create transaction
            transactions.append({
                "date": iso_date,
                "description": clean_description(desc),
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num,
                "source_file": ""
            })
            
            prev_balance = balance
        
        return transactions
    
    finally:
        if should_close:
            doc.close()


def parse_by_text_blocks(page, page_num, year="2025"):
    """
    Fallback: Parse using text blocks with coordinate detection.
    Groups text by Y-coordinate to reconstruct table rows.
    """
    
    # Get text with bounding boxes
    blocks = page.get_text("dict")["blocks"]
    
    # Group text by Y-coordinate (same row)
    rows = {}
    
    for block in blocks:
        if "lines" not in block:
            continue
        
        for line in block["lines"]:
            y = round(line["bbox"][1])  # Y-coordinate (top)
            
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                
                x = span["bbox"][0]  # X-coordinate (left)
                
                if y not in rows:
                    rows[y] = []
                
                rows[y].append((x, text))
    
    # Sort rows by Y-coordinate, then sort text within row by X
    transactions = []
    prev_balance = None
    
    for y in sorted(rows.keys()):
        # Sort by X coordinate to get proper order
        row_texts = [text for x, text in sorted(rows[y], key=lambda item: item[0])]
        line = " ".join(row_texts)
        
        # Match transaction pattern: DATE AMOUNT BALANCE DESCRIPTION
        match = re.match(
            r'^(\d{2}/\d{2})\s+'
            r'(\d{1,3}(?:,\d{3})*\.\d{2})\s+'
            r'(\d{1,3}(?:,\d{3})*\.\d{2})'
            r'(.*)$',
            line
        )
        
        if not match:
            # Check for Balance B/F
            if re.match(r'^\d{2}/\d{2}\s+Balance\s+B/F', line):
                bal_match = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2})$', line)
                if bal_match:
                    prev_balance = parse_amount(bal_match.group(1))
            continue
        
        date_str = match.group(1)
        amount = parse_amount(match.group(2))
        balance = parse_amount(match.group(3))
        desc = match.group(4).strip()
        
        # Calculate debit/credit
        debit = 0.0
        credit = 0.0
        
        if prev_balance is not None:
            if balance > prev_balance:
                credit = amount
            elif balance < prev_balance:
                debit = amount
            else:
                credit = amount
        else:
            if "DR-" in desc.upper() or "CHRG" in desc.upper():
                debit = amount
            else:
                credit = amount
        
        # Format date
        dd, mm = date_str.split("/")
        iso_date = f"{year}-{mm}-{dd}"
        
        transactions.append({
            "date": iso_date,
            "description": clean_description(desc),
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "page": page_num,
            "source_file": ""
        })
        
        prev_balance = balance
    
    return transactions


def parse_amount(text):
    """Convert amount string to float"""
    clean = text.replace(",", "").replace(" ", "")
    return float(clean)


def clean_description(text):
    """Remove extra whitespace and unwanted characters"""
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
