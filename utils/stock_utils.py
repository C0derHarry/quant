import yfinance as yf
import pandas as pd
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

def fetch_ohlcv_data(stocks, days, interval):
    """
    Download ohlcv stock data for given stocks & return as a dict.

    Args:
        stocks (list of str): List of stock symbols.
        days (int): Number of days back from today.
        interval (str): Data interval (e.g., "1d", "1wk", "1mo").

    Returns:
        dict: {stock_symbol: DataFrame of ohlcv data}
    """
    start_date = dt.datetime.today() - dt.timedelta(days=days)
    end_date = dt.datetime.today()

    # 1. Download everything in one go
    # group_by='ticker' makes it much easier to iterate later
    print(f"Downloading data for {len(stocks)} tickers...")
    full_df = yf.download(
        stocks, 
        start=start_date, 
        end=end_date, 
        interval=interval, 
        group_by='ticker', 
        progress=False,
        threads=True # Uses multi-threading for even more speed
    )

    ohlcv_data = {}

    # 2. If only one stock was requested, yfinance returns a standard DF
    # If multiple, it returns a Multi-Index. This handles both.
    if len(stocks) == 1:
        ticker = stocks[0]
        if not full_df.empty:
            ohlcv_data[ticker] = full_df.dropna(how="all")
    else:
        # 3. Iterate through the top level of the Multi-Index (the Tickers)
        for ticker in stocks:
            try:
                # Extract the sub-dataframe for this specific ticker
                if ticker in full_df.columns.levels[0]:
                    ticker_df = full_df[ticker].dropna(how="all")
                    
                    # Check if the data is actually there (handles delisted tickers)
                    if not ticker_df.empty:
                        ohlcv_data[ticker] = ticker_df
                    else:
                        print(f"Skipping {ticker}: No data found.")
                else:
                    print(f"Skipping {ticker}: Ticker not found in results.")
                    
            except Exception as e:
                print(f"Error processing {ticker}: {e}")

    print(f"Successfully downloaded {len(ohlcv_data)}/{len(stocks)} stocks.")
    return ohlcv_data


# 1. Define a function for a single ticker download
def fetch_financial_data(ticker_list):
    """
    Fetches balance sheet, financials, cash flow, and info for a list of tickers 
    using multithreading for speed.
    
    Args:
        ticker_list (list): List of NSE/BSE ticker strings.
        max_workers (int): Number of simultaneous threads.
        
    Returns:
        dict: A nested dictionary where keys are tickers and values are their data.
    """
    def fetch_single_ticker(ticker):
        try:
            tk = yf.Ticker(ticker)
            # Return a tuple of the ticker name and its data dictionary
            return ticker, {
                "balance_sheet": tk.balance_sheet,
                "financials": tk.financials,
                "cash_flow": tk.cashflow,
                "info": tk.info
            }
        except Exception as e:
            print(f"Error for {ticker}: {e}")
            return ticker, None

    financial_dir = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_single_ticker, ticker_list)

    # 3. Process the results into your main dictionary
    for ticker, data in results:
        if data:
            financial_dir[ticker] = data

    print("\n--- All downloads complete ---")
    return financial_dir