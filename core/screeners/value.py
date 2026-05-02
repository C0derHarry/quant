import numpy as np
import pandas as pd
import os
import sys

from core.data import fetch_financial_data


## Joel Greenblatt's magic formula

import pandas as pd

def magic_formula_rank(ticker_list):
    '''
    Uses Joel Greenblatt's magic formula to calculate Earnings Yield and Return On Capital.
    Banking/financial stocks use Pretax Income and equity-based invested capital as proxies.

    Args:
        ticker_list (List): List of all the stocks you want to compare

    Returns:
        rank_df (pd.DataFrame): df of all your stocks with individual and combined ranks
    '''

    ticker_list = [t if '.NS' in t else f'{t}.NS' for t in ticker_list]

    financial_data = fetch_financial_data(ticker_list)

    results = []

    for ticker in ticker_list:
        try:
            data = financial_data.get(ticker)
            if not data: continue

            info = data['info']
            total_cash = info.get('totalCash', 0) or 0
            total_debt = info.get('totalDebt', 0) or 0
            market_cap = info.get('marketCap', 0) or 0

            fin = data['financials']
            bs  = data['balance_sheet']

            # EBIT: use directly if available, else fall back to Pretax Income (banks/holding cos)
            if 'EBIT' in fin.index:
                EBIT = fin.loc['EBIT'].iloc[0]
            elif 'Pretax Income' in fin.index:
                EBIT = fin.loc['Pretax Income'].iloc[0]
            else:
                print(f"Skipping {ticker}: no EBIT or Pretax Income in financials")
                continue

            if EBIT is None or (hasattr(EBIT, '__float__') and pd.isna(float(EBIT))):
                print(f"Skipping {ticker}: EBIT is null")
                continue

            # Invested capital: standard (Net PPE + working capital), then balance-sheet fallback for banks
            if 'Current Assets' in bs.index and 'Current Liabilities' in bs.index:
                net_ppe      = bs.loc['Net PPE'].iloc[0] if 'Net PPE' in bs.index else 0
                working_cap  = bs.loc['Current Assets'].iloc[0] - bs.loc['Current Liabilities'].iloc[0]
                invested_capital = (net_ppe or 0) + working_cap
            elif 'Invested Capital' in bs.index:
                invested_capital = bs.loc['Invested Capital'].iloc[0]
            elif 'Common Stock Equity' in bs.index:
                invested_capital = bs.loc['Common Stock Equity'].iloc[0]
            elif 'Stockholders Equity' in bs.index:
                invested_capital = bs.loc['Stockholders Equity'].iloc[0]
            else:
                print(f"Skipping {ticker}: cannot determine invested capital")
                continue

            if not invested_capital or pd.isna(float(invested_capital)):
                print(f"Skipping {ticker}: invested capital is null/zero")
                continue

            enterprise_value = market_cap + total_debt - total_cash

            earnings_yield = float(EBIT) / enterprise_value if enterprise_value > 0 else 0
            ROC = float(EBIT) / float(invested_capital) if float(invested_capital) > 0 else 0

            results.append({
                "Ticker": ticker,
                "Earnings Yield": earnings_yield,
                "ROC": ROC
            })

        except Exception as e:
            print(f'Error calculating rank for {ticker}: {e}')

    # 2. Create DataFrame
    rank_df = pd.DataFrame(results)

    # 3. Calculate Ranks
    # For EY and ROC, higher is better, so we rank descending (ascending=False)
    rank_df['EY Rank'] = rank_df['Earnings Yield'].rank(ascending=False)
    rank_df['ROC Rank'] = rank_df['ROC'].rank(ascending=False)

    # 4. Combined Rank
    rank_df['Combined Rank'] = rank_df['EY Rank'] + rank_df['ROC Rank']
    
    # Sort by final rank (lower score is better)
    return rank_df.sort_values('Combined Rank').reset_index(drop=True)


## Quality at a reasonable price (QARP)

def qarp_screener(ticker_list):
    '''
    Gives you all the stocks within a particular sector that provide high quality but are currently at a very reasonable price. 
    These stocks have high upside potential. 

    Args: 
        ticker_list (List): List of all the tickers

    Returns: 
        results_df (pd.Dataframe): 
    '''

    ticker_list = [t if '.NS' in t else f'{t}.NS' for t in ticker_list]

    financial_data = fetch_financial_data(ticker_list)

    results = []
    for ticker in ticker_list:
        try:
            data = financial_data.get(ticker)
            if not data:
                continue
            inf = data['info']
            fin = data['financials']
            bs  = data['balance_sheet']

            # ROE: Net Income / Stockholders Equity, fall back to info.returnOnEquity
            try:
                net_income = fin.loc['Net Income'].iloc[0]
                equity_row = 'Stockholders Equity' if 'Stockholders Equity' in bs.index else 'Common Stock Equity'
                equity = bs.loc[equity_row].iloc[0]
                return_on_equity = float(net_income) / float(equity)
            except Exception:
                roe_raw = inf.get('returnOnEquity')
                if roe_raw is None:
                    print(f"Could not process {ticker}: no ROE data")
                    continue
                return_on_equity = float(roe_raw)

            # D/E: yfinance reports as percentage (e.g. 45 means 0.45); None for banks/some industrials
            # Fall back to priceToBook proxy: P/B < 3 treated as acceptable leverage
            de_raw = inf.get('debtToEquity')
            if de_raw is not None:
                debt_to_equity = de_raw / 100
                is_healthy = debt_to_equity < 0.5
            else:
                ptb = inf.get('priceToBook')
                debt_to_equity = None
                is_healthy = ptb is not None and ptb < 3.0

            # P/E: handle None forwardPE or trailingPE
            current_pe  = inf.get('forwardPE')
            trailing_pe = inf.get('trailingPE')
            if current_pe is None:
                is_cheap = False
            elif trailing_pe is not None:
                is_cheap = current_pe < 15 or current_pe < (trailing_pe * 0.9)
            else:
                is_cheap = current_pe < 15

            is_quality = return_on_equity > 0.20

            criteria_met = sum([is_quality, is_healthy, is_cheap])
            if criteria_met == 3:
                verdict = "BUY"
            elif criteria_met == 2:
                verdict = "WATCH"
            else:
                verdict = "AVOID"

            results.append({
                "Ticker":      ticker,
                "ROE":         f"{return_on_equity:.2%}",
                "D/E":         round(debt_to_equity, 2) if debt_to_equity is not None else "N/A",
                "Forward P/E": round(current_pe, 2) if current_pe is not None else "N/A",
                "Verdict":     verdict,
            })

        except Exception as e:
            print(f"Could not process {ticker}: {e}")

    return pd.DataFrame(results)