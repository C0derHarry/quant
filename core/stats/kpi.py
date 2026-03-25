import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.stats.diagnostic import acorr_ljungbox

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

## Rolling Sharpe

def rolling_sharpe(df, timeframe, window, column='Close', is_price=True):
    df = df.copy()
    
    if is_price:
        df['return'] = df[column].pct_change()
    else:
        df['return'] = df[column]
    
    df['excess_returns'] = df['return'] - 0.07/timeframe
    rolling_mean = df['excess_returns'].rolling(window=window).mean()
    rolling_std = df['excess_returns'].rolling(window=window).std()

    df['rolling_sharpe'] = (rolling_mean/rolling_std) * np.sqrt(timeframe)
    return df['rolling_sharpe']


## Sortino Ratio

def Sortino(df, timeframe, rfr=0.07):
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


## Drawdown Duration

def drawdown_analysis(df, column='Close', is_price=True):
    df=df.copy()
    if is_price:
        df['return'] = df[column].pct_change()
    else:
        df['return'] = df[column]
    cum_returns = (1 + df['return']).cumprod()
    
    # Running maximum (the "high water mark")
    rolling_max = cum_returns.cummax()
    
    # Drawdown at each point
    drawdown = (cum_returns - rolling_max) / rolling_max
    
    return drawdown, cum_returns, rolling_max


## Underwater Periods

def underwater_periods(df, column='Close', is_price=True):
    drawdown, cum_returns, rolling_max = drawdown_analysis(df, column, is_price)
    
    # Boolean mask: are we underwater?
    is_underwater = drawdown < 0
    
    # Label each consecutive underwater streak
    streak_id = (is_underwater != is_underwater.shift()).cumsum()
    streak_id = streak_id.where(is_underwater)  # only keep underwater streaks
    
    periods = []
    for sid, group in drawdown.groupby(streak_id):
        start = group.index[0]
        end = group.index[-1]
        duration = len(group)
        max_dd = drawdown.loc[start:end].min()
        
        periods.append({
            "start":        start,
            "end":          end,
            "duration":     duration,       # in periods (months if monthly data)
            "max_drawdown": max_dd,
            "recovered":    end != drawdown.index[-1]  # has it recovered?
        })
    
    return pd.DataFrame(periods).sort_values("max_drawdown")


## Summarise the drawdown

def drawdown_summary(df, column='Close', is_price=True):
    dd, _, _ = drawdown_analysis(df, column, is_price)
    uw        = underwater_periods(df, column, is_price)
    
    print(f"Max Drawdown:               {dd.min():.2%}")
    print(f"Current Drawdown:           {dd.iloc[-1]:.2%}")
    print(f"Avg Underwater Duration:    {uw['duration'].mean():.1f} periods")
    print(f"Longest Underwater Period:  {uw['duration'].max()} periods")
    print(f"Number of Drawdowns:        {len(uw)}")
    print(f"Still Underwater:           {dd.iloc[-1] < 0}")


## Volatility clustering

def squared_returns_plot(df, column="Close", is_price=True, lags=20, significance=0.05):
    df=df.copy()
    if is_price:
        returns = df[column].pct_change()
    else:
        returns = df[column]
    squared_returns = returns ** 2
    
    # Calculate autocorrelations for each lag
    acf_values = [squared_returns.autocorr(lag=i) for i in range(1, lags + 1)]
    
    # Significance bounds (95% confidence interval)
    n = len(returns)
    sig_bound = 1.96 / np.sqrt(n)
    
    # Ljung-Box test for overall significance
    lb_test = acorr_ljungbox(squared_returns, lags=lags, return_df=True)
    
    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # --- Top: ACF bar chart ---
    lags_range = range(1, lags + 1)
    colors = ["red" if abs(v) > sig_bound else "steelblue" for v in acf_values]
    
    ax1.bar(lags_range, acf_values, color=colors, alpha=0.7, edgecolor="black", linewidth=0.5)
    ax1.axhline(y=sig_bound,  color="red", linestyle="--", linewidth=1.2, label=f"95% CI (±{sig_bound:.3f})")
    ax1.axhline(y=-sig_bound, color="red", linestyle="--", linewidth=1.2)
    ax1.axhline(y=0, color="black", linewidth=0.8)
    ax1.set_title("Squared Returns Autocorrelation (Volatility Clustering)", fontsize=14)
    ax1.set_xlabel("Lag")
    ax1.set_ylabel("Autocorrelation")
    ax1.set_xticks(list(lags_range))
    ax1.legend()
    
    # --- Bottom: Ljung-Box p-values ---
    ax2.bar(lags_range, lb_test["lb_pvalue"], color="steelblue", alpha=0.7, edgecolor="black", linewidth=0.5)
    ax2.axhline(y=significance, color="red", linestyle="--", linewidth=1.2, label=f"p = {significance}")
    ax2.set_title("Ljung-Box Test p-values (H0: No Autocorrelation)", fontsize=14)
    ax2.set_xlabel("Lag")
    ax2.set_ylabel("p-value")
    ax2.set_xticks(list(lags_range))
    ax2.legend()
    
    plt.tight_layout()
    plt.show()
    
    # Summary
    sig_lags = [i+1 for i, v in enumerate(acf_values) if abs(v) > sig_bound]
    print(f"Significant lags: {sig_lags}")
    print(f"Ljung-Box p-value at lag 20: {lb_test['lb_pvalue'].iloc[-1]:.4f}")
    print(f"Volatility clustering present: {lb_test['lb_pvalue'].iloc[-1] < significance}")
    
    return pd.DataFrame({"lag": list(lags_range), "acf": acf_values, "significant": [abs(v) > sig_bound for v in acf_values]})

## Rolling Alpha

def rolling_alpha(strategy_returns, benchmark_returns, timeframe, window):
    """
    USE YOUR OWN KNOWLEDGE TO MAKE THIS BETTER
    """
    alphas = []
    for i in range(window, len(strategy_returns)):
        y = strategy_returns.iloc[i-window:i]
        x = benchmark_returns.iloc[i-window:i]
        x = sm.add_constant(x)
        
        model = sm.OLS(y, x).fit()
        # model.params[0] is the Alpha (intercept)
        alphas.append(model.params[0] * timeframe) # Annualized
        
    return pd.Series(alphas, index=strategy_returns.index[window:])



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