import os
from dotenv import load_dotenv
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import pycurl
from io import BytesIO
import json
import time
from functools import wraps
import random
import csv
import argparse
from io import StringIO

# 加载 .env 文件
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.coingecko.com/api/v3"
API_KEY = os.getenv("COINGECKO_API_KEY")  # 从 .env 文件中读取 API 密钥

# 检查 API_KEY 是否成功加载
if not API_KEY:
    logger.error("API key not found. Please make sure COINGECKO_API_KEY is set in your .env file.")
    exit(1)

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_top_coins(start, end):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={end-start+1}&page={start//50 + 1}&sparkline=false"
    
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from CoinGecko: {e}")
        return None

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except:
                    if x == retries:
                        raise
                    sleep = (backoff_in_seconds * 2 ** x + random.uniform(0, 1))
                    time.sleep(sleep)
                    x += 1
        return wrapper
    return decorator

@retry_with_backoff(retries=3)
def get_coin_history(coin_id):
    url = f"{API_BASE_URL}/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": 30,
        "interval": "hourly",
        "x_cg_demo_api_key": API_KEY
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def process_data(data):
    df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("date", inplace=True)
    df.drop("timestamp", axis=1, inplace=True)
    
    # 对每天选取最接近9:00的数据点
    df['time'] = df.index.time
    df['time_diff'] = abs(df['time'] - pd.Timestamp('09:00:00').time())
    df = df.groupby(df.index.date).apply(lambda x: x.loc[x['time_diff'].idxmin()])
    df.index = df.index.droplevel(1)
    df.drop(['time', 'time_diff'], axis=1, inplace=True)
    
    return df

def analyze_coin(coin_id):
    try:
        data = get_coin_history(coin_id)
        df = process_data(data)
        
        # 计算指标
        df["returns"] = df["price"].pct_change()
        volatility = df["returns"].std()
        rsi = calculate_rsi(df)
        ma7 = df["price"].rolling(window=7).mean().iloc[-1]
        ma30 = df["price"].mean()
        volume_change = (data["total_volumes"][-1][1] / data["total_volumes"][0][1]) - 1
        
        # 评分
        score = 0
        if volatility < 0.05:
            score += 1
        if 30 <= rsi <= 70:
            score += 1
        if ma7 > ma30:
            score += 1
        if volume_change > 0:
            score += 1
        
        return {
            "coin_id": coin_id,
            "score": score,
            "volatility": volatility,
            "rsi": rsi,
            "ma7": ma7,
            "ma30": ma30,
            "volume_change": volume_change
        }
    except Exception as e:
        logger.error(f"Error analyzing {coin_id}: {e}")
        return None

def calculate_rsi(price_data, periods=14):
    delta = price_data['price'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=periods, min_periods=1).mean()
    avg_loss = loss.rolling(window=periods, min_periods=1).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1]  # Return the most recent RSI value

def get_historical_data(coin_id, days=14, max_retries=5, base_delay=1):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&x_cg_demo_api_key={API_KEY}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if 'prices' not in data:
                logger.warning(f"'prices' not found in data for {coin_id}. Data keys: {data.keys()}")
                return None
            
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data for {coin_id}: {e}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1 * (2 ** attempt))
                logger.info(f"Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"Failed to fetch data for {coin_id} after {max_retries} attempts.")
                return None

def save_to_csv(data, filename, mode='w'):
    file_exists = os.path.isfile(filename)
    
    with open(filename, mode, newline='') as csvfile:
        fieldnames = data[0].keys() if data else []
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if mode == 'w' or not file_exists:
            writer.writeheader()
        
        for row in data:
            writer.writerow(row)

def fetch_and_save_data(batches):
    all_coin_data = []
    for start, end in batches:
        logger.info(f"Fetching data for coins {start} to {end}")
        top_coins = get_top_coins(start, end)
        
        if top_coins is None:
            logger.error(f"Failed to fetch coins {start} to {end}. Skipping this batch.")
            continue
        
        for coin in top_coins:
            historical_data = get_historical_data(coin['id'])
            if historical_data is not None:
                coin_data = {
                    'id': coin['id'],
                    'symbol': coin['symbol'],
                    'name': coin['name'],
                    'historical_data': historical_data.to_json()
                }
                all_coin_data.append(coin_data)
            else:
                logger.warning(f"Skipping {coin['id']} due to missing historical data.")
            
            time.sleep(random.uniform(0.5, 1.5))
    
    save_to_csv(all_coin_data, 'data.csv')
    logger.info("All data fetched and saved to data.csv")

def analyze_data():
    with open('data.csv', 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        analyzed_data = []
        
        for row in reader:
            # 将 JSON 字符串解析为 Python 字典
            historical_data_dict = json.loads(row['historical_data'])
            
            # 将字典转换回 JSON 字符串，并用 StringIO 包装
            historical_data_io = StringIO(json.dumps(historical_data_dict))
            
            # 使用 StringIO 对象读取 JSON 数据
            historical_data = pd.read_json(historical_data_io)
            
            rsi = calculate_rsi(historical_data)
            analyzed_data.append({
                'id': row['id'],
                'symbol': row['symbol'],
                'name': row['name'],
                'score': rsi
            })
    
    save_to_csv(analyzed_data, 'coin_scores.csv')
    logger.info("Analysis complete. Results saved to coin_scores.csv")

def parse_batch(batch_str):
    start, end = map(int, batch_str.split('-'))
    return (start, end)

def main():
    parser = argparse.ArgumentParser(description='Process top coins from CoinGecko in batches.')
    parser.add_argument('batches', nargs='+', type=str, 
                        help='Batches to process, format: start-end (e.g., 1-50 51-100)')
    parser.add_argument('--fetch', action='store_true', help='Fetch new data from CoinGecko')
    parser.add_argument('--analyze', action='store_true', help='Analyze existing data')
    args = parser.parse_args()

    batches = [parse_batch(batch) for batch in args.batches]
    
    if args.fetch:
        fetch_and_save_data(batches)
    
    if args.analyze:
        analyze_data()

    if not args.fetch and not args.analyze:
        logger.warning("No action specified. Use --fetch to get new data or --analyze to process existing data.")

if __name__ == "__main__":
    main()
