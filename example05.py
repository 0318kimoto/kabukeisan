import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup, Comment
import logging
import concurrent.futures

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# 株価終値を取得（キャッシュを利用）
@st.cache_data
def get_stock_price(date, ticker):
    retry_limit = 10
    retries = 0
    while retries < retry_limit:
        try:
            while date.weekday() > 4:
                date -= timedelta(days=1)
            start_date = date - timedelta(days=7)
            data = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"), end=(date + timedelta(days=1)).strftime("%Y-%m-%d"))
            logging.info(data)
            if not data.empty:
                stock_price = data['Adj Close'].iloc[-1] if 'Adj Close' in data.columns else data['Close'].iloc[-1]
                return float(stock_price)
            else:
                logging.warning(f"{date} のデータが見つかりませんでした。前日を試します。")
                date -= timedelta(days=1)
                retries += 1
        except Exception as e:
            logging.error(f"株価の取得に失敗しました: {str(e)}")
            raise
    raise ValueError(f"{retry_limit} 回試みても指定された日付のデータが見つかりませんでした。")

# TTMレートを取得（キャッシュを利用）
@st.cache_data
def get_ttm_rate(date):
    retry_limit = 10
    retries = 0
    while retries < retry_limit:
        try:
            url = f"https://www.77bank.co.jp/kawase/usd{date.year}.html"
            response = requests.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            logging.info(soup.prettify())

            target_date_str = f"●{date.year}/{date.month}/{date.day}●"
            logging.info(f"対象日付の文字列: {target_date_str}")

            tds = soup.find_all('td', class_='activity')
            for td in tds:
                comments = td.find_all(string=lambda text: isinstance(text, Comment))
                for comment in comments:
                    if target_date_str in comment:
                        rate_str = td.get_text().strip()
                        logging.info(f"コメント内で発見: {comment} - レート: {rate_str}")
                        return float(rate_str.replace(',', ''))
            raise ValueError(f"{target_date_str} のTTMレートが見つかりませんでした。")
        except ValueError as e:
            logging.warning(f"{date}のTTMレートが見つかりませんでした。前日を試します。")
            date -= timedelta(days=1)
            retries += 1
        except requests.RequestException as e:
            logging.error(f"TTMレートの取得に失敗しました: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"TTMレート解析中にエラーが発生しました: {str(e)}")
            raise
    raise ValueError(f"{retry_limit} 回試みてもTTMレートが見つかりませんでした。")

# 並列処理のための関数
def fetch_data(date_input, stock_symbol, session):
    date = datetime.strptime(date_input, "%Y%m%d")
    if date > datetime.now():
        return None, None
    stock_price = get_stock_price(date, stock_symbol)
    ttm_rate = get_ttm_rate_with_session(date, session)
    return stock_price, ttm_rate

# HTTPセッションを利用したTTMレートの取得
def get_ttm_rate_with_session(date, session):
    retry_limit = 10
    retries = 0
    while retries < retry_limit:
        try:
            url = f"https://www.77bank.co.jp/kawase/usd{date.year}.html"
            response = session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            logging.info(soup.prettify())

            target_date_str = f"●{date.year}/{date.month}/{date.day}●"
            logging.info(f"対象日付の文字列: {target_date_str}")

            tds = soup.find_all('td', class_='activity')
            for td in tds:
                comments = td.find_all(string=lambda text: isinstance(text, Comment))
                for comment in comments:
                    if target_date_str in comment:
                        rate_str = td.get_text().strip()
                        logging.info(f"コメント内で発見: {comment} - レート: {rate_str}")
                        return float(rate_str.replace(',', ''))
            raise ValueError(f"{target_date_str} のTTMレートが見つかりませんでした。")
        except ValueError as e:
            logging.warning(f"{date}のTTMレートが見つかりませんでした。前日を試します。")
            date -= timedelta(days=1)
            retries += 1
        except requests.RequestException as e:
            logging.error(f"TTMレートの取得に失敗しました: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"TTMレート解析中にエラーが発生しました: {str(e)}")
            raise
    raise ValueError(f"{retry_limit} 回試みてもTTMレートが見つかりませんでした。")

# Streamlitアプリの設定
st.title("株価計算アプリ")

# 年度設定を追加（スライダー付き）
year = st.number_input("Year:", value=2025, step=1, format='%d')

cols = st.columns(4)
date_inputs = []
stock_symbols = []
stock_amounts = []

# デフォルト日付を設定
default_dates = [f"{year}0315", f"{year}0615", f"{year}0915", f"{year}1215"]

for i in range(4):
    date_input = cols[i].text_input(f"Vesting date{i+1} (YYYYMMDD):", value=default_dates[i])
    date_inputs.append(date_input)

for i in range(4):
    stock_symbol = cols[i].text_input(f"銘柄{i+1} (ティッカー):", value="AVGO")
    stock_symbols.append(stock_symbol)

for i in range(4):
    stock_amount = cols[i].number_input(f"株数{i+1}:", value=0, step=1, format='%d', key=f"stock_amount{i+1}")
    stock_amounts.append(stock_amount)

if st.button("計算"):
    total_sum = 0
    subtotals = []
    
    with requests.Session() as session:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_data = {executor.submit(fetch_data, date_inputs[i], stock_symbols[i], session): i for i in range(4)}

            for future in concurrent.futures.as_completed(future_to_data):
                i = future_to_data[future]
                try:
                    stock_price, ttm_rate = future.result()
                    if stock_price is None or ttm_rate is None:
                        cols[i].write(f"データ取得不要：未来の日付です。")
                        continue
                    subtotal = stock_price * stock_amounts[i] * ttm_rate
                    subtotals.append(subtotal)
                    cols[i].write(f"株価終値 (USD): {stock_price:.2f}\nTTM (JPY): {subtotal:.2f}")
                    total_sum += subtotal
                except Exception as e:
                    cols[i].write(f"データ取得エラー: {str(e)}")

    st.write(f"総額 (JPY): {total_sum:.2f}")
