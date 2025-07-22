import yfinance as yf
import pandas as pd
import datetime as dt

def download_stock_data(stocks, days, interval="1d"):
    """
    Download stock close price data for given stocks & export to Excel.

    Args:
        stocks (list of str): List of stock symbols.
        days (int): Number of days back from today.
        interval (str): Data interval (e.g., "1d", "1wk", "1mo").
        filename (str): Name of the output Excel file.

    Returns:
        pd.DataFrame: DataFrame of downloaded stock data.
    """
    start_date = dt.datetime.now() - dt.timedelta(days=days)
    end_date = dt.datetime.now()
    
    data = yf.download(stocks, start=start_date, end=end_date, interval=interval)["Close"]
    # data.to_excel(filename, index=True, engine="openpyxl")
    # print(f"Data saved to {filename}")
    return data
