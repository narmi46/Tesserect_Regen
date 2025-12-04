import re

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
    r"^CLOSING BALANCE",
    r"^End of Statement",
    r"^\" # Added to ignore source tags if present in raw text
]

def is_ignored(line):
    return any(re.search(p, line) for p in IGNORE_PATTERNS)

# Strict Money Pattern: Matches 1,234.56 or 50.00
# Enforces exactly 2 decimal places to avoid confusing Ref Nos (integers) with Money.
MONEY_PATTERN = r"(?<![\d.])\d{1,3}(?:,\d{3})*\.\d{2}(?![\d.])"

def parse_transactions_cimb(text, page_num, source_file):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    cleaned_rows = []
    buffer = ""
    
    # ----------------------------------------------
    # 1️⃣ MERGE SPLIT LINES INTO COMPLETE ROW BLOCKS
    # ----------------------------------------------
    for line in lines:
        if is_ignored(line):
            continue

        # Check for standard Transaction Date start
        is_date_row = re.search(r"\d{2}/\d{2}/\d{4}", line)
        
        # Check for Opening Balance start (special case, no date)
        is_opening_row = "Opening Balance" in line

        if is_date_row or is_opening_row:
            if buffer:
                cleaned_rows.append(buffer)
            buffer = line
        else:
            # Append to previous line to fix split descriptions
            buffer += " " + line

    # Append the last buffer remaining
    if buffer:
        cleaned_rows.append(buffer)

    final_data = []

    # ----------------------------------------------
    # 2️⃣ EXTRACT COLUMNS
    # ----------------------------------------------
    for row in cleaned_rows:
        # Clean up CSV artifacts if present (quotes)
        clean_row_text = row.replace('"', '').strip()

        # Find ALL strictly formatted money values in the row
        money_matches = re.findall(MONEY_PATTERN, clean_row_text)
        
        # --- CASE A: Opening Balance ---
        if "Opening Balance" in clean_row_text:
            if money_matches:
                # The only money value in an Opening Balance row is the balance itself
                balance = float(money_matches[0].replace(",", ""))
                final_data.append({
                    "date": "N/A", # Or set to Statement Date if available
                    "description": "OPENING BALANCE",
                    "ref_no": "",
                    "withdrawal": 0.0,
                    "deposit": 0.0,
                    "balance": balance,
                    "page": page_num,
                    "source_file": source_file
                })
            continue

        # --- CASE B: Standard Transaction ---
        # We need at least 2 money values (Amount + Balance) usually, 
        # or sometimes 1 if it's a weird row, but Balance is ALWAYS the last one.
        if not money_matches:
            continue

        # The LAST money match is ALWAYS the running Balance
        balance = float(money_matches[-1].replace(",", ""))
        
        # The SECOND TO LAST money match is the Transaction Amount (Withdrawal or Deposit)
        amount = 0.0
        if len(money_matches) >= 2:
            amount = float(money_matches[-2].replace(",", ""))

        # Extract Date
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", clean_row_text)
        date = date_match.group(1).replace("/", "-") if date_match else ""

        # Extract Ref No (Look for long integers, 5+ digits)
        # We exclude the numbers we just identified as money to avoid duplicates
        temp_text_for_ref = clean_row_text
        for m in money_matches:
            temp_text_for_ref = temp_text_for_ref.replace(m, "")
            
        refno_match = re.search(r"\b(\d{5,20})\b", temp_text_for_ref)
        ref_no = refno_match.group(1) if refno_match else ""

        # Extract Description
        # Remove Date, Ref, and Money from string to leave description
        description = clean_row_text
        if date_match: description = description.replace(date_match.group(1), "")
        if ref_no: description = description.replace(ref_no, "")
        for m in money_matches:
            description = description.replace(m, "")
        
        # Clean up description whitespace
        description = re.sub(r'\s+', ' ', description).strip()
        description = description.replace(" ,", "").replace(",,", "") # Clean CSV remnants

        # Determine if Withdrawal or Deposit based on logical file structure or column position
        # (Since text extraction loses column position, we infer by common sense or return Raw Amount)
        # Note: In raw text parsing without x-coordinates, distinguishing Deposit vs Withdrawal 
        # specifically often requires context. 
        # Here we return "amount" generic, or you can check if description contains "DEPOSIT" / "CREDIT".
        
        # Heuristic: If description contains "CREDIT" or "DEPOSIT", it's likely a deposit.
        # Otherwise treated as withdrawal for simple categorization, or stored as generic amount.
        is_deposit = False
        if "CREDIT" in description.upper() or "DEPOSIT" in description.upper() or "REMITTANCE CR" in description.upper():
            is_deposit = True

        final_data.append({
            "date": date,
            "description": description,
            "ref_no": ref_no,
            "withdrawal": 0.0 if is_deposit else amount,
            "deposit": amount if is_deposit else 0.0,
            "balance": balance,
            "page": page_num,
            "source_file": source_file
        })

    return final_data
