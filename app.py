import streamlit as st
import pdfplumber
import pandas as pd

from banks import parse_page_by_bank, detect_bank_by_text
from exporter import dataframe_to_ascii, dataframe_to_json


# -------------------------------
# Streamlit Setup
# -------------------------------
st.set_page_config(page_title="Bank Parser", layout="wide")
st.title("📄 Bank Statement Parser (Multi-Bank Support)")


# -------------------------------
# Session State
# -------------------------------
if "status" not in st.session_state:
    st.session_state.status = "idle"
if "results" not in st.session_state:
    st.session_state.results = []


# -------------------------------
# Bank Selection
# -------------------------------
bank_choice = st.selectbox("Select Bank Format", [
    "Auto-detect",
    "Maybank",
    "Public Bank (PBB)",
    "RHB Bank",
    "CIMB Bank",
    "Bank Islam"
])

bank_map = {
    "Maybank": "maybank",
    "Public Bank (PBB)": "pbb",
    "RHB Bank": "rhb",
    "CIMB Bank": "cimb",
    "Bank Islam": "bank_islam"
}

bank_hint = bank_map.get(bank_choice)  # None = Auto-detect


# -------------------------------
# File Upload
# -------------------------------
uploaded_files = st.file_uploader(
    "Upload PDF files",
    type=["pdf"],
    accept_multiple_files=True
)

default_year = st.text_input("Default Year", "2025")


# -------------------------------
# Auto-Detect Preview (Before Start)
# -------------------------------
if uploaded_files and bank_hint is None:
    st.subheader("🔍 Auto-Detect Preview")
    for f in uploaded_files:
        try:
            with pdfplumber.open(f) as pdf:
                text = pdf.pages[0].extract_text() or ""
                detected = detect_bank_by_text(text)

                readable = {
                    "maybank": "Maybank",
                    "pbb": "Public Bank (PBB)",
                    "rhb": "RHB Bank",
                    "cimb": "CIMB Bank",
                    "bank_islam": "Bank Islam",
                    "unknown": "Unknown Format"
                }[detected]

                st.info(f"📄 {f.name} → 🏦 {readable}")

        except Exception as e:
            st.error(f"Preview error for {f.name}: {e}")


# -------------------------------
# Controls
# -------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("▶ Start"):
        st.session_state.status = "running"

with col2:
    if st.button("⏹ Stop"):
        st.session_state.status = "stopped"

with col3:
    if st.button("🔄 Reset"):
        st.session_state.results = []
        st.session_state.status = "idle"
        st.rerun()


st.write(f"### Status: **{st.session_state.status.upper()}**")


# -------------------------------
# MAIN PROCESSING LOOP
# -------------------------------
if uploaded_files and st.session_state.status == "running":

    live_status = st.empty()
    collected = []

    for f in uploaded_files:
        st.write(f"### Processing {f.name}")

        with pdfplumber.open(f) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):

                if st.session_state.status == "stopped":
                    st.warning("Processing stopped by user.")
                    break

                text = page.extract_text() or ""

                tx, bank_used = parse_page_by_bank(
                    text=text,
                    page_obj=page,
                    page_num=page_num,
                    bank_hint=bank_hint,
                    default_year=default_year,
                    source_file=f.name
                )

                live_status.info(f"🏦 Processing: {bank_used} (Page {page_num})")

                for t in tx:
                    t["source_file"] = f.name
                    t["bank"] = bank_used

                collected.extend(tx)

    st.session_state.results = collected


# -------------------------------
# DISPLAY RESULTS & EXPORT
# -------------------------------
if st.session_state.results:
    st.subheader("📊 Extracted Transactions")
    df = pd.DataFrame(st.session_state.results)

    st.dataframe(df, use_container_width=True)

    # JSON export
    json_export = dataframe_to_json(df)
    st.download_button("⬇ Download JSON", json_export, "transactions.json")

    # TXT export
    txt_export = dataframe_to_ascii(df)
    st.download_button("⬇ Download TXT", txt_export, "transactions.txt")

else:
    if uploaded_files:
        st.warning("No transactions found — press START to begin.")
