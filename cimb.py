# cimb.py  ← save this file

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
]


def is_ignored(line):
    """Return True if a line matches any ignored pattern."""
    return any(re.match(p, line) for p in IGNORE_PATTERNS)


# MAIN CIMB PATTERN (date + desc + ref + amount + balance)
MAIN_ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{6,12})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
)


def parse_transactions_cimb(text, page_num):
    """
    Parse CIMB bank statement text for a single page.
    Returns a list of transaction dictionaries.
    """

    lines = text.split("\n")
    i = 0
    rows = []
    previous_balance = None  # needed to detect debit vs credit

    while i < len(lines):
        line = lines[i].strip()

        match = MAIN_ROW.match(line)
        if match:

            date, desc, refno, amount, balance = match.groups()

            # Collect additional description lines
            desc_extra = []
            j = i + 1

            while j < len(lines):

                next_line = lines[j].strip()

                # stop if next transaction starts
                if re.match(r"^\d{2}/\d{2}/\d{4}", next_line):
                    break

                # ignore footer/header lines
                if not is_ignored(next_line) and next_line.strip():
                    # stop if next line is a REF line
                    if re.match(r"^\d{6,12}\s+[\d,]+\.\d{2}", next_line):
                        break
                    desc_extra.append(next_line)

                j += 1

            full_desc = desc + " " + " ".join(desc_extra)

            # Convert amounts
            amount_f = float(amount.replace(",", ""))
            balance_f = float(balance.replace(",", ""))

            # Determine debit/credit via balance direction
            if previous_balance is None:
                # First entry is ambiguous → treat as debit
                debit = amount_f
                credit = 0
            else:
                if balance_f > previous_balance:
                    credit = amount_f
                    debit = 0
                else:
                    debit = amount_f
                    credit = 0

            previous_balance = balance_f

            rows.append({
                "date": date.replace("/", "-"),
                "description": full_desc,
                "debit": debit,
                "credit": credit,
                "balance": balance_f,
                "page": page_num,
            })

            i = j
            continue

        i += 1

    return rows
