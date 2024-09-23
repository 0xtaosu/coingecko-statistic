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
            
            if not all(key in data for key in ['prices', 'market_caps', 'total_volumes']):
                logger.warning(f"Missing data for {coin_id}. Data keys: {data.keys()}")
                return None
            
            historical_data = {
                'prices': data['prices'],
                'market_caps': data['market_caps'],
                'total_volumes': data['total_volumes']
            }
            
            return json.dumps(historical_data)
        
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
                    'historical_data': historical_data
                }
                all_coin_data.append(coin_data)
            else:
                logger.warning(f"Skipping {coin['id']} due to missing historical data.")
            
            time.sleep(random.uniform(0.5, 1.5))
    
    # 将所有数据保存到一个 CSV 文件
    df = pd.DataFrame(all_coin_data)
    df.to_csv('data.csv', index=False)
    logger.info("All data fetched and saved to data.csv")

def analyze_data(coin_range='1-300'):
    start, end = map(int, coin_range.split('-'))
    
    # 读取数据
    df = pd.read_csv('data.csv')
    
    print("Columns in the CSV file:", df.columns.tolist())
    
    # 添加 rank 列
    df['rank'] = list(range(1, len(df) + 1))
    
    # 只分析指定范围内的数据
    df = df[(df['rank'] >= start) & (df['rank'] <= end)]
    
    results = []
    for _, row in df.iterrows():
        print(f"Processing {row['name']}:")
        
        historical_data = json.loads(row['historical_data'])
        
        prices_df = pd.DataFrame(historical_data['prices'], columns=['timestamp', 'price'])
        volumes_df = pd.DataFrame(historical_data['total_volumes'], columns=['timestamp', 'volume'])
        market_caps_df = pd.DataFrame(historical_data['market_caps'], columns=['timestamp', 'market_cap'])
        
        coin_data = prices_df.merge(volumes_df, on='timestamp').merge(market_caps_df, on='timestamp')
        coin_data['timestamp'] = pd.to_datetime(coin_data['timestamp'], unit='ms')
        coin_data.set_index('timestamp', inplace=True)
        
        indicators = calculate_indicators(coin_data)
        if indicators is not None:
            results.append({
                'id': row['id'],
                'symbol': row['symbol'],
                'name': row['name'],
                'rank': row['rank'],
                'score': indicators['total_score'],  # 确保保存总分
                **indicators
            })
        else:
            print(f"Skipping {row['name']} due to insufficient data")
    
    # 将结果保存到 CSV 文件
    results_df = pd.DataFrame(results)
    results_df.to_csv('coin_scores.csv', index=False)
    print(f"Analysis completed for range {coin_range}. Results saved to coin_scores.csv")

def calculate_indicators(data, short_ma=7, long_ma=30):
    # 数据验证和清理
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < max(short_ma, long_ma, 14):  # 14 是用于计算 RSI 的默认周期
        return None  # 数据不足，返回 None

    # 计算每日回报率
    data['returns'] = data['price'].pct_change()
    
    # 计算波动率（使用过去14天的标准差）
    volatility = data['returns'].rolling(window=14).std().iloc[-1]
    
    # 计算 RSI
    delta = data['price'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    
    # 计算移动平均线
    data['short_ma'] = data['price'].rolling(window=short_ma).mean()
    data['long_ma'] = data['price'].rolling(window=long_ma).mean()
    ma_diff_percentage = (data['short_ma'].iloc[-1] - data['long_ma'].iloc[-1]) / data['long_ma'].iloc[-1]
    
    # 计算成交量变化率
    vol_change_rate = data['volume'].pct_change().iloc[-1]
    
    # 计算 K 线影线比例 (这里使用日线数据的最后一根 K 线)
    last_candle = data.iloc[-1]
    body = abs(last_candle['price'] - data['price'].iloc[-2])
    high_shadow = last_candle['price'] - min(last_candle['price'], data['price'].iloc[-2])
    low_shadow = max(last_candle['price'], data['price'].iloc[-2]) - last_candle['price']
    shadow_ratio = (high_shadow + low_shadow) / (body + high_shadow + low_shadow) if (body + high_shadow + low_shadow) != 0 else 0
    
    # 获取最新市值
    market_cap = data['market_cap'].iloc[-1]
    
    # 计算价格趋势
    price_trend = (data['price'].iloc[-1] / data['price'].iloc[-7] - 1) * 100
    
    # 计算交易量趋势
    volume_trend = (data['volume'].iloc[-1] / data['volume'].iloc[-7] - 1) * 100

    def safe_score(value, func):
        if np.isnan(value) or np.isinf(value):
            return 0
        return func(value)

    def score_volatility(v):
        return max(0, min(10, int(10 - v * 200)))  # 0-10分，线性插值

    def score_rsi(r):
        if r < 30: return 10 - int((r - 20) / 1)  # 20-30 之间，每1递减1分
        elif r > 70: return 10 - int((r - 70) / 1)  # 70-80 之间，每1递减1分
        else: return max(0, 5 - abs(50 - r) // 3)  # 30-70 之间，接近50分数越高

    def score_ma(m):
        return min(10, int(m * 200))  # 0-10分，线性插值

    def score_volume(v):
        return max(0, min(10, int(5 + v * 10)))  # -0.5到1.5之间，线性插值

    def score_shadow(s):
        return min(10, int(s * 20))  # 0-10分，线性插值

    def score_market_cap(m):
        return min(10, max(0, int(np.log10(m) - 5)))  # 对数刻度，1e6到1e16之间

    def score_price_trend(t):
        return max(0, min(10, int(5 + t)))  # -5%到5%之间，线性插值

    def score_volume_trend(t):
        return max(0, min(10, int(5 + t / 2)))  # -10%到10%之间，线性插值

    vol_score = safe_score(volatility, score_volatility)
    rsi_score = safe_score(rsi, score_rsi)
    ma_score = safe_score(ma_diff_percentage, score_ma)
    volume_score = safe_score(vol_change_rate, score_volume)
    shadow_score = safe_score(shadow_ratio, score_shadow)
    cap_score = safe_score(market_cap, score_market_cap)
    price_trend_score = safe_score(price_trend, score_price_trend)
    volume_trend_score = safe_score(volume_trend, score_volume_trend)

    total_score = vol_score + rsi_score + ma_score + volume_score + shadow_score + cap_score + price_trend_score + volume_trend_score

    return {
        'volatility': volatility,
        'rsi': rsi,
        'ma_diff_percentage': ma_diff_percentage,
        'vol_change_rate': vol_change_rate,
        'shadow_ratio': shadow_ratio,
        'market_cap': market_cap,
        'price_trend': price_trend,
        'volume_trend': volume_trend,
        'total_score': total_score,
        'vol_score': vol_score,
        'rsi_score': rsi_score,
        'ma_score': ma_score,
        'volume_score': volume_score,
        'shadow_score': shadow_score,
        'cap_score': cap_score,
        'price_trend_score': price_trend_score,
        'volume_trend_score': volume_trend_score
    }

def parse_batch(batch_str):
    start, end = map(int, batch_str.split('-'))
    return (start, end)

# 主函数
def main():
    parser = argparse.ArgumentParser(description='Fetch and analyze cryptocurrency data')
    parser.add_argument('ranges', nargs='*', help='Ranges of coins to process (e.g. 1-50 51-100)')
    parser.add_argument('--fetch', action='store_true', help='Fetch new data')
    parser.add_argument('--analyze', action='store_true', help='Analyze data')
    args = parser.parse_args()

    if args.fetch:
        fetch_and_save_data([parse_batch(batch) for batch in args.ranges])
    if args.analyze:
        analyze_data()

# 如果直接运行此脚本
if __name__ == '__main__':
    main()
