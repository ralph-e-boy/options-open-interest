# options_open_interest_snap_zoom.py

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import time
import logging

# ---- Streamlit UI ----
st.set_page_config(page_title="Options Flow Map", layout="wide")
st.header("📈 Options Open Interest Tracker", divider=True)

# ---- Functions ----
def next_weekday(d):
    while d.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        d += timedelta(days=1)
    return d

# Rate limiter function to prevent too many requests
def rate_limit():
    """Sleep for 2 seconds to avoid hitting API rate limits"""
    time.sleep(2)

@st.cache_data(ttl=3600)  # Cache for 1 hour instead of 24 hours to be safer
def get_stock_spot(ticker):
    try:
        rate_limit()  # Add rate limiting
        stock = yf.Ticker(ticker)
        history = stock.history(period="1d")
        
        if history.empty:
            st.warning(f"No price data available for {ticker}")
            return None
            
        todays_price = history["Close"].iloc[-1]
        return todays_price
    except Exception as e:
        st.error(f"Error fetching stock price for {ticker}: {str(e)}")
        logging.error(f"Stock price fetch error: {str(e)}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_option_chain(symbol, expiration_date):
    try:
        rate_limit()  # Add rate limiting
        ticker = yf.Ticker(symbol)
        opt_chain = ticker.option_chain(expiration_date)
        
        calls = opt_chain.calls
        puts = opt_chain.puts
        
        # Check if data is empty
        if calls.empty or puts.empty:
            return None, None, {
                "message": f"No options data available for {symbol} on {expiration_date}",
                "available_dates": []
            }
            
        return calls, puts, None
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Option chain fetch error: {error_msg}")
        
        # Check if it's an expiration date error
        if "cannot be found" in error_msg:
            # Extract available expirations if they're in the error message
            available_dates = []
            if "Available expirations are:" in error_msg:
                try:
                    dates_part = error_msg.split("Available expirations are: [")[1].split("]")[0]
                    available_dates = [date.strip() for date in dates_part.split(',')]
                except IndexError:
                    # Handle case where error message format is unexpected
                    pass
            
            return None, None, {
                "message": f"No options available for {expiration_date}",
                "available_dates": available_dates
            }
        else:
            return None, None, {"message": f"Error fetching data: {error_msg}"}

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
        textposition='outside',
        textfont=dict(size=16),
        insidetextanchor='start',
        hovertemplate="Strike: %{y}<br>Call OI: %{x}<br>Price: $%{customdata:.2f}<extra></extra>",
        customdata=merged_df['call_price']
    ))

    # Add PUT bars
    fig.add_trace(go.Bar(
        y=merged_df['strike'],
        x=-merged_df['put_oi'],
        name='Put Open Interest',
        orientation='h',
        marker=dict(color='rgba(200,0,0,0.6)'),
        text=merged_df['put_oi'],
        textposition='outside',
        textfont=dict(size=16),
        insidetextanchor='end',
        hovertemplate="Strike: %{y}<br>Put OI: %{x}<br>Price: $%{customdata:.2f}<extra></extra>",
        customdata=merged_df['put_price']
    ))

    # Horizontal line at Spot Price
    fig.add_shape(
        type="line",
        x0=-merged_df[['put_oi', 'call_oi']].max().max() * 1.1,
        x1=merged_df[['put_oi', 'call_oi']].max().max() * 1.1,
        y0=spot,
        y1=spot,
        line=dict(color="blue", width=4, dash="dash"),
    )

    # Delta markers
    fig.add_trace(go.Scatter(
        x=merged_df['delta'],
        y=merged_df['strike'],
        mode='markers',
        marker=dict(color='black', size=8),
        name='Net Call-Put Delta',
        hovertemplate="Strike: %{y}<br>Net Delta: %{x}<extra></extra>",
    ))

    # Use the full range of strikes in the filtered data
    y_min = merged_df['strike'].min()
    y_max = merged_df['strike'].max()

    fig.update_layout(
        title=f"{ticker} Options Open Interest Map",
        barmode='overlay',
        xaxis_title="Open Interest (Calls ➡ | ⬅ Puts)",
        yaxis_title="Strike Price",
        yaxis=dict(
            tickmode='array',
            tickvals=merged_df['strike'],
            ticktext=[str(int(strike)) for strike in merged_df['strike']],
            tickfont=dict(size=16),  # Increased from 12 to 16
            range=[y_min, y_max],  # Show the full range of filtered strikes
            gridcolor='lightgray',  # Add light gray horizontal grid lines
            gridwidth=0.5,          # Make grid lines thin
        ),
        xaxis=dict(
            zeroline=True, 
            zerolinewidth=2, 
            zerolinecolor='black',
            tickfont=dict(size=16)  # Added font size for x-axis
        ),
        plot_bgcolor="#f9f9f9",
        bargap=0.2,
        height=1600,
		legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
		font=dict(
			size=18,
			color="RebeccaPurple"
			)
    )
    return fig

# ---- Main App ----

# Set up logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configuration settings above tabs
st.subheader("⚙️ Configure Settings")

col1, col2, col3 = st.columns(3)
with col1:
    ticker = st.text_input("Ticker Symbol", value="SPY")
with col2:
    expiration = st.date_input("Select Expiration Date", value=next_weekday(date.today()))
with col3:
    range_above_below = st.slider("Range Above and Below Spot ($)", min_value=0, max_value=200, value=25)

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
        try:
            # Get stock spot price
            spot = get_stock_spot(ticker)
            if spot is None:
                st.error(f"Could not fetch price data for {ticker}. Please check the ticker symbol.")
                st.session_state['merged'] = None
                st.session_state['last_params'] = current_params
                return
                
            st.success(f"Fetched {ticker} Spot Price: **${spot:.2f}**")

            # Get option chain data
            calls, puts, error = fetch_option_chain(ticker, expiration.strftime('%Y-%m-%d'))
            
            if error:
                # Handle error case
                st.error(error["message"])
                
                # If we have available dates, show them
                if error.get("available_dates") and len(error["available_dates"]) > 0:
                    st.info("Available expiration dates:")
                    # Convert string dates to date objects for better display
                    try:
                        available_dates = [pd.to_datetime(d).date() for d in error["available_dates"]]
                        available_dates.sort()  # Sort dates chronologically
                        
                        # Display the next few available dates
                        date_cols = st.columns(min(5, len(available_dates)))
                        for i, col in enumerate(date_cols):
                            if i < len(available_dates):
                                col.metric("Expiration", available_dates[i].strftime('%Y-%m-%d'))
                    except Exception as e:
                        # Fallback if date conversion fails
                        st.write(", ".join(error["available_dates"]))
                        logging.error(f"Date conversion error: {str(e)}")
                
                # Clear any previous data
                st.session_state['merged'] = None
                
                # Update last parameters to prevent auto-fetch loop
                st.session_state['last_params'] = {
                    'ticker': ticker,
                    'expiration': expiration,
                    'step': step,
                    'range_above_below': range_above_below
                }
                return
                
            # Process the data
            min_strike = max(0, spot - range_above_below)  # Ensure min_strike is not negative
            max_strike = spot + range_above_below

            # Check if we have valid data to process
            if calls.empty or puts.empty:
                st.error(f"No options data available for {ticker} on {expiration}")
                st.session_state['merged'] = None
                st.session_state['last_params'] = current_params
                return

            # Filter calls and puts based on the range
            calls_filtered = calls[(calls['strike'] >= min_strike) & (calls['strike'] <= max_strike)]
            puts_filtered = puts[(puts['strike'] >= min_strike) & (puts['strike'] <= max_strike)]

            # Check if filtered data is empty
            if calls_filtered.empty or puts_filtered.empty:
                st.warning(f"No options data found within the selected price range. Try increasing the range.")
                
            calls_filtered = calls_filtered[calls_filtered['strike'] % step == 0]
            puts_filtered = puts_filtered[puts_filtered['strike'] % step == 0]

            # Create merged dataframe
            try:
                merged = pd.merge(
                    calls_filtered[['strike', 'openInterest', 'lastPrice']].rename(
                        columns={'openInterest':'call_oi', 'lastPrice':'call_price'}),
                    puts_filtered[['strike', 'openInterest', 'lastPrice']].rename(
                        columns={'openInterest':'put_oi', 'lastPrice':'put_price'}),
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
            except Exception as e:
                st.error(f"Error processing options data: {str(e)}")
                logging.error(f"Data processing error: {str(e)}")
                st.session_state['merged'] = None
                st.session_state['last_params'] = current_params
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            logging.error(f"Unexpected error: {str(e)}")
            st.session_state['merged'] = None

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
else:
    with tab1:
        st.info("No data to display. Please select a valid expiration date and fetch data.")
    
    with tab2:
        st.info("No data to display. Please select a valid expiration date and fetch data.")
        
    with tab3:
        st.header("ℹ️ About This Tool", divider=True)
        st.write("""
        This tool visualizes options open interest for a given ticker and expiration date.
        
        - **Green bars**: Call option open interest
        - **Red bars**: Put option open interest
        - **Blue dashed line**: Current stock price
        - **Black dots**: Net delta (Call OI - Put OI)
        """)

