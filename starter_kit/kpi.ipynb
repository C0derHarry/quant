{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 100,
   "id": "9d5b0a2d",
   "metadata": {},
   "outputs": [],
   "source": [
    "import yfinance as yf\n",
    "import pandas as pd\n",
    "import datetime as dt\n",
    "import numpy as np"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 101,
   "id": "d4b1055c",
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "[*********************100%***********************]  1 of 1 completed\n"
     ]
    }
   ],
   "source": [
    "stocks = [\"TCS.NS\"]\n",
    "start_date = dt.datetime.now() - dt.timedelta(days=365)\n",
    "end_date = dt.datetime.now()\n",
    "data = {}\n",
    "for stock in stocks:\n",
    "    data[stock] = yf.download(stock, start=start_date, end=end_date, interval=\"1d\")"
   ]
  },
  {
   "cell_type": "markdown",
   "id": "6275bc32",
   "metadata": {},
   "source": [
    "## Compounded Annual Growth Rate (CAGR)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 102,
   "id": "322d27d5",
   "metadata": {},
   "outputs": [],
   "source": [
    "def CAGR(df):\n",
    "    df = df.copy()\n",
    "    df['return'] = df['Close'].pct_change()\n",
    "    df['cum_return'] = (1 + df['return']).cumprod()\n",
    "    n= len(df) / 252  # Assuming 252 trading days in a year\n",
    "    cagr = (df['cum_return'].iloc[-1]) ** (1/n) - 1\n",
    "    return cagr"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "51bfb2e0",
   "metadata": {},
   "outputs": [],
   "source": []
  },
  {
   "cell_type": "code",
   "execution_count": 103,
   "id": "c90f8727",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "CAGR for TCS.NS: -0.25230078793652044\n"
     ]
    }
   ],
   "source": [
    "for ticker in data:\n",
    "    print(\"CAGR for {}: {}\".format(ticker, CAGR(data[ticker])))"
   ]
  },
  {
   "cell_type": "markdown",
   "id": "ab853efb",
   "metadata": {},
   "source": [
    "## Volaitility "
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 104,
   "id": "81ccb115",
   "metadata": {},
   "outputs": [],
   "source": [
    "def volatility(df):\n",
    "    df = df.copy()\n",
    "    df['return'] = df['Close'].pct_change()\n",
    "    vol = np.std(df['return']) * np.sqrt(252)  # Annualized volatility\n",
    "    return vol"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 105,
   "id": "044db99b",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Voloatility for TCS.NS: 0.20573195152232368\n"
     ]
    }
   ],
   "source": [
    "for ticker in data:\n",
    "    print(\"Voloatility for {}: {}\".format(ticker, volatility(data[ticker])))"
   ]
  },
  {
   "cell_type": "markdown",
   "id": "9a8c5138",
   "metadata": {},
   "source": [
    "## Sharpe Ratio"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 106,
   "id": "22db1ce1",
   "metadata": {},
   "outputs": [],
   "source": [
    "def Sharpe(df):\n",
    "    df = df.copy()\n",
    "    sharpe = (CAGR(df)-0.03) / volatility(df)\n",
    "    return sharpe"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 107,
   "id": "f596f4e0",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Sharpe Ratio for TCS.NS: -1.3721776605316867\n"
     ]
    }
   ],
   "source": [
    "for ticker in data:\n",
    "    print(\"Sharpe Ratio for {}: {}\".format(ticker, Sharpe(data[ticker])))"
   ]
  },
  {
   "cell_type": "markdown",
   "id": "9f9727d2",
   "metadata": {},
   "source": [
    "## Sortino Ratio"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 114,
   "id": "e3e66d15",
   "metadata": {},
   "outputs": [],
   "source": [
    "\n",
    "def Sortino(df, rfr):\n",
    "    df = df.copy()\n",
    "    cagr = CAGR(df)\n",
    "    df['return'] = df['Close'].pct_change()\n",
    "    negative_return = np.where(df['return'] > 0,0,df['return'])\n",
    "    negative_volume = pd.Series(negative_return[negative_return != 0]).std() * np.sqrt(252)  # Annualized downside volatility\n",
    "    sortino = (cagr - rfr) / negative_volume\n",
    "    return sortino"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 115,
   "id": "d5bdcf87",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Sortino Ratio for TCS.NS: -2.0187783055568334\n"
     ]
    }
   ],
   "source": [
    "for ticker in data:\n",
    "    print(\"Sortino Ratio for {}: {}\".format(ticker, Sortino(data[ticker], 0.03)))"
   ]
  },
  {
   "cell_type": "markdown",
   "id": "8a6156c7",
   "metadata": {},
   "source": [
    "## Maximum Drawdown"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 116,
   "id": "54d969a3",
   "metadata": {},
   "outputs": [],
   "source": [
    "def max_dd(df):\n",
    "    df = df.copy()\n",
    "    df['return'] = df['Close'].pct_change()\n",
    "    df['cum_return'] = (1 + df['return']).cumprod()\n",
    "    df['peak'] = df['cum_return'].cummax()\n",
    "    df['drawdown'] = df['peak'] - df['cum_return']\n",
    "    return (df['drawdown']/ df['peak']).max()\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 117,
   "id": "a7559b44",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Maximum Drawdown for TCS.NS: 0.2962099102840837\n"
     ]
    }
   ],
   "source": [
    "for ticker in data:\n",
    "    print(\"Maximum Drawdown for {}: {}\".format(ticker, max_dd(data[ticker])))"
   ]
  },
  {
   "cell_type": "markdown",
   "id": "73504230",
   "metadata": {},
   "source": [
    "## Calamar Ratio"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 118,
   "id": "d21d007c",
   "metadata": {},
   "outputs": [],
   "source": [
    "def calamar(df):\n",
    "    df = df.copy()\n",
    "    return CAGR(df) / max_dd(df)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 119,
   "id": "5a1474bc",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Calamar Ratio for TCS.NS: -0.851763493309688\n"
     ]
    }
   ],
   "source": [
    "for ticker in data:\n",
    "    print(\"Calamar Ratio for {}: {}\".format(ticker, calamar(data[ticker])))"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "venv",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.13.3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
