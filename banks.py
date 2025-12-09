# banks.py

# Import individual bank parser modules
from maybank import parse_transactions_maybank
from public_bank import parse_transactions_pbb
from rhb import parse_transactions_rhb
from cimb import parse_transactions_cimb


def detect_bank_by_text(text: str):
    """
    Lightweight bank detection for preview or routing.
    """
    text_up = text.upper()

    if "CIMB" in text_up:
        return "cimb"
    if "MAYBANK" in text_up:
        return "maybank"
    if "PUBLIC BANK" in text_up or "PBB" in text_up:
        return "pbb"
    if "RHB" in text_up:
        return "rhb"

    return "unknown"


def parse_page_by_bank(text, page_obj, page_num, bank_hint, default_year, source_file):
    """
    Unifies all bank parsing logic into one place.
    """

    # If bank was explicitly selected
    if bank_hint == "maybank":
        return parse_transactions_maybank(text, page_num, default_year), "Maybank"
    if bank_hint == "pbb":
        return parse_transactions_pbb(text, page_num, default_year), "Public Bank (PBB)"
    if bank_hint == "rhb":
        return parse_transactions_rhb(text, page_num), "RHB Bank"
    if bank_hint == "cimb":
        return parse_transactions_cimb(page_obj, page_num, source_file), "CIMB Bank"

    # AUTO-DETECT MODE
    detected = detect_bank_by_text(text)

    if detected == "cimb":
        return parse_transactions_cimb(page_obj, page_num, source_file), "CIMB Bank"
    if detected == "maybank":
        return parse_transactions_maybank(text, page_num, default_year), "Maybank"
    if detected == "pbb":
        return parse_transactions_pbb(text, page_num, default_year), "Public Bank (PBB)"
    if detected == "rhb":
        return parse_transactions_rhb(text, page_num), "RHB Bank"

    return [], "Unknown"
