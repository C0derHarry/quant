import yfinance as yf
import pandas as pd
import datetime as dt
import numpy as np

## Compounded Annual Growth Rate (CAGR)

def CAGR(df, timeframe):
    df = df.copy()
    df['return'] = df['Close'].pct_change()
    df['cum_return'] = (1 + df['return']).cumprod()
    n= len(df) / timeframe  
    cagr = (df['cum_return'].iloc[-1]) ** (1/n) - 1
    return cagr


## Volaitility 

def volatility(df, timeframe):
    df = df.copy()
    df['return'] = df['Close'].pct_change()
    vol = np.std(df['return']) * np.sqrt(timeframe)  
    return vol

## Sharpe Ratio

def Sharpe(df):
    df = df.copy()
    sharpe = (CAGR(df)-0.03) / volatility(df)
    return sharpe

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

def max_dd(df):
    df = df.copy()
    df['return'] = df['Close'].pct_change()
    df['cum_return'] = (1 + df['return']).cumprod()
    df['peak'] = df['cum_return'].cummax()
    df['drawdown'] = df['peak'] - df['cum_return']
    return (df['drawdown']/ df['peak']).max()

## Calamar Ratio

def calamar(df, timeframe):
    df = df.copy()
    return CAGR(df, timeframe) / max_dd(df)