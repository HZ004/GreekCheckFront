import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd
import plotly.graph_objs as go
import gspread
from google.oauth2.service_account import Credentials
import io

st.set_page_config(layout="wide")
st.title("Upstox Live Options Greeks Dashboard")

# Google Sheets Authentication using SERVICE_ACCOUNT_JSON as environment variable
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON")
raw = SERVICE_ACCOUNT_JSON.encode("utf-8").decode("unicode_escape")


if not SERVICE_ACCOUNT_JSON:
    st.error("SERVICE_ACCOUNT_JSON environment variable not set")
    st.stop()

creds_dict = json.loads(raw)

creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
])
gc = gspread.authorize(creds)

SPREADSHEET_NAME = "Upstox-Greeks"
sheet = gc.open(SPREADSHEET_NAME).sheet1

def read_greeks_from_sheets():
    records = sheet.get_all_records()
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)

# Read data once on app start or refresh
historical_df = read_greeks_from_sheets()

if historical_df.empty:
    st.info("No historical data found in Google Sheets yet.")
else:
    # Convert timestamps and add date column
    historical_df["timestamp"] = pd.to_datetime(historical_df["timestamp"], errors='coerce')
    historical_df["date"] = historical_df["timestamp"].dt.date
    unique_dates = sorted(historical_df["date"].dropna().unique(), reverse=True)

    # Sidebar date filter showing last 30 days or all available, whichever is smaller
    max_display_dates = 30
    available_dates = unique_dates[:max_display_dates]

    selected_date = st.sidebar.selectbox(
        "Select date to view Greeks data (most recent first)",
        options=available_dates,
        index=0
    )

    filtered_df = historical_df[historical_df["date"] == selected_date]

    if filtered_df.empty:
        st.warning(f"No data found for {selected_date}")
    else:
        st.subheader(f"Historical Greeks Data for {selected_date}")
        st.dataframe(filtered_df)

        # Define metrics and option types
        # greek_metrics = ["ltp", "delta", "gamma", "theta"]
        greek_metrics = ["ltp", "delta", "gamma", "theta"]
        names_for_caption = {
            "ltp": "Last Traded Price",
            "delta": "Delta",
            "gamma": "Gamma",
            "theta": "Theta"
        }
        col1, col2 = st.columns(2)
        for metric in greek_metrics:
            ce_cols = [c for c in df.columns if c.startswith("CE_") and c.endswith(f"_{metric}")]
            pe_cols = [c for c in df.columns if c.startswith("PE_") and c.endswith(f"_{metric}")]
            y_min, y_max = None, None
            if ce_cols or pe_cols:
                combined_data = pd.concat([
                    df[ce_cols] if ce_cols else pd.DataFrame(),
                    df[pe_cols] if pe_cols else pd.DataFrame()
                ], axis=1)
                y_min = combined_data.min().min()
                y_max = combined_data.max().max()
            y_range = [y_min, y_max] if y_min is not None and y_max is not None else None
            with col1:
                if ce_cols:
                    fig_ce = px.line(df, x="timestamp", y=ce_cols,
                                     title=f"Call (CE) {names_for_caption[metric]} Time Series",
                                     labels={"value": names_for_caption[metric], "timestamp": "Time"})
                    if y_range:
                        fig_ce.update_yaxes(range=y_range)
                    st.plotly_chart(fig_ce, use_container_width=True)
            with col2:
                if pe_cols:
                    fig_pe = px.line(df, x="timestamp", y=pe_cols,
                                     title=f"Put (PE) {names_for_caption[metric]} Time Series",
                                     labels={"value": names_for_caption[metric], "timestamp": "Time"})
                    if y_range:
                        fig_pe.update_yaxes(range=y_range)
                    st.plotly_chart(fig_pe, use_container_width=True)

        # Download CSV button for selected date
        csv_buffer = io.StringIO()
        filtered_df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode()
        st.download_button(
            label="Download Greeks Data CSV for Selected Date",
            data=csv_bytes,
            file_name=f"greeks_data_{selected_date}.csv",
            mime="text/csv"
        )
