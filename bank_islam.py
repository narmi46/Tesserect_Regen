# bank_islam.py

import fitz  # PyMuPDF
import re
import pandas as pd

# ---------------------------
# REGEX
# ---------------------------

# A Bank Islam row always begins with dd/mm/yyyy
BANK_ISLAM_ROW_START = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}")

# General row pattern extracted from your working RHB logic:
BANK_ISLAM_PATTERN = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{4})\s+"         # date
    r"(\d{2}:\d{2}:\d{2})?\s*"             # optional time
    r"(.+?)\s+"                            # description
    r"([0-9,]+\.\d{2})\s+"                 # amount #1
    r"([0-9,]+\.\d{2})\s+"                 # amount #2
    r"([0-9,]+\.\d{2})$"                   # balance
)


# ---------------------------
# GROUP WORDS INTO ROWS
# ---------------------------
def group_words_into_rows(words, y_tolerance=3):
    rows = {}
    for w in words:
        x0, y0, x1, y1, text, *_ = w
        y_key = round(y1, 1)

        assigned = False
        for existing_y in list(rows.keys()):
            if abs(existing_y - y_key) <= y_tolerance:
                rows[existing_y].append(w)
                assigned = True
                break

        if not assigned:
            rows[y_key] = [w]

    return rows


# ---------------------------
# SORT WORDS LEFT → RIGHT
# ---------------------------
def row_to_text(row_words):
    row_words = sorted(row_words, key=lambda w: w[0])
    return " ".join([w[4] for w in row_words])


# ---------------------------
# PARSE SINGLE BANK ISLAM ROW
# ---------------------------
def parse_bank_islam_row(text, source_file, page):
    m = BANK_ISLAM_PATTERN.match(text)
    if not m:
        return None

    date_raw, time_raw, desc, amt1, amt2, balance_raw = m.groups()

    # Clean numbers
    a1 = float(amt1.replace(",", ""))
    a2 = float(amt2.replace(",", ""))
    balance = float(balance_raw.replace(",", ""))

    # --------------------------
    # Determine whether a1=debit or credit
    # --------------------------
    debit = credit = 0.0

    # Typical Bank Islam logic:
    if a1 > 0 and a2 == 0:
        debit = a1
    elif a2 > 0 and a1 == 0:
        credit = a2
    else:
        # fallback if both filled:
        text_u = desc.upper()
        if "CHARGE" in text_u or "DR" in text_u:
            debit = a1
        else:
            credit = a1

    return {
        "date": date_raw,
        "description": desc.strip(),
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "source_file": source_file,
        "page": page
    }


# ---------------------------
# MAIN PARSER FUNCTION
# Called from banks.py
# pdf_data = RAW PDF BYTES from Streamlit
# ---------------------------
def parse_bank_islam(pdf_data):
    """
    Receives RAW PDF BYTES (from Streamlit f.getvalue()).
    """
    if isinstance(pdf_data, (bytes, bytearray)):
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    elif isinstance(pdf_data, str):
        doc = fitz.open(pdf_data)
    else:
        raise TypeError(
            f"Bank Islam parser expected bytes or file path, got {type(pdf_data)}"
        )

    transactions = []

    for page_index, page in enumerate(doc, start=1):
        words = page.get_text("words")

        if not words:
            continue

        rows = group_words_into_rows(words)
        sorted_rows = [rows[y] for y in sorted(rows.keys())]

        for row in sorted_rows:
            text = row_to_text(row).strip()

            # Must start with dd/mm/yyyy
            if not BANK_ISLAM_ROW_START.match(text):
                continue

            parsed = parse_bank_islam_row(text, source_file="PDF", page=page_index)

            if parsed:
                transactions.append(parsed)

    return transactions
