import streamlit as st
import pdfplumber
import json
import pandas as pd

from maybank import parse_transactions_maybank
from public_bank import parse_transactions_pbb
from rhb import parse_transactions_rhb


# ---------------------------------------------------
# Streamlit Setup
# ---------------------------------------------------

st.set_page_config(page_title="Bank Statement Parser", layout="wide")

st.title("📄 Bank Statement Parser (Multi-File + Preview + Controls)")


# ---------------------------------------------------
# Clear All Button
# ---------------------------------------------------

if st.button("🧹 Clear All Uploaded PDFs"):
    st.session_state.clear()
    st.experimental_rerun()


# ---------------------------------------------------
# Bank Selection
# ---------------------------------------------------

bank_choice = st.selectbox(
    "Select Bank Format",
    ["Auto-detect", "Maybank", "Public Bank (PBB)", "RHB Bank"]
)

bank_hint = None
if bank_choice == "Maybank":
    bank_hint = "maybank"
elif bank_choice == "Public Bank (PBB)":
    bank_hint = "pbb"
elif bank_choice == "RHB Bank":
    bank_hint = "rhb"


# ---------------------------------------------------
# Multiple File Upload
# ---------------------------------------------------

uploaded_files = st.file_uploader(
    "Upload PDF Files",
    type=["pdf"],
    accept_multiple_files=True,
    key="uploaded_files"
)

default_year = st.text_input("Default Year", "2025")


# ---------------------------------------------------
# Start Button
# ---------------------------------------------------

start_processing = st.button("🚀 START PROCESSING")


# ---------------------------------------------------
# Auto Detect Parser
# ---------------------------------------------------

def auto_detect_and_parse(text, page_num, default_year="2025"):
    t1 = parse_transactions_maybank(text, page_num, default_year)
    if t1:
        return t1

    t2 = parse_transactions_pbb(text, page_num, default_year)
    if t2:
        return t2

    t3 = parse_transactions_rhb(text, page_num)
    if t3:
        return t3

    return []


# ---------------------------------------------------
# Main Processing
# ---------------------------------------------------

all_tx = []

if start_processing and uploaded_files:

    for uploaded_file in uploaded_files:

        st.subheader(f"📄 Preview: {uploaded_file.name}")

        with pdfplumber.open(uploaded_file) as pdf:

            # PREVIEW SECTION (TEXT PER PAGE)
            with st.expander(f"🔍 Preview Extracted Text ({uploaded_file.name})"):
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    st.markdown(f"### 📘 Page {page_num}")
                    st.text(text)

            # RESET BACK TO FIRST PAGE FOR PROCESSING
            # Re-open PDF for actual processing (needed because we iterated once for preview)
with pdfplumber.open(uploaded_file) as pdf_process:
    for page_num, page in enumerate(pdf_process.pages, start=1):
        text = page.extract_text() or ""

        if bank_hint == "maybank":
            tx = parse_transactions_maybank(text, page_num, default_year)
        elif bank_hint == "pbb":
            tx = parse_transactions_pbb(text, page_num, default_year)
        elif bank_hint == "rhb":
            tx = parse_transactions_rhb(text, page_num)
        else:
            tx = auto_detect_and_parse(text, page_num, default_year)

        for t in tx:
            t["source_file"] = uploaded_file.name

        all_tx.extend(tx)


            # PROCESS TRANSACTIONS
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""

                if bank_hint == "maybank":
                    tx = parse_transactions_maybank(text, page_num, default_year)
                elif bank_hint == "pbb":
                    tx = parse_transactions_pbb(text, page_num, default_year)
                elif bank_hint == "rhb":
                    tx = parse_transactions_rhb(text, page_num)
                else:
                    tx = auto_detect_and_parse(text, page_num, default_year)

                for t in tx:
                    t["source_file"] = uploaded_file.name

                all_tx.extend(tx)


# ---------------------------------------------------
# Display Extracted Transactions
# ---------------------------------------------------

if all_tx:

    st.subheader("📊 Extracted Transactions (Readable Table)")

    df = pd.DataFrame(all_tx)
    col_order = ["date", "description", "debit", "credit", "balance", "page", "source_file"]
    df = df[[c for c in col_order if c in df.columns]]

    st.dataframe(df, use_container_width=True)


    # ---------------------------------------------------
    # JSON DOWNLOAD
    # ---------------------------------------------------

    json_data = json.dumps(all_tx, indent=4)

    st.download_button(
        "⬇️ Download JSON",
        json_data,
        file_name="transactions.json",
        mime="application/json"
    )


    # ---------------------------------------------------
    # TXT (Pretty Table) DOWNLOAD
    # ---------------------------------------------------

    df_txt = df[["date", "description", "debit", "credit", "balance", "source_file"]]

    w_date = 12
    w_desc = 45
    w_debit = 12
    w_credit = 12
    w_balance = 14
    w_file = 20

    header = (
        f"{'DATE':<{w_date}} | "
        f"{'DESCRIPTION':<{w_desc}} | "
        f"{'DEBIT':>{w_debit}} | "
        f"{'CREDIT':>{w_credit}} | "
        f"{'BALANCE':>{w_balance}} | "
        f"{'FILE':<{w_file}}"
    )
    separator = "-" * len(header)

    lines = [header, separator]

    for _, row in df_txt.iterrows():
        line = (
            f"{row['date']:<{w_date}} | "
            f"{str(row['description'])[:w_desc]:<{w_desc}} | "
            f"{row['debit']:>{w_debit}.2f} | "
            f"{row['credit']:>{w_credit}.2f} | "
            f"{row['balance']:>{w_balance}.2f} | "
            f"{row['source_file']:<{w_file}}"
        )
        lines.append(line)

    txt_data = "\n".join(lines)

    st.download_button(
        "⬇️ Download TXT",
        txt_data,
        file_name="transactions.txt",
        mime="text/plain"
    )


else:
    st.info("Upload PDF files and click **START PROCESSING** to begin.")
