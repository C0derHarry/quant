import yfinance as yf
import pandas as pd
import datetime as dt
import numpy as np


# Moving Average Convergence Divergence (MACD)
def MACD(df, a=12, b=26, c=9, column='Close'):
    df = df.copy()
    df['EMA12'] = df['Close'].ewm(span=a, min_periods=a).mean()
    df['EMA26'] = df['Close'].ewm(span=b, min_periods=b).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=c, min_periods=c).mean()
    return df.loc[:, ['MACD', 'Signal']]


# Average True Range (ATR)
def ATR(df, period=14):
    df = df.copy()
    df['TR'] = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift(1)).abs(),
        (df['Low'] - df['Close'].shift(1)).abs()
    ], axis=1).max(axis=1, skipna=False)
    df['ATR'] = df['TR'].ewm(com=period).mean()
    return df[['ATR']]


# Bollinger Bands
def Boll_Bands(df, period=14, num_std_dev=2):
    df = df.copy()
    df['MA'] = df['Close'].rolling(window=period).mean()
    df['STD'] = df['Close'].rolling(window=period).std(ddof=0)  # Use ddof=0 for population std deviation
    df['Upper Band'] = df['MA'] + (num_std_dev * df['STD'])
    df['Lower Band'] = df['MA'] - (num_std_dev * df['STD'])
    df['Bandwidth'] = df['Upper Band'] - df['Lower Band']
    return df[['Upper Band', 'Lower Band', 'Bandwidth']]


# Relative Strength Index (RSI)
def RSI(df, period=14):
    df = df.copy()
    df['change'] = df['Close'] - df['Close'].shift(1)
    df['gain'] = np.where(df['change'] >= 0, df['change'], 0)
    df['loss'] = np.where(df['change'] < 0, -df['change'], 0)
    df['avg_gain'] = df['gain'].ewm(alpha = 1/period, min_periods=period).mean()
    df['avg_loss'] = df['loss'].ewm(alpha = 1/period, min_periods=period).mean()
    df['rs'] = df['avg_gain'] / df['avg_loss']
    df['RSI'] = 100 - (100 / (1 + df['rs']))
    return df[['RSI']]


# Average Directional Index (ADX)
def ADX(df, period=20):
    df = df.copy()
    df['TR'] = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift(1)).abs(),
        (df['Low'] - df['Close'].shift(1)).abs()
    ], axis=1).max(axis=1, skipna=False)
    
    df['+DM'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), 
                         np.maximum(df['High'] - df['High'].shift(1), 0), 0)
    df['-DM'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), 
                         np.maximum(df['Low'].shift(1) - df['Low'], 0), 0)
    
    df['+DI'] = 100 * (df['+DM'].rolling(window=period).sum() / df['TR'].rolling(window=period).sum())
    df['-DI'] = 100 * (df['-DM'].rolling(window=period).sum() / df['TR'].rolling(window=period).sum())
    
    df['DX'] = 100 * (np.abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI']))
    df['ADX'] = df['DX'].rolling(window=period).mean()
    
    return df[['ADX', '+DI', '-DI']]