# spy_options_open_interest_refined.py

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

# ---- Streamlit UI ----
st.set_page_config(page_title="SPY Options Flow Map", layout="wide")
st.title("📈 SPY Institutional Flow Tracker — Refined")

# Inputs
expiration = st.date_input("Select Expiration Date", value=date.today() + timedelta(days=7))
step = st.number_input("Strike Step Interval ($)", min_value=1, max_value=50, value=5)
range_above_below = st.slider("Range Above and Below Spot ($)", min_value=0, max_value=200, value=100)
fetch_button = st.button("🚀 Fetch Open Interest Data")

# ---- Functions ----

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

def make_refined_chart(merged_df, spot):
    fig = go.Figure()

    # Add CALL bars
    fig.add_trace(go.Bar(
        y=merged_df['strike'],
        x=merged_df['call_oi'],
        name='Call Open Interest',
        orientation='h',
        marker=dict(color='rgba(0,200,0,0.6)'),
        text=merged_df['call_oi'],
        textposition='inside',
        insidetextanchor='start',
        hovertemplate="Strike: %{y}<br>Call OI: %{x}<extra></extra>",
        ))

    # Add PUT bars (negative x)
    fig.add_trace(go.Bar(
        y=merged_df['strike'],
        x=-merged_df['put_oi'],
        name='Put Open Interest',
        orientation='h',
        marker=dict(color='rgba(200,0,0,0.6)'),
        text=merged_df['put_oi'],
        textposition='inside',
        insidetextanchor='end',
        hovertemplate="Strike: %{y}<br>Put OI: %{x}<extra></extra>",
        ))

    # Add horizontal line for SPOT PRICE
    fig.add_shape(
            type="line",
            x0=-merged_df[['put_oi', 'call_oi']].max().max() * 1.1,
            x1=merged_df[['put_oi', 'call_oi']].max().max() * 1.1,
            y0=spot,
            y1=spot,
            line=dict(color="blue", width=2, dash="dash"),
            )

    # Delta = call OI - put OI
    merged_df['delta'] = merged_df['call_oi'] - merged_df['put_oi']

    # Add small marker for net delta at each strike
    fig.add_trace(go.Scatter(
        x=merged_df['delta'],
        y=merged_df['strike'],
        mode='markers',
        marker=dict(color='black', size=6),
        name='Net Call-Put Delta',
        hovertemplate="Strike: %{y}<br>Net Delta: %{x}<extra></extra>",
        ))

    fig.update_layout(
            title="SPY Options Open Interest Map",
            barmode='overlay',
            xaxis_title="Open Interest (Calls ➡ | ⬅ Puts)",
            yaxis_title="Strike Price",
            yaxis_autorange=True,
            xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black'),
			yaxis=dict(
				tickmode='array',
				tickvals=merged_df['strike'],
				ticktext=[str(int(strike)) for strike in merged_df['strike']],
			),
            plot_bgcolor="#f9f9f9",
            bargap=0.2,
            height=900,
            legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
            )
    return fig

# ---- Main App ----
if fetch_button:
    spot = get_spy_spot()
    st.success(f"Current SPY Spot Price: **${spot:.2f}**")

    calls, puts = fetch_option_chain("SPY", expiration.strftime('%Y-%m-%d'))

    min_strike = (spot - range_above_below)
    max_strike = (spot + range_above_below)

    calls_filtered = calls[(calls['strike'] >= min_strike) & (calls['strike'] <= max_strike)]
    puts_filtered = puts[(puts['strike'] >= min_strike) & (puts['strike'] <= max_strike)]

    calls_filtered = calls_filtered[calls_filtered['strike'] % step == 0]
    puts_filtered = puts_filtered[puts_filtered['strike'] % step == 0]

    merged = pd.merge(
            calls_filtered[['strike', 'openInterest']].rename(columns={'openInterest':'call_oi'}),
            puts_filtered[['strike', 'openInterest']].rename(columns={'openInterest':'put_oi'}),
            on='strike',
            how='outer'
            ).fillna(0)

    merged['call_oi'] = merged['call_oi'].astype(int)
    merged['put_oi'] = merged['put_oi'].astype(int)
    merged['delta'] = merged['call_oi'] - merged['put_oi']  # <-- add delta here

    st.subheader("📝 Open Interest Table (Delta Added)")
    st.dataframe(
            merged.style.background_gradient(axis=0, cmap="Greens", subset=["call_oi"])
            .background_gradient(axis=0, cmap="Reds", subset=["put_oi"])
            .background_gradient(axis=0, cmap="coolwarm", subset=["delta"])
            )

    st.subheader("📊 Open Interest Bar Chart with Spot Line and Net Delta")
    fig = make_refined_chart(merged, spot)
    st.plotly_chart(fig, use_container_width=True)

