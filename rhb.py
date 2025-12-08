import re
import json
import csv
from datetime import datetime

# ============================================================
#                REGEX PATTERNS (OLD & NEW FORMAT)
# ============================================================

PATTERN_RHB_NEW = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+"
    r"(\d{3})\s+"
    r"(.+?)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2}|-)\s+"
    r"([0-9,]+\.\d{2})([+-])"
)

PATTERN_RHB_OLD = re.compile(
    r"(\d{2}\s+\w{3})\s+"
    r"(.+?)\s+"
    r"(\d{6,12})\s+"
    r"([0-9,]+\.\d{2})\s+"
    r"(-?[0-9,]+\.\d{2})"
)

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}


# ============================================================
#                BANK STATEMENT PARSER CLASS
# ============================================================

class BankStatementParser:

    def __init__(self, text, page_num):
        self.text = text
        self.page = page_num
        self.year = self.detect_year()

    # Auto-detect year from PDF content
    def detect_year(self):
        m = re.search(r"(20\d{2})", self.text)
        if m:
            return int(m.group(1))
        return datetime.now().year

    def parse_amount(self, v):
        if not v or v == "-":
            return 0.00
        return float(v.replace(",", ""))

    def convert_old_date(self, raw_date):
        d, mon = raw_date.split()
        return f"{self.year}-{MONTH_MAP[mon]}-{d}"

    # --------------------------------------------------------
    # NEW FORMAT PARSER
    # --------------------------------------------------------
    def parse_new(self, line):
        m = PATTERN_RHB_NEW.search(line)
        if not m:
            return None

        date_raw, branch, desc, dr_raw, cr_raw, bal_raw, sign = m.groups()

        balance = self.parse_amount(bal_raw)
        if sign == "-":
            balance = -balance

        return {
            "date": date_raw,
            "description": desc.strip(),
            "debit": self.parse_amount(dr_raw),
            "credit": self.parse_amount(cr_raw),
            "balance": balance,
            "page": self.page
        }

    # --------------------------------------------------------
    # OLD FORMAT PARSER
    # --------------------------------------------------------
    def parse_old(self, line):
        m = PATTERN_RHB_OLD.search(line)
        if not m:
            return None

        date_raw, desc, cheque, amt_raw, bal_raw = m.groups()

        full_date = self.convert_old_date(date_raw)
        amount = self.parse_amount(amt_raw)
        balance = self.parse_amount(bal_raw)

        # Credit or debit? → heuristic
        if any(x in desc.upper() for x in ["DEPOSIT", "QR", "CR", "TRANSFER", "P2P"]):
            debit, credit = 0, amount
        else:
            debit, credit = amount, 0

        return {
            "date": full_date,
            "description": f"{desc.strip()} ({cheque})",
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "page": self.page
        }

    # --------------------------------------------------------
    # MAIN PARSER FOR ONE PAGE
    # --------------------------------------------------------
    def parse(self):
        results = []
        for raw_line in self.text.splitlines():
            line = raw_line.strip()

            # Try NEW format first
            tx = self.parse_new(line)
            if tx:
                results.append(tx)
                continue

            # Try OLD format
            tx = self.parse_old(line)
            if tx:
                results.append(tx)

        return results


# ============================================================
#    COMPATIBILITY WRAPPER (MATCHES YOUR app.py SIGNATURE)
# ============================================================

def parse_transactions_rhb(text, page_num):
    """
    MUST match signature in app.py:
        parse_transactions_rhb(text, page_num)
    """
    parser = BankStatementParser(text, page_num)
    return parser.parse()


if __name__ == "__main__":
    print("RHB parser loaded OK")
