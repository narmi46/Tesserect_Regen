# banks.py

from maybank import parse_transactions_maybank
from public_bank import parse_transactions_pbb
from rhb import parse_transactions_rhb
from cimb import parse_transactions_cimb
from bank_islam import parse_bank_islam


def detect_bank_by_text(text: str):
    """
    Lightweight bank detection for preview + auto-detect mode.
    """
    t = text.upper()

    if "CIMB" in t:
        return "cimb"

    if "MAYBANK" in t or "MBB" in t:
        return "maybank"

    if "PUBLIC BANK" in t or "PBB" in t:
        return "pbb"

    if "RHB" in t:
        return "rhb"

    if "BANK ISLAM" in t or "BIMB" in t:
        return "bank_islam"

    return "unknown"


def parse_page_by_bank(text, page_obj, page_num, bank_hint, default_year, source_file):
    """
    Returns (transactions, bank_name)
    This is the unified parser router.
    """

    # -------------------------------
    # 1. Manual Bank Selection
    # -------------------------------
    if bank_hint == "maybank":
        return parse_transactions_maybank(text, page_num, default_year), "Maybank"

    if bank_hint == "pbb":
        return parse_transactions_pbb(text, page_num, default_year), "Public Bank (PBB)"

    if bank_hint == "rhb":
        return parse_transactions_rhb(text, page_num), "RHB Bank"

    if bank_hint == "cimb":
        return parse_transactions_cimb(page_obj, page_num, source_file), "CIMB Bank"

    if bank_hint == "bank_islam":
        return parse_bank_islam(text), "Bank Islam"

    # -------------------------------
    # 2. AUTO-DETECT MODE
    # -------------------------------
    detected = detect_bank_by_text(text)

    if detected == "cimb":
        return parse_transactions_cimb(page_obj, page_num, source_file), "CIMB Bank"

    if detected == "maybank":
        return parse_transactions_maybank(text, page_num, default_year), "Maybank"

    if detected == "pbb":
        return parse_transactions_pbb(text, page_num, default_year), "Public Bank (PBB)"

    if detected == "rhb":
        return parse_transactions_rhb(text, page_num), "RHB Bank"

    if detected == "bank_islam":
        return parse_bank_islam(text), "Bank Islam"

    # Unknown bank
    return [], "Unknown"
