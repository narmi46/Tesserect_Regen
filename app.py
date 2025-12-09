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
# Session State
# ---------------------------------------------------
if "status" not in st.session_state:
    st.session_state.status = "idle"    # idle, running, stopped

if "results" not in st.session_state:
    st.session_state.results = []


# ---------------------------------------------------
# ASCII TABLE EXPORT FUNCTION
# ---------------------------------------------------
def dataframe_to_ascii(df):
    df_str = df.astype(str)
    col_widths = {col: max(df_str[col].map(len).max(), len(col)) for col in df_str.columns}

    separator = "+" + "+".join("-" * (col_widths[col] + 2) for col in df_str.columns) + "+"
    header = "|" + "|".join(f" {col.ljust(col_widths[col])} " for col in df_str.columns) + "|"

    rows = [
        "|" + "|".join(f" {str(val).ljust(col_widths[col])} " for col, val in row.items()) + "|"
        for _, row in df_str.iterrows()
    ]

    return "\n".join([separator, header, separator] + rows + [separator])


# ---------------------------------------------------
# Bank Selection Dropdown
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
# Auto-Detect Preview BEFORE Start Processing
# ---------------------------------------------------
if uploaded_files and bank_hint is None:
    st.subheader("🔍 Auto-Detect Preview (Before Processing)")

    for uploaded_file in uploaded_files:
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""

                detected_bank = "Unknown"

                if "CIMB" in text.upper():
                    detected_bank = "CIMB Bank"
                elif "MAYBANK" in text.upper():
                    detected_bank = "Maybank"
                elif "PUBLIC BANK" in text.upper() or "PBB" in text.upper():
                    detected_bank = "Public Bank (PBB)"
                elif "RHB" in text.upper():
                    detected_bank = "RHB Bank"

                st.info(f"📄 **{uploaded_file.name}** → 🏦 **Detected Bank: {detected_bank}**")

        except Exception as e:
            st.error(f"Error previewing {uploaded_file.name}: {e}")


# ---------------------------------------------------
# Start / Stop / Reset Controls
# ---------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("▶️ Start Processing"):
        st.session_state.status = "running"

with col2:
    if st.button("⏹️ Stop"):
        st.session_state.status = "stopped"

with col3:
    if st.button("🔄 Reset"):
        st.session_state.status = "idle"
        st.session_state.results = []
        st.rerun()

st.write(f"### ⚙️ Status: **{st.session_state.status.upper()}**")


# ---------------------------------------------------
# Auto-detect Parsing Function
# ---------------------------------------------------
def auto_detect_and_parse(text, page_obj, page_num, default_year="2025", **source_file_kwargs):

    source_file = source_file_kwargs.get("source_file", "AutoDetect")

    if "CIMB" in text.upper():
        tx = parse_transactions_cimb(page_obj, page_num, source_file)
        if tx:
            return tx, "CIMB Bank"

    tx = parse_transactions_maybank(text, page_num, default_year)
    if tx:
        return tx, "Maybank"

    tx = parse_transactions_pbb(text, page_num, default_year)
    if tx:
        return tx, "Public Bank (PBB)"

    tx = parse_transactions_rhb(text, page_num)
    if tx:
        return tx, "RHB Bank"

    return [], "Unknown"


# ---------------------------------------------------
# MAIN PROCESSING
# ---------------------------------------------------
all_tx = []

if uploaded_files and st.session_state.status == "running":

    bank_display_box = st.empty()

    for uploaded_file in uploaded_files:

        st.write(f"### 🗂 Processing File: **{uploaded_file.name}**")

        try:
            with pdfplumber.open(uploaded_file) as pdf:

                for page_num, page in enumerate(pdf.pages, start=1):

                    if st.session_state.status == "stopped":
                        st.warning("⏹️ Processing stopped by user.")
                        break

                    text = page.extract_text() or ""
                    tx = []
                    detected_bank = "Auto"

                    bank_display_box.info(f"🔍 Detecting bank for Page {page_num}...")

                    if bank_hint == "maybank":
                        detected_bank = "Maybank"
                        tx = parse_transactions_maybank(text, page_num, default_year)

                    elif bank_hint == "pbb":
                        detected_bank = "Public Bank (PBB)"
                        tx = parse_transactions_pbb(text, page_num, default_year)

                    elif bank_hint == "rhb":
                        detected_bank = "RHB Bank"
                        tx = parse_transactions_rhb(text, page_num)

                    elif bank_hint == "cimb":
                        detected_bank = "CIMB Bank"
                        tx = parse_transactions_cimb(page, page_num, uploaded_file.name)

                    else:
                        tx, detected_bank = auto_detect_and_parse(
                            text=text,
                            page_obj=page,
                            page_num=page_num,
                            default_year=default_year,
                            source_file=uploaded_file.name
                        )

                    bank_display_box.success(f"🏦 Processing: **{detected_bank}** (Page {page_num})")

                    if tx:
                        for t in tx:
                            t["source_file"] = uploaded_file.name
                            t["bank"] = detected_bank

                        all_tx.extend(tx)

        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {e}")

    st.session_state.results = all_tx


# ---------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------
if st.session_state.results:
    st.subheader("📊 Extracted Transactions")

    df = pd.DataFrame(st.session_state.results)

    expected_cols = ["date", "description", "debit", "credit", "balance", "page", "bank", "source_file"]
    df = df[[c for c in expected_cols if c in df.columns]]

    st.dataframe(df, use_container_width=True)

    # JSON Export
    json_data = json.dumps(df.to_dict(orient="records"), indent=4)
    st.download_button("⬇️ Download JSON", json_data, file_name="transactions.json", mime="application/json")

    # TXT Export
    ascii_txt = dataframe_to_ascii(df)
    st.download_button(
        "⬇️ Download TXT (ASCII Table)",
        ascii_txt,
        file_name="transactions.txt",
        mime="text/plain"
    )

else:
    if uploaded_files:
        st.warning("⚠️ No transactions found — click **Start Processing**.")
