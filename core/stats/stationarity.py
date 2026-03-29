import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller, kpss

def stationarity(df, column='Close', is_price=True):
    df=df.copy()
    df['return'] = df[column].pct_change() if is_price else df[column]

    def adf(df):
        res = adfuller(df['return'].dropna())
        test_statistic = res[0]
        p_value = res[1]
        return p_value < 0.05


    def kpss_helper(df):
        res = kpss(df['return'].dropna())
        test_statistic = res[0]
        p_value = res[1]
        return p_value < 0.05

    diff_counter = 0
    for diff in range(3):
        if adf(df) and not kpss_helper(df):
            break
        else:
            df['return'] = df['return'].diff()
            diff_counter+1
    
    return diff_counter