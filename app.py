import streamlit as st
import pdfplumber
import json
import pandas as pd
from datetime import datetime
from io import BytesIO
import re

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

# Sort uploaded files by name (assumes filenames contain dates/months)
if uploaded_files:
    uploaded_files = sorted(uploaded_files, key=lambda x: x.name)


# ---------------------------------------------------
# Helper: Extract Statement Month from PDF
# ---------------------------------------------------
def extract_statement_month(pdf, filename):
    """
    Extract the statement month/year from the PDF header or filename.
    Returns tuple: (year, month) or None
    """
    try:
        # Try to extract from first page
        first_page = pdf.pages[0]
        text = first_page.extract_text() or ""
        
        # Common patterns in bank statements
        # Pattern 1: "Statement Date: 01 Jan 2025" or "Statement Period: Jan 2025"
        patterns = [
            r'Statement\s+(?:Date|Period)[:\s]+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})',
            r'Statement\s+(?:Date|Period)[:\s]+([A-Za-z]+)\s+(\d{4})',
            r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}',
            r'([A-Za-z]+)\s+(\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Handle different match formats
                if len(groups) == 3:
                    # Has day, month, year
                    month_str = groups[1]
                    year = int(groups[2])
                elif len(groups) == 2:
                    # Has month, year
                    month_str = groups[0]
                    year = int(groups[1])
                else:
                    continue
                
                # Convert month name to number
                month_map = {
                    'jan': 1, 'january': 1,
                    'feb': 2, 'february': 2,
                    'mar': 3, 'march': 3,
                    'apr': 4, 'april': 4,
                    'may': 5,
                    'jun': 6, 'june': 6,
                    'jul': 7, 'july': 7,
                    'aug': 8, 'august': 8,
                    'sep': 9, 'sept': 9, 'september': 9,
                    'oct': 10, 'october': 10,
                    'nov': 11, 'november': 11,
                    'dec': 12, 'december': 12
                }
                
                month = month_map.get(month_str.lower()[:3])
                if month:
                    return (year, month)
        
        # Try to extract from filename as fallback
        # e.g., "statement_jan_2025.pdf" or "2025-01.pdf"
        filename_patterns = [
            r'(\d{4})[_-](\d{1,2})',  # 2025-01 or 2025_1
            r'([a-z]+)[_-](\d{4})',    # jan_2025
            r'(\d{4})[_-]([a-z]+)',    # 2025_jan
        ]
        
        for pattern in filename_patterns:
            match = re.search(pattern, filename.lower())
            if match:
                g1, g2 = match.groups()
                
                # Try to determine which is year and which is month
                if g1.isdigit() and len(g1) == 4:
                    year = int(g1)
                    if g2.isdigit():
                        month = int(g2)
                    else:
                        month = month_map.get(g2[:3])
                elif g2.isdigit() and len(g2) == 4:
                    year = int(g2)
                    if g1.isdigit():
                        month = int(g1)
                    else:
                        month = month_map.get(g1[:3])
                else:
                    continue
                
                if month and 1 <= month <= 12:
                    return (year, month)
    
    except Exception as e:
        st.warning(f"Could not extract statement month: {e}")
    
    return None


# ---------------------------------------------------
# Auto-Detect Preview (Before Start Processing)
# ---------------------------------------------------
if uploaded_files and bank_hint is None:
    st.subheader("🔍 Auto-Detect Preview (Before Processing)")

    for uploaded_file in uploaded_files:
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""

                detected_bank = "Unknown"

                # SIMPLE detection — matching logos/text
                if "CIMB" in text.upper():
                    detected_bank = "CIMB Bank"
                elif "MAYBANK" in text.upper():
                    detected_bank = "Maybank"
                elif "PUBLIC BANK" in text.upper() or "PBB" in text.upper():
                    detected_bank = "Public Bank (PBB)"
                elif "RHB" in text.upper():
                    detected_bank = "RHB Bank"
                
                # Extract statement month
                statement_month = extract_statement_month(pdf, uploaded_file.name)
                month_info = f" | Statement: {statement_month[0]}-{statement_month[1]:02d}" if statement_month else ""

                st.info(f"📄 **{uploaded_file.name}** → 🏦 **Detected Bank: {detected_bank}**{month_info}")

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
# Auto-Detect Parsing Function
# ---------------------------------------------------
def auto_detect_and_parse(text, page_obj, page_num, default_year="2025", **source_file_kwargs):

    source_file = source_file_kwargs.get("source_file", "AutoDetect")

    # CIMB
    if "CIMB" in text.upper():
        tx = parse_transactions_cimb(page_obj, page_num, source_file)
        if tx:
            return tx, "CIMB Bank"

    # Maybank
    tx = parse_transactions_maybank(text, page_num, default_year)
    if tx:
        return tx, "Maybank"

    # Public Bank
    tx = parse_transactions_pbb(text, page_num, default_year)
    if tx:
        return tx, "Public Bank (PBB)"

    # RHB
    tx = parse_transactions_rhb(text, page_num)
    if tx:
        return tx, "RHB Bank"

    return [], "Unknown"


# ---------------------------------------------------
# MAIN PROCESSING
# ---------------------------------------------------
all_tx = []

if uploaded_files and st.session_state.status == "running":

    bank_display_box = st.empty()  # live status

    for uploaded_file in uploaded_files:

        st.write(f"### 🗂 Processing File: **{uploaded_file.name}**")

        try:
            with pdfplumber.open(uploaded_file) as pdf:
                
                # Extract statement month for this file
                statement_month = extract_statement_month(pdf, uploaded_file.name)
                if statement_month:
                    st.success(f"📅 Statement Period: {statement_month[0]}-{statement_month[1]:02d}")

                for page_num, page in enumerate(pdf.pages, start=1):

                    if st.session_state.status == "stopped":
                        st.warning("⏹️ Processing stopped by user.")
                        break

                    text = page.extract_text() or ""
                    tx = []
                    detected_bank = "Auto"

                    bank_display_box.info(f"🔍 Detecting bank for Page {page_num}...")

                    # DIRECT PARSING if bank selected
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

                    # AUTO-DETECT MODE
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
                            
                            # Add statement month metadata if available
                            if statement_month:
                                t["statement_year"] = statement_month[0]
                                t["statement_month"] = statement_month[1]

                        all_tx.extend(tx)

        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {e}")

    st.session_state.results = all_tx


# ---------------------------------------------------
# CALCULATE MONTHLY SUMMARY - IMPROVED VERSION
# ---------------------------------------------------
def calculate_monthly_summary(transactions):
    if not transactions:
        return []
    
    df = pd.DataFrame(transactions)
    
    # First, try to use statement_year and statement_month if available
    has_statement_metadata = 'statement_year' in df.columns and 'statement_month' in df.columns
    
    if has_statement_metadata:
        # Use the statement metadata for grouping
        df['year_month'] = df.apply(
            lambda row: pd.Period(year=int(row['statement_year']), 
                                 month=int(row['statement_month']), 
                                 freq='M') if pd.notna(row.get('statement_year')) else None,
            axis=1
        )
    else:
        # Fallback to parsing dates from transactions
        df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date_parsed'])
        df['year_month'] = df['date_parsed'].dt.to_period('M')
    
    # Remove rows without valid year_month
    df = df.dropna(subset=['year_month'])
    
    if df.empty:
        st.warning("⚠️ No valid dates found in transactions. Check date format in parser outputs.")
        return []
    
    # Convert debit, credit, balance to float
    df['debit'] = pd.to_numeric(df['debit'], errors='coerce').fillna(0)
    df['credit'] = pd.to_numeric(df['credit'], errors='coerce').fillna(0)
    df['balance'] = pd.to_numeric(df['balance'], errors='coerce')
    
    # Group by year_month
    monthly_summary = []
    for ym, group in df.groupby('year_month'):
        summary = {
            'month': str(ym),
            'total_debit': round(group['debit'].sum(), 2),
            'total_credit': round(group['credit'].sum(), 2),
            'net_change': round(group['credit'].sum() - group['debit'].sum(), 2),
            'lowest_balance': round(group['balance'].min(), 2) if not group['balance'].isna().all() else None,
            'highest_balance': round(group['balance'].max(), 2) if not group['balance'].isna().all() else None,
            'transaction_count': len(group),
            'source_files': ', '.join(group['source_file'].unique()) if 'source_file' in group.columns else ''
        }
        monthly_summary.append(summary)
    
    return sorted(monthly_summary, key=lambda x: x['month'])


# ---------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------
if st.session_state.results:
    st.subheader("📊 Extracted Transactions")

    df = pd.DataFrame(st.session_state.results)

    expected_cols = ["date", "description", "debit", "credit", "balance", "page", "bank", "source_file"]
    # Add statement metadata columns if they exist
    if 'statement_year' in df.columns:
        expected_cols.extend(['statement_year', 'statement_month'])
    
    df = df[[c for c in expected_cols if c in df.columns]]

    st.dataframe(df, use_container_width=True)

    # Calculate monthly summary
    monthly_summary = calculate_monthly_summary(st.session_state.results)
    
    if monthly_summary:
        st.subheader("📅 Monthly Summary")
        summary_df = pd.DataFrame(monthly_summary)
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.warning("⚠️ Could not generate monthly summary. Please check if dates are being extracted correctly.")

    # JSON Export - Transactions Only
    st.subheader("⬇️ Download Options")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        json_transactions = json.dumps(df.to_dict(orient="records"), indent=4)
        st.download_button(
            "📄 Download Transactions (JSON)", 
            json_transactions, 
            file_name="transactions.json", 
            mime="application/json"
        )
    
    with col2:
        # JSON Export - Full Report with Summary
        full_report = {
            "transactions": df.to_dict(orient="records"),
            "monthly_summary": monthly_summary
        }
        json_full_report = json.dumps(full_report, indent=4)
        st.download_button(
            "📊 Download Full Report (JSON)", 
            json_full_report, 
            file_name="full_report.json", 
            mime="application/json"
        )
    
    with col3:
        # Excel Export - Full Report with Multiple Sheets
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Transactions', index=False)
                if monthly_summary:
                    summary_df = pd.DataFrame(monthly_summary)
                    summary_df.to_excel(writer, sheet_name='Monthly Summary', index=False)
            
            excel_data = output.getvalue()
            st.download_button(
                "📊 Download Full Report (XLSX)", 
                excel_data, 
                file_name="full_report.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ImportError:
            st.error("⚠️ xlsxwriter package not installed. Install with: pip install xlsxwriter")

else:
    if uploaded_files:
        st.warning("⚠️ No transactions found — click **Start Processing**.")
