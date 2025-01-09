import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup, Comment
import logging

# ログの設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 関数: 株価終値を取得
def get_stock_price(date, ticker):
    try:
        while date.weekday() > 4:
            date -= timedelta(days=1)
        data = yf.download(ticker, start=date.strftime("%Y-%m-%d"), end=(date + timedelta(days=1)).strftime("%Y-%m-%d"))
        logging.debug(data)
        if not data.empty:
            stock_price = data['Adj Close'].iloc[0] if 'Adj Close' in data.columns else data['Close'].iloc[0]
            return float(stock_price)
        else:
            raise ValueError("No data found for the specified date.")
    except Exception as e:
        logging.error(f"Failed to fetch stock price: {str(e)}")
        raise

# 関数: TTMを取得
def get_ttm_rate(date):
    try:
        response = requests.get('https://www.77bank.co.jp/kawase/usd2024.html')
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        logging.debug(soup.prettify())

        target_date_str = date.strftime("%Y/%m/%d")
        logging.debug(f"Target date string: {target_date_str}")

        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if target_date_str in comment:
                rate_str = comment.find_parent('td').get_text().strip()
                logging.debug(f"Found comment: {comment} with rate: {rate_str}")
                return float(rate_str.replace(',', ''))
        raise ValueError(f"Failed to find the TTM rate for {target_date_str}.")
    except requests.RequestException as e:
        logging.error(f"Failed to fetch TTM rate: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error parsing TTM rate: {str(e)}")
        raise

# Streamlitアプリの設定
st.title("株価計算アプリ")

date_input = st.text_input("権利確定日 (YYYY-MM-DD):", value="2025-01-09")
stock_symbol = st.text_input("株式銘柄 (ティッカーシンボル):", value="AVGO")
stock_amount = st.number_input("株数:", value=0.0)

if st.button("計算"):
    try:
        date = datetime.strptime(date_input, "%Y-%m-%d")
        stock_price = get_stock_price(date, stock_symbol)
        ttm_rate = get_ttm_rate(date)
        total = stock_price * stock_amount * ttm_rate
        st.write(f"株価終値 (USD): {stock_price:.2f}")
        st.write(f"TTM (JPY): {ttm_rate:.2f}")
        st.write(f"総額 (JPY): {total:.2f}")
    except Exception as e:
        st.error(f"Error: {str(e)}")
