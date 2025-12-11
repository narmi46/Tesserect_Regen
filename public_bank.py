import re
import fitz


DATE_PATTERN = re.compile(r"^(?P<date>\d{2}/\d{2})\b")
AMOUNT_BAL = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})$"
)

IGNORE_PREFIXES = [
    "PUBLIC BANK", "PUBLIC ISLAMIC BANK", "STATEMENT", "PENYATA",
    "SUMMARY", "RINGKASAN", "ACCOUNT", "NOMBOR", "MUKA",
    "PAGE", "URUS", "URUS NIAGA", "TRANSACTION", "TEL:",
]


def extract_blocks(doc):
    blocks = []
    for page_num, page in enumerate(doc, start=1):
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = b
            text = text.strip()
            if text:
                blocks.append({"page": page_num, "x": x0, "y": y0, "text": text})
    return blocks


def group_rows(blocks, tolerance=3):
    rows = []
    cur, last_y = [], None

    blocks = sorted(blocks, key=lambda b: (b["page"], b["y"], b["x"]))

    for b in blocks:
        if last_y is None or abs(b["y"] - last_y) < tolerance:
            cur.append(b)
        else:
            rows.append(cur)
            cur = [b]
        last_y = b["y"]

    if cur:
        rows.append(cur)

    return rows


def join_row(row):
    return " ".join(b["text"] for b in sorted(row, key=lambda b: b["x"]))


def parse_transactions_pbb(doc, year="2025"):

    blocks = extract_blocks(doc)
    grouped = group_rows(blocks)

    rows = []
    for r in grouped:
        line = join_row(r)
        if not any(line.upper().startswith(p) for p in IGNORE_PREFIXES):
            rows.append(line)

    tx, desc, current_date, prev_balance = [], "", None, None

    for line in rows:

        date_match = DATE_PATTERN.match(line)
        amount_match = AMOUNT_BAL.search(line)

        if date_match:
            current_date = date_match.group("date")
            desc = line[len(current_date):].strip()
            continue

        if not amount_match:
            desc += " " + line.strip()
            continue

        amount = float(amount_match.group("amount").replace(",", ""))
        balance = float(amount_match.group("balance").replace(",", ""))

        debit = credit = 0.0
        if prev_balance is not None:
            debit = amount if balance < prev_balance else 0.0
            credit = amount if balance > prev_balance else 0.0
        else:
            credit = amount if "CR" in desc.upper() else 0.0
            debit = amount if credit == 0 else 0.0

        dd, mm = current_date.split("/")
        iso = f"{year}-{mm}-{dd}"

        tx.append({
            "date": iso,
            "description": desc.strip(),
            "debit": debit,
            "credit": credit,
            "balance": balance
        })

        prev_balance = balance
        desc = ""

    return tx
