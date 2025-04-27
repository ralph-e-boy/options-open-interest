# spy_options_open_interest.py

import streamlit as st
import yfinance as yf
import pandas as pd
import time
import plotly.express as px
from datetime import date, timedelta

# ---- Streamlit UI ----
st.title("SPY Options Open Interest Map")

# Inputs
expiration = st.date_input("Select Expiration Date", value=date.today() + timedelta(days=7))
step = st.number_input("Strike Step Interval", min_value=1, max_value=50, value=5)
range_above_below = st.slider("Range Above and Below Spot ($)", min_value=0, max_value=200, value=100)
fetch_button = st.button("Fetch Option Data")

# Cache spot price and option data for 1 day
@st.cache_data(ttl=86400)
def get_spy_spot():
    spy = yf.Ticker("SPY")
    todays_price = spy.history(period="1d")["Close"].iloc[-1]
    return todays_price

@st.cache_data(ttl=86400)
def fetch_option_chain(symbol, expiration_date):
    ticker = yf.Ticker(symbol)
    opt_chain = ticker.option_chain(expiration_date)
    calls = opt_chain.calls
    puts = opt_chain.puts
    return calls, puts

# ---- Main Logic ----
if fetch_button:
    spot = get_spy_spot()
    st.write(f"Current SPY Spot Price: **${spot:.2f}**")
    
    calls, puts = fetch_option_chain("SPY", expiration.strftime('%Y-%m-%d'))
    
    # Filter strikes around the spot
    min_strike = (spot - range_above_below)
    max_strike = (spot + range_above_below)

    calls_filtered = calls[(calls['strike'] >= min_strike) & (calls['strike'] <= max_strike)]
    puts_filtered = puts[(puts['strike'] >= min_strike) & (puts['strike'] <= max_strike)]
    
    # Adjust to nearest step
    calls_filtered = calls_filtered[calls_filtered['strike'] % step == 0]
    puts_filtered = puts_filtered[puts_filtered['strike'] % step == 0]

    # Merge and prepare DataFrame
    merged = pd.merge(
        calls_filtered[['strike', 'openInterest']].rename(columns={'openInterest':'call_oi'}),
        puts_filtered[['strike', 'openInterest']].rename(columns={'openInterest':'put_oi'}),
        on='strike',
        how='outer'
    ).fillna(0)

    merged['call_oi'] = merged['call_oi'].astype(int)
    merged['put_oi'] = merged['put_oi'].astype(int)

    st.subheader("Open Interest Table")
    st.dataframe(merged)

    # ---- Plot Horizontal Bar Chart ----
    fig = px.bar(
        merged,
        y="strike",
        x=["call_oi", "put_oi"],
        orientation="h",
        title="SPY Options Open Interest (Calls vs Puts)",
        labels={"value":"Open Interest", "strike":"Strike Price"},
        height=800
    )
    fig.update_layout(barmode="stack", yaxis_autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

