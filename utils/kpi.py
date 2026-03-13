import yfinance as yf
import pandas as pd
import datetime as dt
import numpy as np

## Compounded Annual Growth Rate (CAGR)

def CAGR(df, timeframe, column='Close', is_price=True):
    """
    Calculate CAGR.

    Args:
        df (pd.DataFrame): DataFrame with time series data
        timeframe (int): number of periods per year (e.g., 12 for monthly)
        column (str): column name to use
        is_price (bool): True if column is price series, False if already returns

    Returns:
        float: CAGR
    """
    df = df.copy()

    # if column not in df.columns:
    #     raise ValueError(f"Column '{column}' not found in DataFrame.")

    if is_price:
        df['return'] = df[column].pct_change()
    else:
        df['return'] = df[column]

    df['cum_return'] = (1 + df['return']).cumprod()
    n = len(df) / timeframe
    cagr = df['cum_return'].iloc[-1] ** (1/n) - 1
    return cagr


## Volaitility 

def volatility(df, timeframe, column='Close', is_price=True):
    df = df.copy()
    if is_price:
        df['return'] = df[column].pct_change()
    else:
        df['return'] = df[column]
    vol = df['return'].std() * np.sqrt(timeframe)  
    return vol


## Sharpe Ratio

def Sharpe(df, timeframe, column='Close', is_price=True):
    df = df.copy()
    c = CAGR(df, timeframe, column, is_price)
    v = volatility(df, timeframe, column, is_price)
    return (c - 0.03) / v # Assuming 3% Risk-Free Rate


## Sortino Ratio

def Sortino(df, rfr, timeframe):
    df = df.copy()
    cagr = CAGR(df)
    df['return'] = df['Close'].pct_change()
    negative_return = np.where(df['return'] > 0,0,df['return'])
    negative_volume = pd.Series(negative_return[negative_return != 0]).std() * np.sqrt(timeframe)
    sortino = (cagr - rfr) / negative_volume
    return sortino


## Maximum Drawdown

def max_dd(df, column='Close', is_price=True):
    df=df.copy()
    if is_price:
        df['return'] = df[column].pct_change()
    else:
        df['return'] = df[column]
    df['cum_return'] = (1 + df['return']).cumprod()
    df['peak'] = df['cum_return'].cummax()
    df['drawdown'] = df['peak'] - df['cum_return']
    return (df['drawdown']/ df['peak']).max()


## Calamar Ratio

def calamar(df, timeframe):
    df = df.copy()
    return CAGR(df, timeframe) / max_dd(df)