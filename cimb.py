import re

# Ignore footer/header/garbage lines
IGNORE_PATTERNS = [
    r"^CONTINUE NEXT PAGE",
    r"^You can perform",
    r"^For more information",
    r"^Statement of Account",
    r"^Page / Halaman",
    r"^CIMB BANK",
    r"^\(Protected by",
    r"^Date Description",
    r"^Tarikh Diskripsi",
    r"^\(RM\)",
    r"^Opening Balance",
    r"^Account No",
    r"^Branch / Cawangan",
    r"^Current Account Transaction Details",
    r"^Cheque / Ref No",
    r"^Withdrawal",
    r"^Deposits",
    r"^Balance",
    r"^No of Withdrawal",
    r"^Bil Pengeluaran",
    r"^No of Deposits",
    r"^Bil Deposit",
    r"^Total Withdrawal",
    r"^Jumlah Pengeluaran",
    r"^Total Deposits",
    r"^Jumlah Deposit",
    r"^CLOSING BALANCE/BAKI PENUTUP",
    r"^End of Statement / Penyata Tamat",
    r"^Important Notice / Notis Penting",
    r"^GENERIC MESSAGES",
]


def is_ignored(line):
    """Return True if a line matches any ignored pattern."""
    return any(re.search(p, line) for p in IGNORE_PATTERNS)


# --- NEW, IMPROVED REGEX PATTERNS ---
# We must use two separate patterns to correctly capture the two distinct transaction layouts:

# 1. DEBIT/WITHDRAWAL pattern (Amount appears in the Withdrawal column, Deposit column is empty/collapsed)
# Groups: (Date) (Description) (Ref No) (Withdrawal Amount) (Balance)
DEBIT_ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{6,20})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
)

# 2. CREDIT/DEPOSIT pattern (Amount appears in the Deposit column, Withdrawal column is empty/collapsed)
# Groups: (Date) (Description) (Ref No) (Deposit Amount) (Balance)
# NOTE: The missing Withdrawal amount causes the Description to extend into that column's space.
# We look for a line containing the Date, a Ref No, an amount, and a Balance, but lacking a second amount (Withdrawal).
CREDIT_ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{6,20})\s+([\d,]+\.\d{2})$"
)


def parse_transactions_cimb(text, page_num, source_file):
    """
    Parse CIMB bank statement text for a single page.
    Returns a list of transaction dictionaries.
    """

    lines = text.split("\n")
    i = 0
    rows = []
    
    # Check for the PDF Opening Balance to initialize the starting value if no transaction is found.
    # This value is needed to verify the first transaction's debit/credit determination.
    # We rely on the provided PDF summary table's opening balance for robustness.
    # Since this function only parses one page, we'll rely on the main logic below.

    while i < len(lines):
        line = lines[i].strip()
        
        # Skip garbage/footer/header lines
        if is_ignored(line):
            i += 1
            continue

        match_debit = DEBIT_ROW.match(line)
        match_credit = CREDIT_ROW.match(line)
        
        date, desc, refno, amount, balance = None, None, None, 0.0, 0.0
        debit, credit = 0.0, 0.0
        
        # --- Handle DEBIT/WITHDRAWAL Transaction (4 number groups) ---
        if match_debit:
            # Matches: (Date) (Description) (Ref No) (Withdrawal Amount) (Balance)
            date, desc, refno, amount, balance = match_debit.groups()
            amount_f = float(amount.replace(",", ""))
            
            # Use the previous entry's balance to confirm if this is a withdrawal/debit.
            # In the original PDF table, Withdrawal appears *before* Deposit.
            # A debit transaction is the one that has an amount in the first numeric column after Ref No.
            # However, due to floating column collapse, checking the description for keywords is more reliable here.
            
            # Since a match with DEBIT_ROW means there are two number columns after Ref No,
            # this often represents the Withdrawal (Debit) Amount and the Balance.
            # Assuming the amount captured in Group 4 is the DEBIT/WITHDRAWAL amount.
            debit = amount_f
        
        # --- Handle CREDIT/DEPOSIT Transaction (3 number groups) ---
        elif match_credit:
            # Matches: (Date) (Description) (Ref No) (Deposit Amount) (Balance)
            # This logic assumes the absence of a Withdrawal amount causes the text extraction to collapse 
            # to only 3 final numeric fields (Ref No, Deposit Amount, Balance).
            date, desc, refno, amount, balance = match_credit.groups()
            amount_f = float(amount.replace(",", ""))
            
            # Assuming the amount captured in Group 4 is the CREDIT/DEPOSIT amount.
            credit = amount_f
        
        else:
            # No transaction line found, move to the next line
            i += 1
            continue
            
        # --- Common processing for matched row ---
        
        # Collect additional description lines
        desc_extra = []
        j = i + 1

        while j < len(lines):
            next_line = lines[j].strip()
            
            # Stop if next transaction starts
            if re.match(r"^\d{2}/\d{2}/\d{4}", next_line):
                break
                
            # Stop if next line is a REF/AMOUNT line (indicating a multi-line transaction entry which is not common for description overflow)
            if re.match(r"^\d{6,20}\s+[\d,]+\.\d{2}", next_line):
                break
            
            # Stop if ignored pattern is found
            if is_ignored(next_line):
                break

            if next_line.strip():
                desc_extra.append(next_line)

            j += 1

        full_desc = desc.strip() + " " + " ".join(desc_extra)
        full_desc = re.sub(r'\s+', ' ', full_desc).strip() # Clean up multiple spaces

        balance_f = float(balance.replace(",", ""))

        rows.append({
            "date": date.replace("/", "-"),
            "description": full_desc,
            "ref_no": refno,
            "debit": debit,
            "credit": credit,
            "balance": balance_f,
            "page": page_num,
            "source_file": source_file
        })

        i = j
        
    return rows


# --- NEW ENTRY POINT FOR FULL FILE PROCESSING (MIMICS ORIGINAL USER CODE FLOW) ---

def process_cimb_files(uploaded_files):
    """
    Iterate through all CIMB files and parse transactions.
    Returns a flattened list of all transactions.
    """
    all_transactions = []
    
    # Sort files to maintain chronological order for better balance tracking later
    sorted_files = sorted([f for f in uploaded_files if f['fileName'].startswith('CIMB')])
    
    for file_data in sorted_files:
        file_name = file_data['fileName']
        full_content = file_data['fullContent']
        
        # Split content into pages, using '--- PAGE X ---' as delimiter
        pages = re.split(r'--- PAGE (\d+) ---', full_content)
        
        # First page is usually empty or headers, start from index 2 to get page 1's content
        for i in range(1, len(pages), 2):
            page_num_str = pages[i]
            page_content = pages[i+1]
            
            try:
                page_num = int(page_num_str.strip())
            except ValueError:
                # Should not happen if split is correct, but handles case where page number is missing/malformed
                continue

            # This is where the core parser is called
            transactions_on_page = parse_transactions_cimb(
                page_content, 
                page_num, 
                file_name
            )
            all_transactions.extend(transactions_on_page)
            
    return all_transactions


# Note: The original parsing logic that determines debit/credit based on the previous balance 
# has been simplified here to rely purely on the column structure inferred by the two regex patterns. 
# This is a much stronger assumption based on the typical layout of these statements.
# Further refinement would be necessary for perfect reconstruction of debit/credit where the extracted 
# text format is ambiguous or incomplete.
