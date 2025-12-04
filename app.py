import streamlit as st
import pdfplumber
import json
import pandas as pd

# Import parsers
from maybank import parse_transactions_maybank
from public_bank import parse_transactions_pbb
from rhb import parse_transactions_rhb
from cimb import parse_transactions_cimb

# ---------------------------------------------------
# Streamlit Setup
# ---------------------------------------------------

st.set_page_config(page_title="Bank Statement Parser", layout="wide")
st.title("📄 Bank Statement Parser (Multi-File Support)")
st.write("Upload one or more bank statement PDFs to extract transactions.")

# ---------------------------------------------------
# Bank Selection
# ---------------------------------------------------

bank_choice = st.selectbox(
    "Select Bank Format",
    ["Auto-detect", "Maybank", "Public Bank (PBB)", "RHB Bank", "CIMB Bank"]
)

bank_hint = None
if bank_choice == "Maybank":
    bank_hint = "maybank"
elif bank_choice == "Public Bank (PBB)":
    bank_hint = "pbb"
elif bank_choice == "RHB Bank":
    bank_hint = "rhb"
elif bank_choice == "CIMB Bank":
    bank_hint = "cimb"

# ---------------------------------------------------
# File Upload
# ---------------------------------------------------

uploaded_files = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)
default_year = st.text_input("Default Year", "2025")

# ---------------------------------------------------
# Auto Detect Parsing Logic
# ---------------------------------------------------

def auto_detect_and_parse(text, page_obj, page_num, default_year="2025", **source_file_kwargs):
    """
    Tries all parsers. 
    Note: CIMB requires 'page_obj' (the pdfplumber page), others utilize 'text'.
    """
    source_file = source_file_kwargs.get("source_file", "AutoDetect")

    # 1. Check CIMB (Precise table check using page object)
    if "CIMB" in text or "cimb" in text.lower():
        if page_obj:
            tx = parse_transactions_cimb(page_obj, page_num, source_file)
            if tx: return tx

    # 2. Maybank
    tx = parse_transactions_maybank(text, page_num, default_year)
    if tx: return tx

    # 3. Public Bank
    tx = parse_transactions_pbb(text, page_num, default_year)
    if tx: return tx

    # 4. RHB
    tx = parse_transactions_rhb(text, page_num)
    if tx: return tx

    return []

# ---------------------------------------------------
# Main Processing
# ---------------------------------------------------

all_tx = []

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.write(f"Processing: **{uploaded_file.name}**")

        try:
            with pdfplumber.open(uploaded_file) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    
                    # Extract raw text for text-based parsers (Maybank/PBB/RHB)
                    text = page.extract_text() or ""
                    
                    # --- ROUTING LOGIC ---
                    tx = []

                    if bank_hint == "maybank":
                        tx = parse_transactions_maybank(text, page_num, default_year)

                    elif bank_hint == "pbb":
                        tx = parse_transactions_pbb(text, page_num, default_year)

                    elif bank_hint == "rhb":
                        tx = parse_transactions_rhb(text, page_num)

                    elif bank_hint == "cimb":
                        # UPDATED: Pass the 'page' object, not just text
                        tx = parse_transactions_cimb(page, page_num, uploaded_file.name)

                    else:
                        # Auto-detect: Pass both text and page object
                        tx = auto_detect_and_parse(
                            text=text, 
                            page_obj=page, 
                            page_num=page_num, 
                            default_year=default_year, 
                            source_file=uploaded_file.name
                        )

                    # Add to master list
                    if tx:
                        for t in tx:
                            t["source_file"] = uploaded_file.name
                        all_tx.extend(tx)
                        
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {e}")

# ---------------------------------------------------
# Display Results
# ---------------------------------------------------

if all_tx:
    st.subheader("Extracted Transactions")
    
    df = pd.DataFrame(all_tx)
    
    # Normalize columns
    cols = ["date", "description", "debit", "credit", "balance", "ref_no", "page", "source_file"]
    df = df[[c for c in cols if c in df.columns]]
    
    st.dataframe(df, use_container_width=True)

    # JSON Download
    json_data = json.dumps(all_tx, indent=4)
    st.download_button("Download JSON", json_data, file_name="transactions.json", mime="application/json")

    # CSV Download (Easier for Excel)
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv_data, file_name="transactions.csv", mime="text/csv")

else:
    if uploaded_files:
        st.warning("No transactions found. Check if the file format is supported.")
