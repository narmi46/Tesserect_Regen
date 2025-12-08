import regex as re
import json
from pathlib import Path

# ============================================================
# CONFIG / CONSTANTS
# ============================================================

KNOWN_TOKENS = [
    "CDT", "CASH", "DEPOSIT",
    "ANNUAL", "FEES",
    "DUITNOW", "QR", "P2P", "CR", "DR",
    "RPP", "INWARD", "INST", "TRF",
    "MBK", "INSTANT",
    "MYDEBIT", "FUND", "MB", "ATM",
    "WITHDRAWAL", "PAYMENT", "TRANSFER"
]

MONTH_MAP = {
    "Jan": "-01-", "Feb": "-02-", "Mar": "-03-",
    "Apr": "-04-", "May": "-05-", "Jun": "-06-",
    "Jul": "-07-", "Aug": "-08-", "Sep": "-09-",
    "Oct": "-10-", "Nov": "-11-", "Dec": "-12-"
}

# ============================================================
# TOKEN / DESCRIPTION HELPERS
# ============================================================

def split_tokens_glued(text: str) -> str:
    """
    Split glued tokens in the description based on KNOWN_TOKENS.
    Example: 'DUITNOWQRP2PCR' → 'DUITNOW QR P2P CR'
    """
    s = text
    result = []

    while s:
        matched = False
        for tok in sorted(KNOWN_TOKENS, key=len, reverse=True):
            if s.startswith(tok):
                result.append(tok)
                s = s[len(tok):]
                matched = True
                break
        if not matched:
            result.append(s[0])
            s = s[1:]

    out, buf = [], ""
    for p in result:
        if p in KNOWN_TOKENS:
            if buf:
                out.append(buf)
                buf = ""
            out.append(p)
        else:
            buf += p
    if buf:
        out.append(buf)

    return " ".join(out)


def fix_description(desc: str) -> str:
    if not desc:
        return desc
    desc = split_tokens_glued(desc)
    # separate letters and digits that are stuck together
    desc = re.sub(r"([A-Za-z])(\d)", r"\1 \2", desc)
    desc = re.sub(r"(\d)([A-Za-z])", r"\1 \2", desc)
    return " ".join(desc.split())


# ============================================================
# BALANCE-BASED DEBIT/CREDIT
# ============================================================

def compute_debit_credit(prev_balance, curr_balance):
    """
    Determine debit/credit from movement between balances.
    First transaction with unknown previous balance → (0.0, 0.0)
    """
    if prev_balance is None:
        return 0.0, 0.0

    if curr_balance < prev_balance:
        return round(prev_balance - curr_balance, 2), 0.0  # debit
    if curr_balance > prev_balance:
        return 0.0, round(curr_balance - prev_balance, 2)  # credit
    return 0.0, 0.0


# ============================================================
# REGEX PATTERNS
# ============================================================

# Regular transaction line
PATTERN_TX = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+"   # day + month e.g. 07Mar
    r"(.+?)\s+"                     # description (glued)
    r"(\d{6,12})\s+"                # serial number
    r"([0-9,]+\.\d{2})\s+"          # amount column (ignored for movement)
    r"([0-9,]+\.\d{2})$"            # balance
)

# B/F and C/F rows
PATTERN_BF_CF = re.compile(
    r"^(\d{1,2})([A-Za-z]{3})\s+(B/F BALANCE|C/F BALANCE)\s+([0-9,]+\.\d{2})$"
)


# ============================================================
# LINE PARSER
# ============================================================

def parse_line_rhb(line: str, page_num: int, year: int = 2024):
    """
    Parse a single glued-text line from RHB statement.
    Returns:
      - dict with type 'bf_cf' for B/F or C/F
      - dict with transaction fields for normal tx
      - None if line doesn't match anything interesting
    """
    line = line.strip()
    if not line:
        return None

    # Try B/F or C/F first
    m_bf = PATTERN_BF_CF.match(line)
    if m_bf:
        day, mon, kind, bal = m_bf.groups()
        date_fmt = f"{year}{MONTH_MAP.get(mon, '-01-')}{day.zfill(2)}"
        return {
            "type": "bf_cf",
            "kind": kind,  # "B/F BALANCE" or "C/F BALANCE"
            "date": date_fmt,
            "balance": float(bal.replace(",", "")),
            "page": page_num,
        }

    # Then normal tx line
    m_tx = PATTERN_TX.match(line)
    if not m_tx:
        return None

    day, mon, desc_raw, serial, amt1, amt2 = m_tx.groups()
    date_fmt = f"{year}{MONTH_MAP.get(mon, '-01-')}{day.zfill(2)}"

    desc_clean = fix_description(desc_raw)

    return {
        "type": "tx",
        "date": date_fmt,
        "description": desc_clean,
        "serial": serial,
        "raw_amount": float(amt1.replace(",", "")),   # informational only
        "balance": float(amt2.replace(",", "")),
        "page": page_num,
    }


# ============================================================
# PAGE PARSER (USES PREVIOUS BALANCE FOR CONTINUITY)
# ============================================================

def parse_page_rhb(text: str, page_num: int, prev_balance=None, year: int = 2024):
    """
    Parse one page of glued text.
    - prev_balance: closing balance from previous page (or None for first page)
    Returns:
      (tx_list, end_balance)
    """
    tx_list = []
    curr_prev_balance = prev_balance
    end_balance = prev_balance

    for raw_line in text.splitlines():
        parsed = parse_line_rhb(raw_line, page_num, year)
        if not parsed:
            continue

        # B/F / C/F handlers
        if parsed["type"] == "bf_cf":
            if parsed["kind"] == "B/F BALANCE":
                # starting balance for this page
                curr_prev_balance = parsed["balance"]
                end_balance = parsed["balance"]
            elif parsed["kind"] == "C/F BALANCE":
                # closing balance for this page
                end_balance = parsed["balance"]
            continue

        # Normal transaction
        if parsed["type"] == "tx":
            curr_balance = parsed["balance"]
            debit, credit = compute_debit_credit(curr_prev_balance, curr_balance)

            tx = {
                "date": parsed["date"],
                "description": parsed["description"],
                "serial": parsed["serial"],
                "raw_amount": round(parsed["raw_amount"], 2),
                "balance": round(curr_balance, 2),
                "debit": debit,
                "credit": credit,
                "page": page_num,
            }

            tx_list.append(tx)
            curr_prev_balance = curr_balance
            end_balance = curr_balance

    return tx_list, end_balance


# ============================================================
# PDF TEXT EXTRACTOR (GLUED TEXT)
# ============================================================

def extract_pages_glued_text(pdf_path: str):
    """
    Returns a list of glued-text strings, one per page.

    This example uses pdfplumber; adapt to whatever you're already using
    to get the glued text for each page.
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber is required for extract_pages_glued_text()")

    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # You probably already have your own "glue" logic.
            # For now, we just use page.extract_text().
            txt = page.extract_text() or ""
            pages_text.append(txt)
    return pages_text


# ============================================================
# FULL STATEMENT PARSER
# ============================================================

def parse_rhb_statement_pdf(pdf_path: str, year: int = 2024):
    """
    Main function:
    - Extract text per page
    - Parse each page (handling B/F & C/F)
    - Return list of transaction dicts
    """
    pages_text = extract_pages_glued_text(pdf_path)
    all_tx = []
    prev_balance = None

    for page_num, text in enumerate(pages_text, start=1):
        tx_list, prev_balance = parse_page_rhb(text, page_num, prev_balance, year)
        all_tx.extend(tx_list)

    # attach source_file field for each tx
    source_file = Path(pdf_path).name
    for tx in all_tx:
        tx["source_file"] = source_file

    return all_tx


# ============================================================
# CLI / JSON DUMP
# ============================================================

def export_rhb_statement_to_json(pdf_path: str, out_path: str = None, year: int = 2024):
    tx_list = parse_rhb_statement_pdf(pdf_path, year=year)
    if out_path is None:
        out_path = str(Path(pdf_path).with_suffix(".transactions.json"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tx_list, f, indent=4, ensure_ascii=False)
    return out_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python rhb_parser.py 3_March_removed.pdf [year]")
        raise SystemExit(1)

    pdf_path = sys.argv[1]
    year = int(sys.argv[2]) if len(sys.argv) >= 3 else 2024

    out_file = export_rhb_statement_to_json(pdf_path, year=year)
    print(f"Exported transactions to {out_file}")
