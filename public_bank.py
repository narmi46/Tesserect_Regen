import re
import fitz  # PyMuPDF


# ===========================
# REGEX PATTERNS
# ===========================
DATE_PATTERN = re.compile(r"^(?P<date>\d{2}/\d{2})\b")
AMOUNT_BAL = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

IGNORE_PREFIXES = [
    "PUBLIC BANK", "PUBLIC ISLAMIC", "PENYATA", "STATEMENT",
    "RINGKASAN", "SUMMARY", "ACCOUNT", "NOMBOR", "MUKA",
    "PAGE", "TEL:", "DILINDUNGI", "PROTECTED", "HIGHLIGHTS",
    "TEGASAN", "DATE", "URUS NIAGA", "TRANSACTION",
]


# ===========================
# Extract blocks from PyMuPDF
# ===========================
def extract_blocks(doc):
    blocks = []

    for page_num, page in enumerate(doc, start=1):
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = b
            text = text.strip()
            if text:
                blocks.append({
                    "page": page_num,
                    "x": x0,
                    "y": y0,
                    "text": text,
                })

    return blocks


# ===========================
# Group blocks by Y-axis
# ===========================
def group_rows(blocks, tolerance=3):
    rows = []
    current = []
    last_y = None

    blocks = sorted(blocks, key=lambda b: (b["page"], b["y"], b["x"]))

    for b in blocks:
        if last_y is None or abs(b["y"] - last_y) < tolerance:
            current.append(b)
        else:
            rows.append(current)
            current = [b]
        last_y = b["y"]

    if current:
        rows.append(current)

    return rows


# ===========================
# Combine blocks L→R
# ===========================
def join_row(row):
    row = sorted(row, key=lambda b: b["x"])
    return " ".join(b["text"] for b in row)


# ===========================
# MAIN PARSER FOR PUBLIC BANK
# ===========================
def parse_transactions_pbb(doc, year="2025"):
    blocks = extract_blocks(doc)
    grouped = group_rows(blocks)

    cleaned_rows = []

    for row in grouped:
        txt = join_row(row)

        if any(txt.upper().startswith(p) for p in IGNORE_PREFIXES):
            continue

        cleaned_rows.append(txt)

    # --------------------------
    # Build transactions
    # --------------------------
    tx = []
    current_date = None
    desc = ""
    prev_balance = None

    for line in cleaned_rows:

        date_match = DATE_PATTERN.match(line)
        amount_match = AMOUNT_BAL.search(line)

        # A new date always starts a new transaction block
        if date_match:
            current_date = date_match.group("date")
            desc = line[len(current_date):].strip()
            continue

        # If no amount found -> continuation of description
        if not amount_match:
            desc += " " + line.strip()
            continue

        # Amount found → finalize transaction
        amount = float(amount_match.group("amount").replace(",", ""))
        balance = float(amount_match.group("balance").replace(",", ""))

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

        # Convert dd/mm → ISO yyyy-mm-dd
        if current_date:
            dd, mm = current_date.split("/")
            iso_date = f"{year}-{mm}-{dd}"
        else:
            iso_date = f"{year}-01-01"

        tx.append({
            "date": iso_date,
            "description": desc.strip(),
            "debit": debit,
            "credit": credit,
            "balance": balance
        })

        prev_balance = balance
        desc = ""  # reset

    return tx
