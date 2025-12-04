import re

def parse_float(value):
    """Converts string '1,234.56' to float 1234.56. Returns 0.0 if empty."""
    if not value:
        return 0.0
    clean_val = str(value).replace("\n", "").replace(" ", "").replace(",", "")
    if not re.match(r'^-?\d+(\.\d+)?$', clean_val):
        return 0.0
    return float(clean_val)

def clean_text(text):
    """Removes excess newlines from descriptions."""
    if not text:
        return ""
    return text.replace("\n", " ").strip()

def parse_transactions_cimb(page_obj, page_num, source_file):
    """
    Parses a single pdfplumber page object to extract CIMB transactions.
    Requires 'page_obj' (not just text string) to use extract_table().
    """
    transactions = []
    
    # extract_table uses the grid lines to identify columns
    table = page_obj.extract_table()
    
    if not table:
        return []

    for row in table:
        # CIMB Structure: [Date, Desc, Ref, Withdrawal, Deposit, Balance]
        if not row or len(row) < 6:
            continue
        
        # Skip headers
        first_col = str(row[0]).lower()
        if "date" in first_col or "tarikh" in first_col:
            continue

        # Handle Opening Balance
        if "opening balance" in str(row[1]).lower():
            transactions.append({
                "date": "",
                "description": "OPENING BALANCE",
                "ref_no": "",
                "debit": 0.0,
                "credit": 0.0,
                "balance": parse_float(row[5]),
                "page": page_num,
                "source_file": source_file
            })
            continue

        # Ensure valid balance exists
        if not row[5]:
            continue

        # Strict Column Mapping
        debit_val = parse_float(row[3])   # Col 3 is Withdrawal
        credit_val = parse_float(row[4])  # Col 4 is Deposit
        
        # Skip empty rows (sometimes descriptions spill over without money)
        if debit_val == 0.0 and credit_val == 0.0:
            continue

        tx = {
            "date": clean_text(row[0]),
            "description": clean_text(row[1]),
            "ref_no": clean_text(row[2]),
            "debit": debit_val,
            "credit": credit_val,
            "balance": parse_float(row[5]),
            "page": page_num,
            "source_file": source_file
        }
        transactions.append(tx)

    return transactions
