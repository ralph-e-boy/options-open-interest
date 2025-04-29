# options_open_interest_snap_zoom.py

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

# ---- Streamlit UI ----
st.set_page_config(page_title="Options Flow Map", layout="wide")
st.header("📈 Options Open Interest Tracker", divider=True)

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
        height=1100,
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
    )
    return fig

# ---- Main App ----

# Configuration settings above tabs
st.subheader("⚙️ Configure Settings")

col1, col2, col3 = st.columns(3)
with col1:
    ticker = st.text_input("Ticker Symbol", value="SPY")
with col2:
    expiration = st.date_input("Select Expiration Date", value=next_weekday(date.today()))
with col3:
    range_above_below = st.slider("Range Above and Below Spot ($)", min_value=0, max_value=200, value=100)

# Always use step=1
step = 1

fetch_button = st.button("🚀 Fetch Open Interest Data")

# Set up Tabs
tab1, tab2, tab3 = st.tabs(["📊 Chart", "📋 Table", "ℹ️ Info"])

# Shared state variables
if 'merged' not in st.session_state:
    st.session_state['merged'] = None
if 'spot' not in st.session_state:
    st.session_state['spot'] = None
if 'ticker' not in st.session_state:
    st.session_state['ticker'] = "SPY"
if 'last_params' not in st.session_state:
    st.session_state['last_params'] = {}

# Function to fetch data
def fetch_data(ticker, expiration, step, range_above_below):
    with st.spinner(f"Fetching data for {ticker}..."):
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
        
        # Update last parameters
        st.session_state['last_params'] = {
            'ticker': ticker,
            'expiration': expiration,
            'step': step,
            'range_above_below': range_above_below
        }

# Check if fetch button is clicked
if fetch_button:
    fetch_data(ticker, expiration, step, range_above_below)
    
# Check if parameters have changed and need auto-fetch
current_params = {
    'ticker': ticker,
    'expiration': expiration,
    'step': step,
    'range_above_below': range_above_below
}

# Auto-fetch on parameter changes if they're different from last fetch
if (st.session_state['last_params'] != current_params and 
    (st.session_state['last_params'].get('ticker') != ticker or
     st.session_state['last_params'].get('expiration') != expiration or
     st.session_state['last_params'].get('range_above_below') != range_above_below)):
    fetch_data(ticker, expiration, step, range_above_below)

# Handle other tabs
if st.session_state['merged'] is not None:

    with tab1:
        fig = make_refined_chart(st.session_state['merged'], st.session_state['spot'], st.session_state['ticker'])
        st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        st.header("📋 Open Interest Table")

        def color_delta(val):
            color = 'green' if val > 0 else 'red'
            return f'background: linear-gradient(90deg, {color} {min(abs(val), 100)}%, transparent {min(abs(val), 100)}%);'

        styled_table = st.session_state['merged'].style\
            .background_gradient(axis=0, cmap="Greens", subset=["call_oi"])\
            .background_gradient(axis=0, cmap="Reds", subset=["put_oi"])\
            .format({"delta": "{:+d}"})\
            .map(color_delta, subset=["delta"])

        st.dataframe(styled_table)
        
    with tab3:
        st.header("ℹ️ About This Tool", divider=True)
        st.write("""
        This tool visualizes options open interest for a given ticker and expiration date.
        
        - **Green bars**: Call option open interest
        - **Red bars**: Put option open interest
        - **Blue dashed line**: Current stock price
        - **Black dots**: Net delta (Call OI - Put OI)
        """)

