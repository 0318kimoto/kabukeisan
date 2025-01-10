import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup, Comment
import logging

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 関数: 株価終値を取得
def get_stock_price(date, ticker):
    try:
        while date.weekday() > 4:  # 週末は平日に戻す
            date -= timedelta(days=1)
        data = yf.download(ticker, start=date.strftime("%Y-%m-%d"), end=(date + timedelta(days=1)).strftime("%Y-%m-%d"))
        logging.info(data)
        if not data.empty:
            stock_price = data['Adj Close'].iloc[0] if 'Adj Close' in data.columns else data['Close'].iloc[0]
            return float(stock_price)
        else:
            raise ValueError("指定された日付のデータが見つかりませんでした。")
    except Exception as e:
        logging.error(f"株価の取得に失敗しました: {str(e)}")
        raise

# 関数: TTMレートを取得
def get_ttm_rate(date):
    retry_limit = 10  # 最大リトライ回数を設定
    retries = 0
    while retries < retry_limit:
        try:
            # URLを動的に変更
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
            date -= timedelta(days=1)  # 前日を試す
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

date_input = st.text_input("権利確定日 (YYYYMMDD):", value="20250109")
stock_symbol = st.text_input("株式銘柄 (ティッカーシンボル):", value="AVGO")
stock_amount = st.number_input("株数:", value=0, step=1)

if st.button("計算"):
    try:
        date = datetime.strptime(date_input, "%Y%m%d")
        stock_price = get_stock_price(date, stock_symbol)
        ttm_rate = get_ttm_rate(date)
        total = stock_price * stock_amount * ttm_rate
        st.write(f"株価終値 (USD): {stock_price:.2f}")
        st.write(f"TTM (JPY): {ttm_rate:.2f}")
        st.write(f"総額 (JPY): {total:.2f}")
    except ValueError as ve:
        st.error(f"エラー: {str(ve)}")
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
