import re
import fitz  # PyMuPDF

# ===========================
# REGEX PATTERNS
# ===========================
DATE_PATTERN = re.compile(r"^(?P<date>\d{2}/\d{2})\b")
AMOUNT_BAL = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

# Lines to ignore entirely
IGNORE_PREFIXES = [
    "PUBLIC BANK", "PUBLIC ISLAMIC", "PENYATA", "STATEMENT", "SUMMARY", "RINGKASAN",
    "TARIKH", "URUS", "TRANSACTION", "NO.", "PAGE", "MUKA", "TEL:", "DILINDUNGI",
    "PROTECTED", "ACCOUNT", "AKUAN", "HIGHLIGHTS", "TEGASAN",
]


# ===========================
# HELPER: Extract text blocks with coordinates
# ===========================
def extract_blocks(pdf):
    blocks = []
    for page_num, page in enumerate(pdf, start=1):
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = b
            txt = text.strip()
            if txt:
                blocks.append({
                    "page": page_num,
                    "x": x0,
                    "y": y0,
                    "text": txt
                })
    return blocks


# ===========================
# HELPER: Group lines by Y-axis into true rows
# ===========================
def group_rows(blocks, tolerance=3):
    rows = []
    current_row = []
    last_y = None

    blocks = sorted(blocks, key=lambda b: (b["page"], b["y"], b["x"]))

    for b in blocks:
        if last_y is None or abs(b["y"] - last_y) < tolerance:
            current_row.append(b)
        else:
            rows.append(current_row)
            current_row = [b]
        last_y = b["y"]

    if current_row:
        rows.append(current_row)

    return rows


# ===========================
# HELPER: Combine row blocks L→R
# ===========================
def row_to_text(row):
    row = sorted(row, key=lambda b: b["x"])
    return " ".join(b["text"] for b in row)


# ===========================
# MAIN PARSER (REPLACES OLD parse_transactions_pbb)
# ===========================
def parse_transactions_pbb(pdf_obj, year="2025"):
    """
    pdf_obj = PyMuPDF document object (fitz.open)
    Returns list of transactions
    """

    # -------- Extract Raw Rows --------
    blocks = extract_blocks(pdf_obj)
    grouped = group_rows(blocks)

    processed_rows = []
    for row in grouped:
        line = row_to_text(row)

        # Skip useless header/footer lines
        if any(line.upper().startswith(p) for p in IGNORE_PREFIXES):
            continue

        processed_rows.append(line)


    # -------- Assemble Multi-line Transactions --------
    tx = []
    current_date = None
    desc = ""
    prev_balance = None

    for line in processed_rows:
        # Detect the start of a new transaction
        date_match = DATE_PATTERN.match(line)
        amount_match = AMOUNT_BAL.search(line)

        if date_match:
            # Start new transaction block
            if current_date and desc:
                # Incomplete transaction without amount → skip
                desc = ""

            current_date = date_match.group("date")
            desc = line[len(current_date):].strip()
            continue

        # Continuation line (IMEPS / GHL / DMS A3 etc.)
        if not amount_match:
            desc += " " + line.strip()
            continue

        # When amount/balance detected → finalize this transaction
        amount = float(amount_match.group("amount").replace(",", ""))
        balance = float(amount_match.group("balance").replace(",", ""))

        # Determine debit/credit
        debit = credit = 0.0
        if prev_balance is not None:
            if balance < prev_balance:
                debit = amount
            else:
                credit = amount
        else:
            # fallback logic
            if "CR" in desc.upper():
                credit = amount
            else:
                debit = amount

        # Format ISO date
        if current_date:
            dd, mm = current_date.split("/")
            iso_date = f"{year}-{mm}-{dd}"
        else:
            iso_date = f"{year}-01-01"

        # Store transaction
        tx.append({
            "date": iso_date,
            "description": desc.strip(),
            "debit": debit,
            "credit": credit,
            "balance": balance
        })

        prev_balance = balance
        desc = ""  # Reset

    return tx
