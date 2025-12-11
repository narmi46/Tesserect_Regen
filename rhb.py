import regex as re

def parse_transactions_rhb(text, page_num, year=2025):
    """
    Parses RHB transactions, automatically detecting if the text is in the 
    standard line-by-line format or the fragmented CSV block format.
    """
    
    # ==========================================================
    # DETECT FORMAT: Check for CSV-style delimiters
    # ==========================================================
    if '","' in text and re.search(r'\d{2}-\d{2}-\d{4}', text):
        return _parse_rhb_csv_block(text, page_num)
    else:
        # Fallback to your existing line-by-line logic (Function A/C from previous code)
        # For this example, I will return an empty list or you can paste your old logic here.
        # print(f"Page {page_num}: Standard format detected (not CSV).")
        return [] 

def _parse_rhb_csv_block(text, page_num):
    """
    Internal helper to parse the fragmented CSV blocks found in newer/export-style RHB PDFs.
    """
    transactions = []
    
    # 1. CLEANUP: 
    # Remove newlines to merge broken fields (e.g. Branch on one line, Desc on next)
    clean_text = text.replace("\n", " ").replace("\r", "")
    
    # 2. NORMALIZE SEPARATORS:
    # The PDF often contains ",," for empty columns (e.g., empty debit or credit).
    # We replace ",," with ",""," to ensure the split works consistently.
    # We do this twice to catch consecutive empty columns if any.
    clean_text = clean_text.replace(",,", ',"",').replace(",,", ',"",')
    
    # 3. SPLIT INTO ROWS:
    # Split by looking for the Date pattern "DD-MM-YYYY" at the start of a CSV field.
    # We use a lookahead (?=...) to keep the date in the string.
    # Pattern explanation: (?=" matches start of quote, then date, then end quote
    row_pattern = r'(?="\d{2}-\d{2}-\d{4}",")'
    rows = re.split(row_pattern, clean_text)
    
    for row in rows:
        row = row.strip()
        if not row:
            continue
            
        # 4. PARSE COLUMNS
        # Now we can safely split by '","' because we normalized the empty fields.
        parts = row.split('","')
        
        # We need at least basic fields. 
        # Usually: [Date, Branch, Desc, ..., RefNum, Dr, Cr, Balance]
        if len(parts) < 5:
            continue
            
        try:
            # --- EXTRACT ---
            # Date is always first
            raw_date = parts[0].replace('"', '').strip()
            
            # [cite_start]Balance is always last [cite: 10]
            raw_bal = parts[-1].replace('"', '').replace(',', '').strip()
            
            # Credit is second to last
            raw_cr = parts[-2].replace('"', '').replace(',', '').strip()
            
            # Debit is third to last
            raw_dr = parts[-3].replace('"', '').replace(',', '').strip()
            
            # RefNum is fourth to last?
            # Description is everything between Branch (index 1) and RefNum
            # Let's dynamically join the middle parts as description
            branch = parts[1]
            desc_parts = parts[2:-3] # Everything between Branch and Debit/Cr/Bal
            full_desc = f"{branch} " + " ".join(desc_parts).replace('"', '')
            
            # --- CLEAN NUMBERS ---
            # [cite_start]Handle RHB's trailing minus sign for negative balances (e.g. "770,138.57-") [cite: 10]
            if raw_bal.endswith("-"):
                balance = -float(raw_bal[:-1])
            else:
                balance = float(raw_bal) if raw_bal else 0.0
                
            debit = float(raw_dr) if raw_dr and raw_dr != "-" else 0.0
            credit = float(raw_cr) if raw_cr and raw_cr != "-" else 0.0
            
            # --- REFORMAT DATE ---
            # DD-MM-YYYY -> YYYY-MM-DD
            if "-" in raw_date:
                dd, mm, yyyy = raw_date.split("-")
                iso_date = f"{yyyy}-{mm}-{dd}"
            else:
                iso_date = raw_date # Fallback

            # --- APPEND ---
            transactions.append({
                "date": iso_date,
                "description": " ".join(full_desc.split()), # Remove extra whitespace
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "page": page_num
            })
            
        except Exception as e:
            # Skip noise/header rows that don't match the structure
            continue
            
    return transactions
