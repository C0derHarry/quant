import yfinance as yf
import pandas as pd
import datetime as dt

def download_stock_data(stocks, days, interval):
    """
    Download OHLC stock data for given stocks & return as a dict.

    Args:
        stocks (list of str): List of stock symbols.
        days (int): Number of days back from today.
        interval (str): Data interval (e.g., "1d", "1wk", "1mo").

    Returns:
        dict: {stock_symbol: DataFrame of OHLC data}
    """
    start_date = dt.datetime.today() - dt.timedelta(days=days)
    end_date = dt.datetime.today()

    # download data for all stocks at once

    ohlc_data = {}

    for stock in stocks:
        try:
            ohlc_data[stock] = yf.download(stock, start=start_date, end=end_date, interval=interval)
            ohlc_data[stock].dropna(inplace=True, how="all")  # drop rows with all NaN values
        except Exception as e:
            print(f"Error downloading data for {stock}: {e}")
            continue

    return ohlc_data
