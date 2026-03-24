import numpy as np
import pandas as pd
import os
import sys

from core.data import fetch_financial_data


## Joel Greenblatt's magic formula

import pandas as pd

def magic_formula_rank(ticker_list):
    '''
    DO NOT PASS STOCKS BELONGING TO BANKING SECTOR
    Uses Joel Greenblatt's magic formula to calculate the Earnings Yield and Return On Capital of all the stocks in your universe.
    Return a dataframe of all the stocks with their individual Earnings Yield rank, ROC rank and combined rank.

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

            # Extract Info metrics with fallback to 0
            info = data['info']
            total_cash = info.get('totalCash', 0) or 0
            total_debt = info.get('totalDebt', 0) or 0
            market_cap = info.get('marketCap', 0) or 0

            print(f'total cash = {total_cash}, total debt = {total_debt}, market_cap = {market_cap}')

            # Extract Financials/Balance Sheet
            ebit_series = data['financials'].loc['EBIT']
            net_ppe_series = data['balance_sheet'].loc['Net PPE']
            curr_assets_series = data['balance_sheet'].loc['Current Assets']
            curr_liabs_series = data['balance_sheet'].loc['Current Liabilities']

            if any(x is None for x in [ebit_series, net_ppe_series, curr_assets_series, curr_liabs_series]):
                print(f"Skipping {ticker}: Missing key line items.")
                continue

            EBIT = ebit_series.iloc[0]
            fixed_assets = net_ppe_series.iloc[0]
            working_capital = curr_assets_series.iloc[0] - curr_liabs_series.iloc[0]

            print(f'EBIT = {EBIT}, fixed_assets = {fixed_assets}, working_capital = {working_capital}')
            
            # Formula Calculations
            enterprise_value = market_cap + total_debt - total_cash
            
            # Earnings Yield: EBIT / EV
            earnings_yield = EBIT / enterprise_value if enterprise_value > 0 else 0
            
            # ROC: EBIT / (Fixed Assets + Working Capital)
            invested_capital = fixed_assets + working_capital
            ROC = EBIT / invested_capital if invested_capital > 0 else 0

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
    financial_data = fetch_financial_data(ticker_list)

    results = []
    for ticker in ticker_list:
        try:
            info = financial_data.get(ticker)

            # Return on equity(ROE) = Net Income/Shareholders Equity
            net_income = info['financials'].loc['Net Income']
            shareholders_equity = info['balance_sheet'].loc['Stockholders Equity']

            return_on_equity = net_income.iloc[0]/shareholders_equity.iloc[0]

            # --- Filter 2: Financial Health (Debt-to-Equity) ---
            debt_to_equity = info['info'].get('debtToEquity')/100

            # --- Filter 3: The Value Hook (P/E Ratios) ---
            current_pe = info['info'].get('forwardPE')
            trailing_pe = info['info'].get('trailingPE')
            
            # Logic Check
            is_quality = return_on_equity > 0.20
            is_healthy = debt_to_equity < 0.5
            is_cheap = current_pe < 15 or current_pe < (trailing_pe * 0.9) # Simple proxy for 'on sale'

            # if is_quality and is_healthy and is_cheap:
            results.append({
                "Ticker": ticker,
                "ROE": f"{return_on_equity:.2%}",
                "D/E": round(debt_to_equity, 2),
                "Forward P/E": round(current_pe, 2)
            })

            
        except Exception as e:
            print(f"Could not process {ticker}: {e}")

    return pd.DataFrame(results)