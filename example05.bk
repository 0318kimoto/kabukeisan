import streamlit as st
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
import pandas.tseries.offsets as offsets
import logging

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def main():
    st.title("株価終値取得アプリ")

    ticker = st.text_input("ティッカーを入力してください (例: AVGO.US)", "AVGO.US")
    date_input = st.date_input("株価を取得する日付を選択してください", datetime.today())

    if st.button("株価を取得"):
        try:
            stock_price = get_close_price(ticker, date_input.strftime("%Y-%m-%d"))
            if stock_price:
                st.success(f"{date_input.strftime('%Y-%m-%d')} の株価終値: {stock_price}")
            else:
                st.error(f"{date_input.strftime('%Y-%m-%d')} の株価が取得できませんでした")
        except ValueError:
            st.error("無効な日付形式です。日付を選択してください。")

if __name__ == "__main__":
    main()
