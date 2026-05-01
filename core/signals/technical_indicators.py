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


# Exponential Moving Average
def EMA(df, period, column='Close'):
    df = df.copy()
    df[f'EMA{period}'] = df[column].ewm(span=period, min_periods=period).mean()
    return df[[f'EMA{period}']]


# Simple Moving Average
def SMA(df, period, column='Close'):
    df = df.copy()
    df[f'SMA{period}'] = df[column].rolling(window=period).mean()
    return df[[f'SMA{period}']]


# Stochastic Oscillator
def Stochastic(df, k_period=14, d_period=3):
    df = df.copy()
    df['Lowest_Low']   = df['Low'].rolling(window=k_period).min()
    df['Highest_High'] = df['High'].rolling(window=k_period).max()
    denom = (df['Highest_High'] - df['Lowest_Low']).replace(0, np.nan)
    df['%K'] = 100 * (df['Close'] - df['Lowest_Low']) / denom
    df['%D'] = df['%K'].rolling(window=d_period).mean()
    return df[['%K', '%D']]


# On-Balance Volume
def OBV(df):
    df = df.copy()
    df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
    return df[['OBV']]


# Volume-Weighted Average Price (rolling daily)
def VWAP(df, period=20):
    df = df.copy()
    df['TP']   = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['TP'] * df['Volume']).rolling(period).sum() / df['Volume'].rolling(period).sum()
    return df[['VWAP']]


# Commodity Channel Index
def CCI(df, period=20):
    df = df.copy()
    df['TP']       = (df['High'] + df['Low'] + df['Close']) / 3
    df['TP_MA']    = df['TP'].rolling(period).mean()
    df['Mean_Dev'] = df['TP'].rolling(period).apply(
        lambda x: np.mean(np.abs(x - x.mean())), raw=True
    )
    df['CCI'] = (df['TP'] - df['TP_MA']) / (0.015 * df['Mean_Dev'])
    return df[['CCI']]


# Parabolic SAR
def ParabolicSAR(df, step=0.02, max_step=0.2):
    """Returns DataFrame['SAR', 'Trend'] where Trend: 1=uptrend, -1=downtrend."""
    high  = df['High'].values
    low   = df['Low'].values
    close = df['Close'].values
    n     = len(close)

    sar   = np.full(n, np.nan)
    trend = np.ones(n, dtype=int)
    af    = step
    ep    = high[0]
    sar[0] = low[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]
        if trend[i - 1] == 1:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = min(sar[i], low[i - 1], low[max(0, i - 2)])
            if low[i] < sar[i]:
                trend[i] = -1
                sar[i]   = ep
                ep        = low[i]
                af        = step
            else:
                trend[i] = 1
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + step, max_step)
        else:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = max(sar[i], high[i - 1], high[max(0, i - 2)])
            if high[i] > sar[i]:
                trend[i] = 1
                sar[i]   = ep
                ep        = high[i]
                af        = step
            else:
                trend[i] = -1
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + step, max_step)

    result = pd.DataFrame(index=df.index)
    result['SAR']   = sar
    result['Trend'] = trend
    return result[['SAR', 'Trend']]