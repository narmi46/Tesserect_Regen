import re

# -----------------------------------------------------------
# Utility patterns
# -----------------------------------------------------------

IGNORE_PATTERNS = [
    r"^CONTINUE NEXT PAGE",
    r"^You can perform",
    r"^For more information",
    r"^Statement of Account",
    r"^Page / Halaman",
    r"^CIMB BANK",
    r"^\(Protected by",
    r"^Date",
    r"^Tarikh",
    r"^Description",
    r"^Diskripsi",
    r"^\(RM\)",
    r"^Account No",
    r"^Branch",
    r"^Current Account Transaction Details",
    r"^Cheque",
    r"^Withdrawal",
    r"^Deposits",
    r"^Balance",
    r"^No of Withdrawal",
    r"^No of Deposits",
    r"^Total Withdrawal",
    r"^Total Deposits",
    r"^CLOSING BALANCE",
    r"^End of Statement",
    r'^"',
]

DATE_RE = r"^(\d{2}/\d{2}/\d{4})"
MONEY_RE = r"\d{1,3}(?:,\d{3})*\.\d{2}"


def is_ignored(line):
    return any(re.match(p, line) for p in IGNORE_PATTERNS)


def extract_money(text):
    vals = re.findall(MONEY_RE, text)
    return [float(v.replace(",", "")) for v in vals]


def extract_date(text):
    m = re.search(DATE_RE, text)
    return m.group(1).replace("/", "-") if m else ""


def extract_ref_no(text, money_strings):
    temp = text
    for m in money_strings:
        temp = temp.replace(m, "")
    
    matches = re.findall(r"\b(\d{5,20})\b", temp)
    if not matches:
        return ""
    return sorted(matches, key=lambda x: (len(x), temp.rfind(x)))[-1]


def clean_description(text, date_str, ref, money_strings):
    d = text
    if date_str:
        d = d.replace(date_str.replace("-", "/"), "")
    if ref:
        d = d.replace(ref, "")
    
    for m in money_strings:
        d = d.replace(m, "")
    
    d = re.sub(r"\s+", " ", d).strip()
    return d


# -----------------------------------------------------------
# FIXED MAIN FUNCTION
# -----------------------------------------------------------

def parse_transactions_cimb(text, page_num, source_file):
    
    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    lines = [l for l in raw_lines if not is_ignored(l)]
    
    rows = []
    buffer = ""
    
    # -----------------------------------------------------------
    # Transaction line merging logic
    # -----------------------------------------------------------
    for line in lines:
        
        has_date = bool(re.search(DATE_RE, line))
        has_money = bool(re.search(MONEY_RE, line))
        
        if has_date:
            if buffer:
                rows.append(buffer)
            buffer = line
        else:
            buffer += " " + line
        
        # Transaction row complete once we see balance (typically last number)
        if len(re.findall(MONEY_RE, buffer)) >= 2 and not has_date:
            rows.append(buffer)
            buffer = ""
    
    if buffer:
        rows.append(buffer)
    
    # -----------------------------------------------------------
    # Parse rows into transaction objects
    # -----------------------------------------------------------
    
    tx_list = []
    prev_balance = None
    
    for row in rows:
        
        # Opening Balance
        if "Opening Balance" in row:
            money = extract_money(row)
            if not money:
                continue
            bal = money[-1]
            prev_balance = bal
            
            tx_list.append({
                "date": "",
                "description": "OPENING BALANCE",
                "ref_no": "",
                "debit": 0.0,
                "credit": 0.0,
                "balance": bal,
                "page": page_num,
                "source_file": source_file,
            })
            continue
        
        # Extract all money values
        money_strings = re.findall(MONEY_RE, row)
        money_vals = [float(m.replace(",", "")) for m in money_strings]
        
        if len(money_vals) < 1:
            continue
        
        # -----------------------------------------------------------
        # CRITICAL FIX: Handle cases with 3 money values
        # Format: [withdrawal, deposit, balance] OR [value1, value2, balance]
        # -----------------------------------------------------------
        
        date_str = extract_date(row)
        ref = extract_ref_no(row, money_strings)
        description = clean_description(row, date_str, ref, money_strings)
        
        withdrawal = 0.0
        deposit = 0.0
        balance = money_vals[-1]  # Balance is always the last value
        
        if prev_balance is None:
            # First transaction after opening balance
            if len(money_vals) >= 2:
                deposit = money_vals[-2]
            prev_balance = balance
        
        elif len(money_vals) == 3:
            # THREE values: withdrawal, deposit, balance
            # This handles the IBG CREDIT case with both withdrawal and deposit
            withdrawal = money_vals[0]
            deposit = money_vals[1]
            
            # Verify the calculation matches
            expected_balance = prev_balance - withdrawal + deposit
            if abs(expected_balance - balance) > 0.02:
                # If calculation doesn't match, determine by balance change
                balance_change = balance - prev_balance
                if balance_change < 0:
                    withdrawal = abs(balance_change)
                    deposit = 0.0
                else:
                    deposit = balance_change
                    withdrawal = 0.0
        
        elif len(money_vals) == 2:
            # TWO values: amount and balance
            amount = money_vals[0]
            
            # Determine if withdrawal or deposit based on balance change
            balance_change = balance - prev_balance
            
            # Check if withdrawal (balance decreased)
            if abs(balance_change + amount) < 0.02:
                withdrawal = amount
                deposit = 0.0
            # Check if deposit (balance increased)
            elif abs(balance_change - amount) < 0.02:
                withdrawal = 0.0
                deposit = amount
            else:
                # Fallback: Use keywords to determine transaction type
                upper = description.upper()
                
                withdrawal_keywords = [
                    "TR TO ", "DUITNOW TO", "JOMPAY", "CHQ PROCESSING",
                    "STAMP DUTY", "COMMISSION", "DEBIT ADVICE", "CLRG CHQ DR"
                ]
                
                deposit_keywords = [
                    "TR IBG", "IBG CREDIT", "REMITTANCE CR", "I-FUNDS TR FROM",
                    "CLRG CHQ RTN"
                ]
                
                is_withdrawal = any(kw in upper for kw in withdrawal_keywords)
                is_deposit = any(kw in upper for kw in deposit_keywords)
                
                if is_withdrawal and not is_deposit:
                    withdrawal = amount
                elif is_deposit and not is_withdrawal:
                    deposit = amount
                else:
                    # Final fallback: base on balance change
                    if balance_change < 0:
                        withdrawal = amount
                    else:
                        deposit = amount
        
        else:
            # Single value - treat as deposit by default
            deposit = money_vals[0]
        
        prev_balance = balance
        
        tx_list.append({
            "date": date_str,
            "description": description,
            "ref_no": ref,
            "debit": round(withdrawal, 2),
            "credit": round(deposit, 2),
            "balance": round(balance, 2),
            "page": page_num,
            "source_file": source_file,
        })
    
    return tx_list
