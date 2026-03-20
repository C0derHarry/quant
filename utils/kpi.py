import pandas as pd
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
    return (c - 0.07) / v # Assuming 7% Risk-Free Rate


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


## Jensen's Alpha

def jensens_alpha(portfolio_rets, benchmark_rets, years, rf_annual=0.07):
    """
    Calculates Beta and Annualized Jensen's Alpha.
    
    Args:
        portfolio_rets (pd.Series): Series of strategy returns (any frequency)
        benchmark_rets (pd.Series): Series of benchmark returns (same frequency/length)
        years (float): Total duration of the backtest in years (e.g., 30/365 or 10.0)
        rf_annual (float): Annual Risk-Free Rate (default 0.07 for 7%)
    
    Returns: 
        beta, annualized_alpha, total_port_ret, total_bench_ret, ann_port_ret, ann_bench_ret
    """
    # 1. Align the data
    df_link = pd.DataFrame({
        'port': portfolio_rets,
        'bench': benchmark_rets
    }).fillna(0)
    
    # 2. Calculate Beta (Covariance / Variance)
    covariance_matrix = np.cov(df_link['port'], df_link['bench'])
    beta = covariance_matrix[0, 1] / covariance_matrix[1, 1]
    
    # 3. Calculate Total Realized Returns (Cumulative)
    total_port_ret = (1 + df_link['port']).prod() - 1
    total_bench_ret = (1 + df_link['bench']).prod() - 1
    
    # 4. Annualize the returns
    # Formula: (1 + Total Return)^(1/years) - 1
    ann_port_ret = (1 + total_port_ret)**(1/years) - 1
    ann_bench_ret = (1 + total_bench_ret)**(1/years) - 1
    
    # 5. Jensen's Alpha (Annualized)
    # Alpha = Rp_ann - [Rf_ann + Beta * (Rb_ann - Rf_ann)]
    alpha_ann = ann_port_ret - (rf_annual + beta * (ann_bench_ret - rf_annual))
    
    return beta, alpha_ann, total_port_ret, total_bench_ret, ann_port_ret, ann_bench_ret