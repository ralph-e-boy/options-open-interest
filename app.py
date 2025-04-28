# options_open_interest_snap_zoom.py

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

# ---- Streamlit UI ----
st.set_page_config(page_title="Options Flow Map", layout="wide")
st.title("📈 Options Open Interest Tracker")

# ---- Functions ----
def next_weekday(d):
    while d.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        d += timedelta(days=1)
    return d


@st.cache_data(ttl=86400)
def get_stock_spot(ticker):
    stock = yf.Ticker(ticker)
    todays_price = stock.history(period="1d")["Close"].iloc[-1]
    return todays_price

@st.cache_data(ttl=86400)
def fetch_option_chain(symbol, expiration_date):
    ticker = yf.Ticker(symbol)
    opt_chain = ticker.option_chain(expiration_date)
    calls = opt_chain.calls
    puts = opt_chain.puts
    return calls, puts

def make_refined_chart(merged_df, spot, ticker):
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

    # Add PUT bars
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

    # Horizontal line at Spot Price
    fig.add_shape(
        type="line",
        x0=-merged_df[['put_oi', 'call_oi']].max().max() * 1.1,
        x1=merged_df[['put_oi', 'call_oi']].max().max() * 1.1,
        y0=spot,
        y1=spot,
        line=dict(color="blue", width=2, dash="dash"),
    )

    # Delta markers
    fig.add_trace(go.Scatter(
        x=merged_df['delta'],
        y=merged_df['strike'],
        mode='markers',
        marker=dict(color='black', size=6),
        name='Net Call-Put Delta',
        hovertemplate="Strike: %{y}<br>Net Delta: %{x}<extra></extra>",
    ))

    # Snap zoom range: around Spot ± 10 strikes
    y_min = merged_df['strike'].min()
    y_max = merged_df['strike'].max()
    zoom_margin = (y_max - y_min) * 0.15  # 15% margin

    fig.update_layout(
        title=f"{ticker} Options Open Interest Map",
        barmode='overlay',
        xaxis_title="Open Interest (Calls ➡ | ⬅ Puts)",
        yaxis_title="Strike Price",
        yaxis=dict(
            tickmode='array',
            tickvals=merged_df['strike'],
            ticktext=[str(int(strike)) for strike in merged_df['strike']],
            tickfont=dict(size=10),
            range=[spot - zoom_margin, spot + zoom_margin],  # 👈 SNAP ZOOM AROUND SPOT
        ),
        xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black'),
        plot_bgcolor="#f9f9f9",
        bargap=0.2,
        height=600,
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
    )
    return fig

# ---- Main App ----

# Set up Tabs
tab1, tab2, tab3 = st.tabs(["⚙️ Settings", "📊 Chart", "📋 Table"])

with tab1:
    st.header("⚙️  Configure Settings")
    
    ticker = st.text_input("Ticker Symbol", value="SPY")
    expiration = st.date_input("Select Expiration Date", value=next_weekday(date.today()))
    step = st.number_input("Strike Step Interval ($)", min_value=1, max_value=50, value=1)
    range_above_below = st.slider("Range Above and Below Spot ($)", min_value=0, max_value=200, value=100)
    fetch_button = st.button("🚀 Fetch Open Interest Data")

# Shared state variables
if 'merged' not in st.session_state:
    st.session_state['merged'] = None
if 'spot' not in st.session_state:
    st.session_state['spot'] = None
if 'ticker' not in st.session_state:
    st.session_state['ticker'] = "SPY"

# If fetch button is clicked
if fetch_button:
    spot = get_stock_spot(ticker)
    st.success(f"Fetched {ticker} Spot Price: **${spot:.2f}**")

    calls, puts = fetch_option_chain(ticker, expiration.strftime('%Y-%m-%d'))

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
    merged['delta'] = merged['call_oi'] - merged['put_oi']

    st.session_state['merged'] = merged
    st.session_state['spot'] = spot
    st.session_state['ticker'] = ticker

# Handle other tabs
if st.session_state['merged'] is not None:

    with tab3:
        st.header("📋 Open Interest Table")

        def color_delta(val):
            color = 'green' if val > 0 else 'red'
            return f'background: linear-gradient(90deg, {color} {min(abs(val), 100)}%, transparent {min(abs(val), 100)}%);'

        styled_table = st.session_state['merged'].style\
            .background_gradient(axis=0, cmap="Greens", subset=["call_oi"])\
            .background_gradient(axis=0, cmap="Reds", subset=["put_oi"])\
            .format({"delta": "{:+d}"})\
            .applymap(color_delta, subset=["delta"])

        st.dataframe(styled_table)

    with tab2:
        #st.header("📊 Open Interest Chart")
        fig = make_refined_chart(st.session_state['merged'], st.session_state['spot'], st.session_state['ticker'])
        st.plotly_chart(fig, use_container_width=True)

