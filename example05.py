import streamlit as st
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup, Comment
import logging
import concurrent.futures
from decimal import Decimal, getcontext, ROUND_DOWN
import pandas as pd
import pandas.tseries.offsets as offsets
from io import StringIO

# 精度を設定
getcontext().prec = 28

# ログの設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s')

# 株価終値を取得（修正版）
def fetch_stock_data(ticker: str) -> pd.DataFrame:
    """株価データを取得してDataFrameとして返す"""
    url = f"https://stooq.com/q/d/l/?s={ticker}&i=d"
    try:
        response = requests.get(url)
        response.raise_for_status()  # HTTPエラーを例外として処理
        data = StringIO(response.text)
        df = pd.read_csv(data)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except requests.exceptions.RequestException as e:
        logging.error(f"データの取得に失敗しました: {e}")
        return None
    except pd.errors.ParserError as e:
        logging.error(f"CSVデータの解析に失敗しました: {e}")
        return None
    except KeyError as e:
        logging.error(f"データに 'Date' 列が存在しません: {e}")
        return None

def find_closest_business_day(df: pd.DataFrame, target_date: datetime, max_days: int = 5) -> pd.Series:
    """指定日に最も近い営業日の株価データを返す"""
    for i in range(max_days):
        current_date = target_date - offsets.BDay(i)
        row = df[df['Date'] == current_date]
        if not row.empty:
            logging.info(f"{target_date.date()} のデータは見つかりませんでした。{current_date.date()} のデータを返します。")
            return row.iloc[0]
    logging.warning(f"{target_date.date()} から過去 {max_days} 日以内にデータが見つかりませんでした。")
    return None

def get_close_price(ticker: str, date: str) -> float:
    """指定日の株価終値を返す"""
    target_date = pd.to_datetime(date)
    target_year = target_date.year
    start_date = datetime(target_year, 1, 1)

    df = fetch_stock_data(ticker)
    if df is None:
        return None

    # 指定された年のデータを抽出
    df = df[(df['Date'] >= start_date) & (df['Date'] <= target_date)]

    if target_date.weekday() >= 5:  # 土日
        target_date = target_date - offsets.BDay(1)
        logging.info(f"指定日 {date} は営業日ではありません。前営業日 {target_date.date()} のデータを検索します。")

    row = df[df['Date'] == target_date]
    if not row.empty:
        return row['Close'].values[0]

    closest_row = find_closest_business_day(df, target_date)
    if closest_row is not None:
        return closest_row['Close']
    return None

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
            logging.debug(soup.prettify())

            target_date_str = f"●{date.year}/{date.month}/{date.day}●"
            logging.debug(f"対象日付の文字列: {target_date_str}")

            tds = soup.find_all('td', class_='activity')
            for td in tds:
                comments = td.find_all(string=lambda text: isinstance(text, Comment))
                for comment in comments:
                    if target_date_str in comment:
                        rate_str = td.get_text().strip()
                        logging.debug(f"コメント内で発見: {comment} - レート: {rate_str}")
                        return Decimal(str(rate_str.replace(',', '')))
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
    stock_price = get_close_price(stock_symbol, date.strftime("%Y-%m-%d"))
    if stock_price is not None:
      stock_price = Decimal(str(round(stock_price, 2)))
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
            logging.debug(soup.prettify())

            target_date_str = f"●{date.year}/{date.month}/{date.day}●"
            logging.debug(f"対象日付の文字列: {target_date_str}")

            tds = soup.find_all('td', class_='activity')
            for td in tds:
                comments = td.find_all(string=lambda text: isinstance(text, Comment))
                for comment in comments:
                    if target_date_str in comment:
                        rate_str = td.get_text().strip()
                        logging.debug(f"コメント内で発見: {comment} - レート: {rate_str}")
                        return Decimal(str(rate_str.replace(',', '')))
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
    stock_symbol = cols[i].text_input(f"銘柄{i+1} (ティッカー):", value="AVGO.US")
    stock_symbols.append(stock_symbol)

for i in range(4):
    stock_amount = cols[i].number_input(f"株数{i+1}:", value=0, step=1, format='%d', key=f"stock_amount{i+1}")
    stock_amounts.append(stock_amount)

if st.button("計算"):
    total_sum = Decimal(0)
    subtotals = []
    
    with requests.Session() as session:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_data = {executor.submit(fetch_data, date_inputs[i], stock_symbols[i], session): i for i in range(4)}

            for future in concurrent.futures.as_completed(future_to_data):
                i = future_to_data[future]
                try:
                    stock_price, ttm_rate = future.result()
                    if stock_price is None or ttm_rate is None:
                        cols[i].write(f"データ取得不要：未来の日付です。")
                        continue

                    subtotal_intermediate = stock_price * ttm_rate
                    subtotal_final = (subtotal_intermediate * Decimal(stock_amounts[i])).quantize(Decimal('0'), rounding=ROUND_DOWN)
                    
                    cols[i].markdown(f"株価終値 (USD): {stock_price}<br>TTM (JPY): {ttm_rate}<br>小計 (JPY): {subtotal_final}", unsafe_allow_html=True)
                    
                    subtotals.append(subtotal_final)
                    total_sum += subtotal_final
                except Exception as e:
                    cols[i].write(f"データ取得エラー: {str(e)}")

    st.write(f"総額 (JPY): {total_sum}")