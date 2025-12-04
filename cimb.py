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
    # Use re.search for more flexibility, as headings might not start exactly at position 0
    return any(re.search(p, line) for p in IGNORE_PATTERNS)


# --- FIXED, UNIFIED REGEX PATTERN ---

# This pattern captures the most complex layout: Date, Description, Ref No, 
# then uses non-capturing groups (?:) to optionally match the Withdrawal column OR the Deposit column.
# The core columns of the original table:
# [1] Date | [2] Description | [3] Ref No | [4] Withdrawal (RM) | [5] Deposits (RM) | [6] Balance (RM)
#
# Pattern breakdown:
# G1: Date (\d{2}/\d{2}/\d{4})
# G2: Description (.+?)
# G3: Ref No (\d{6,20})
# G4 (Optional Debit Amount): (?:([\d,]+\.\d{2})\s+)?
# G5 (Optional Credit Amount): (?:([\d,]+\.\d{2})\s+)?
# G6: Balance ([\d,]+\.\d{2})
#
# Note: The PDF text collapses columns. The main pattern below relies on the transaction amount being either 
# the first numeric amount after the Ref No (Debit) OR the second (Credit).
# This pattern tries to match either [Withdrawal] [Balance] OR [Deposit] [Balance].
# It's challenging due to the possibility of one amount being misclassified as description text.

# The safest general pattern for CIMB's collapsed text data (based on typical OCR output):
# (Date) (Description) (Ref No) (Optional Amount 1 / Debit) (Optional Amount 2 / Credit) (Balance)
# Since they don't appear together, a single pattern with optional groups and conditional checks is necessary.

MAIN_CIMB_ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+"  # G1: Date
    r"(.+?)\s+"                 # G2: Description (non-greedy)
    r"(\d{6,20})\s+"            # G3: Ref No
    r"((?:[\d,]+\.\d{2}\s+)?)"  # G4: Optional Withdrawal Amount (and space)
    r"((?:[\d,]+\.\d{2}))"      # G5: The transaction Amount OR the Balance
    r"$"                        # End of line
)


# Reverting to the old structure and simplifying the regex further, relying on the actual PDF outputs:
# The cleanest output typically contains: Date, Description, Ref/Cheque, [Amount 1], [Amount 2]
# Amount 1 is Withdrawal, Amount 2 is Deposit, but only one is present, then the Balance.
# Since the format is messy, we'll try to find 3 numeric columns OR 4 numeric columns.

# DEBIT: [Date] [Desc] [Ref No] [Withdrawal] [Balance] (4 numeric groups total)
DEBIT_ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+"      # G1: Date
    r"(.+?)\s+"                      # G2: Description
    r"(\d{6,20})\s+"                # G3: Ref No
    r"([\d,]+\.\d{2})\s+"           # G4: Withdrawal Amount
    r"([\d,]+\.\d{2})"              # G5: Balance
    r"$"
)

# CREDIT: [Date] [Desc] [Ref No] [Deposit] [Balance] (3 numeric groups total: Ref No is complex, needs to be precise)
# In text output, Credit looks like: [Date] [Description] [Ref No] [Deposit Amount] [Balance]
# The description tends to swallow the empty withdrawal column space.
# We modify the description pattern to stop before the last three known fields.

CREDIT_ROW_ALT = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+"  # G1: Date
    r"(.+?)\s+"                  # G2: Description
    r"(\d{6,20})\s+"            # G3: Ref No
    r"([\d,]+\.\d{2})"          # G4: Deposit Amount
    r"$"
)


def parse_transactions_cimb(text, page_num, source_file):
    """
    Parse CIMB bank statement text for a single page.
    Returns a list of transaction dictionaries.
    """

    lines = text.split("\n")
    i = 0
    rows = []
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip garbage/footer/header lines
        if is_ignored(line):
            i += 1
            continue

        match_debit = DEBIT_ROW.match(line)
        match_credit = None
        
        date, desc, refno, amount, balance = None, None, None, '0.00', '0.00'
        debit, credit = 0.0, 0.0
        
        is_debit = False
        is_credit = False

        # --- Handle DEBIT/WITHDRAWAL Transaction (4 final numeric groups) ---
        if match_debit:
            # Matches: (Date) (Description) (Ref No) (Withdrawal Amount) (Balance)
            date, desc, refno, amount, balance = match_debit.groups()
            is_debit = True

        # --- If not a standard debit format, try the credit/collapsed format ---
        else:
            # Check if this line matches the structure of a Credit/Deposit when the Withdrawal column is empty.
            # We look for a pattern that suggests only one amount column (the deposit) and the balance.
            # To avoid the inherent ambiguity, we use the original Credit Row logic which relies on a specific line length.
            match_credit = CREDIT_ROW_ALT.match(line)
            
            if match_credit:
                # Matches: (Date) (Description) (Ref No) (Deposit Amount)
                # NOTE: This pattern is highly ambiguous. In the fixed logic below, we check if the extracted 'amount' is actually the 'balance'
                # by looking at the description content (which is complex). 
                # FOR SIMPLICITY AND TO AVOID THE OLD ERROR, we check if the description *doesn't* match the typical Debit/Withdrawal description.
                
                # A more reliable way for Credit parsing is necessary due to the collapsing columns.
                # However, for a quick fix based on the previous error:
                
                parts = line.split()
                if len(parts) >= 5 and re.match(r"\d{2}/\d{2}/\d{4}", parts[0]):
                    # If we find a line with 5 or more parts starting with date, 
                    # check if the 2nd last part is the Ref No, and the last part is the Balance.
                    
                    # This relies on the transaction description NOT containing extra periods or numbers that disrupt the split.
                    
                    try:
                        # Find the two numbers and the balance near the end of the line
                        last_numeric_group = [p for p in reversed(parts) if re.match(r"^[\d,]+\.\d{2}$", p)]
                        if len(last_numeric_group) == 2:
                            # It's a Credit, as the DEBIT_ROW check failed, but two numeric groups (Deposit & Balance) were found.
                            amount, balance = last_numeric_group[1], last_numeric_group[0]
                            is_credit = True
                            
                            # Re-extract date, description, refno 
                            date = parts[0]
                            # Find the Ref No which is the number before the amount
                            refno_index = parts.index(amount) - 1
                            if refno_index > 0 and re.match(r"\d{6,20}", parts[refno_index]):
                                refno = parts[refno_index]
                                desc_parts = parts[1:refno_index]
                                desc = " ".join(desc_parts)

                    except ValueError:
                        # If splitting/indexing fails, ignore the line
                        pass
        
        # If either a Debit or Credit pattern matched based on column positions
        if is_debit or is_credit:
            
            # Use the captured groups from the debit match, or the re-extracted parts for credit
            if is_debit:
                amount_f = float(amount.replace(",", ""))
                debit = amount_f
                credit = 0.0
                balance_f = float(balance.replace(",", ""))
                current_line_index = i
            
            elif is_credit and 'date' in locals():
                # Re-parse the amounts and balance for the credit entry 
                amount_f = float(amount.replace(",", ""))
                debit = 0.0
                credit = amount_f
                balance_f = float(balance.replace(",", ""))
                current_line_index = i
            
            else:
                # Fallback in case re-extraction for credit failed or variables were not set
                i += 1
                continue


            # --- Common processing: Capture extended description ---
            desc_extra = []
            j = current_line_index + 1

            while j < len(lines):
                next_line = lines[j].strip()
                
                # Stop if next transaction starts
                if re.match(r"^\d{2}/\d{2}/\d{4}", next_line):
                    break
                    
                # Stop if next line looks like a Ref No followed by an amount (start of a new line in a multi-line transaction entry, rare, or table header)
                if re.match(r"^[\d\w]+\s+[\d,]+\.\d{2}", next_line):
                    break
                
                # Stop if ignored pattern is found
                if is_ignored(next_line):
                    break

                if next_line.strip():
                    desc_extra.append(next_line)

                j += 1

            full_desc = desc.strip() + " " + " ".join(desc_extra)
            full_desc = re.sub(r'\s+', ' ', full_desc).strip() # Clean up multiple spaces

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
            
        else:
            # No transaction line found, move to the next line
            i += 1
            continue

    return rows


# --- NEW ENTRY POINT FOR FULL FILE PROCESSING (OPTIONAL, but useful for testing) ---

def process_cimb_files(uploaded_files):
    """
    Iterate through all CIMB files and parse transactions.
    Returns a flattened list of all transactions.
    """
    all_transactions = []
    
    # Simulate the logic from app.py
    sorted_files = sorted([f for f in uploaded_files if f['fileName'].startswith('CIMB')])
    
    for file_data in sorted_files:
        file_name = file_data['fileName']
        full_content = file_data['fullContent']
        
        # Split content into pages, using '--- PAGE X ---' as delimiter
        pages = re.split(r'--- PAGE (\d+) ---', full_content)
        
        for i in range(1, len(pages), 2):
            page_num_str = pages[i]
            page_content = pages[i+1]
            
            try:
                page_num = int(page_num_str.strip())
            except ValueError:
                continue

            transactions_on_page = parse_transactions_cimb(
                page_content, 
                page_num, 
                file_name
            )
            all_transactions.extend(transactions_on_page)
            
    return all_transactions
