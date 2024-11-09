import os
from dotenv import load_dotenv
import requests
import pandas as pd
import numpy as np
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import json
import time
from functools import wraps
import random
import csv
import argparse
from datetime import datetime

# 初始化配置
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.coingecko.com/api/v3"
API_KEY = os.getenv("COINGECKO_API_KEY")

if not API_KEY:
    logger.error("API key not found. Please make sure COINGECKO_API_KEY is set in your .env file.")
    exit(1)

class CoinGeckoAPI:
    """处理所有 CoinGecko API 相关的请求"""
    
    @staticmethod
    def get_session():
        """创建一个带有重试机制的会话"""
        session = requests.Session()
        retry = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    @classmethod
    def get_top_coins(cls, start, end):
        """获取排名靠前的币种"""
        url = f"{API_BASE_URL}/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": end-start+1,
            "page": start//50 + 1,
            "sparkline": False,
            "x_cg_demo_api_key": API_KEY
        }
        
        try:
            session = cls.get_session()
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from CoinGecko: {e}")
            return None

    @classmethod
    def get_historical_data(cls, coin_id, days=360, max_retries=5, base_delay=5):
        """获取币种的历史数据"""
        url = f"{API_BASE_URL}/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": "usd",
            "days": days,
            "interval": "daily",
            "x_cg_demo_api_key": API_KEY
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params)
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                    logger.warning(f"Rate limit hit for {coin_id}. Waiting {retry_after} seconds...")
                    time.sleep(retry_after + random.uniform(1, 3))
                    continue
                    
                response.raise_for_status()
                return json.dumps(response.json())
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching historical data for {coin_id}: {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(1, 5)
                    logger.info(f"Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    return None

class DataProcessor:
    """数据处理和分析类"""
    
    @staticmethod
    def process_data(data):
        """
        处理原始数据，将 UTC 时间转换为北京时间
        
        参数:
            data (dict): 包含 prices, volumes, market_caps 的原始数据
            
        返回:
            DataFrame: 处理后的数据框，包含北京时间的每日数据
        """
        # 创建数据框
        df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
        
        # 将 UTC 时间转换为北京时间（UTC+8）
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
        df.set_index("date", inplace=True)
        df.drop("timestamp", axis=1, inplace=True)
        
        # 由于原始数据是 UTC 0点，转换后就是北京时间 8点的数据，无需额外处理
        return df

    @staticmethod
    def calculate_indicators(data):
        """
        计算技术指标，识别底部横盘后突破的代币
        """
        # 数据验证和清理
        data = data.replace([np.inf, -np.inf], np.nan).dropna()
        total_days = len(data)
        
        if total_days < 30:
            return None
            
        def get_window_size(preferred_size):
            return min(preferred_size, total_days // 2)
        
        scores = {}
        
        # 首先计算收益率
        data['returns'] = data['price'].pct_change()
        
        # 1. 计算横盘特征（使用前期数据）
        consolidation_window = get_window_size(90)  # 考察90天的横盘
        recent_window = get_window_size(14)  # 最近14天的突破特征
        
        if total_days > consolidation_window:
            consolidation_data = data.iloc[-consolidation_window:-recent_window]
            recent_data = data.iloc[-recent_window:]
            
            # 计算横盘期间的波动特征
            consolidation_volatility = consolidation_data['returns'].std()
            consolidation_range = (consolidation_data['price'].max() - consolidation_data['price'].min()) / consolidation_data['price'].mean()
            
            # 计算横盘期间的成交量特征
            avg_volume = consolidation_data['volume'].mean()
            try:
                if avg_volume == 0 or np.isnan(avg_volume):
                    volume_stability_score = 0
                else:
                    volume_stability = consolidation_data['volume'].std() / avg_volume
                    # 处理无穷大和NaN的情况
                    if np.isinf(volume_stability) or np.isnan(volume_stability):
                        volume_stability_score = 0
                    else:
                        volume_stability_score = max(0, min(10, int(10 - volume_stability * 10)))
            except:
                volume_stability_score = 0
            
            # 计算最近的突破特征
            breakout_price_change = (recent_data['price'].iloc[-1] / consolidation_data['price'].mean() - 1) * 100
            try:
                if avg_volume == 0 or np.isnan(avg_volume):
                    breakout_volume_score = 0
                else:
                    breakout_volume_change = (recent_data['volume'].mean() / avg_volume - 1) * 100
                    # 处理无穷大和NaN的情况
                    if np.isinf(breakout_volume_change) or np.isnan(breakout_volume_change):
                        breakout_volume_score = 0
                    else:
                        breakout_volume_score = max(0, min(10, int(breakout_volume_change)))
            except:
                breakout_volume_score = 0
            
            scores['consolidation_score'] = max(0, min(10, int(10 - consolidation_range * 100)))
            scores['volume_stability_score'] = volume_stability_score
            scores['breakout_score'] = max(0, min(10, int(breakout_price_change)))
            scores['breakout_volume_score'] = breakout_volume_score
        else:
            return None
        
        # 2. RSI 特征（关注RSI从低位回升）
        delta = data['price'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # 检查RSI是否从低位回升
        recent_rsi = rsi.iloc[-recent_window:]
        rsi_low = recent_rsi.min()
        rsi_current = recent_rsi.iloc[-1]
        rsi_trend = rsi_current - rsi_low
        
        scores['rsi_score'] = max(0, min(10, int(rsi_trend * 0.5)))
        
        # 3. 移动平均线（判断突破）
        ma20 = data['price'].rolling(window=20).mean()
        ma60 = data['price'].rolling(window=60).mean()
        
        # 检查是否突破MA
        price_current = data['price'].iloc[-1]
        ma_cross = (price_current > ma20.iloc[-1]) and (price_current > ma60.iloc[-1])
        ma_trend = (ma20.iloc[-1] / ma60.iloc[-1] - 1) * 100
        
        scores['ma_score'] = max(0, min(10, int(5 + ma_trend))) if ma_cross else 0
        
        # 4. 市值（倾向于中小市值）
        market_cap = data['market_cap'].iloc[-1]
        
        # 处理市值评分
        try:
            if market_cap <= 0 or np.isnan(market_cap):
                scores['cap_score'] = 0
            else:
                scores['cap_score'] = min(10, max(0, int(15 - np.log10(market_cap))))
        except (OverflowError, ValueError):
            scores['cap_score'] = 0
        
        # 记录原始指标值
        scores.update({
            'consolidation_volatility': consolidation_volatility,
            'consolidation_range': consolidation_range,
            'volume_stability': volume_stability_score,
            'breakout_price_change': breakout_price_change,
            'breakout_volume_change': breakout_volume_score,
            'rsi_current': rsi_current,
            'rsi_trend': rsi_trend,
            'ma_trend': ma_trend,
            'market_cap': market_cap,
            'data_days': total_days
        })
        
        # 计算总分
        weights = {
            'consolidation_score': 1.5,
            'volume_stability_score': 1.0,
            'breakout_score': 1.5,
            'breakout_volume_score': 1.0,
            'rsi_score': 1.0,
            'ma_score': 1.0,
            'cap_score': 1.0
        }
        
        total = 0
        total_weight = sum(weights.values())
        
        for key, weight in weights.items():
            total += scores[key] * weight
            
        scores['total_score'] = total / total_weight
        
        return scores

def fetch_and_save_data(batches):
    """获取并保存数据"""
    all_coin_data = []
    for start, end in batches:
        logger.info(f"Fetching data for coins {start} to {end}")
        top_coins = CoinGeckoAPI.get_top_coins(start, end)
        
        if top_coins is None:
            logger.error(f"Failed to fetch coins {start} to {end}. Skipping this batch.")
            continue
        
        for coin in top_coins:
            historical_data = CoinGeckoAPI.get_historical_data(coin['id'])
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
            
            time.sleep(random.uniform(2, 4))
        
        time.sleep(random.uniform(5, 10))
    
    df = pd.DataFrame(all_coin_data)
    df.to_csv('data.csv', index=False)
    logger.info("All data fetched and saved to data.csv")

def analyze_data(coin_range='1-300'):
    """分析数据"""
    start, end = map(int, coin_range.split('-'))
    
    df = pd.read_csv('data.csv')
    df['rank'] = list(range(1, len(df) + 1))
    df = df[(df['rank'] >= start) & (df['rank'] <= end)]
    
    results = []
    for _, row in df.iterrows():
        logger.info(f"Processing {row['name']}")
        
        historical_data = json.loads(row['historical_data'])
        
        # 使用 process_data 处理价格数据
        prices_df = DataProcessor.process_data({"prices": historical_data['prices']})
        volumes_df = DataProcessor.process_data({"prices": historical_data['total_volumes']}).rename(columns={'price': 'volume'})
        market_caps_df = DataProcessor.process_data({"prices": historical_data['market_caps']}).rename(columns={'price': 'market_cap'})
        
        # 合并所有数据
        coin_data = prices_df.join(volumes_df['volume']).join(market_caps_df['market_cap'])
        
        indicators = DataProcessor.calculate_indicators(coin_data)
        if indicators is not None:
            results.append({
                'id': row['id'],
                'symbol': row['symbol'],
                'name': row['name'],
                'rank': row['rank'],
                **indicators
            })
        else:
            logger.warning(f"Skipping {row['name']} due to insufficient data")
    
    results_df = pd.DataFrame(results)
    results_df.to_csv('coin_scores.csv', index=False)
    logger.info(f"Analysis completed for range {coin_range}. Results saved to coin_scores.csv")

def parse_batch(batch_str):
    """解析批次字符串"""
    start, end = map(int, batch_str.split('-'))
    return (start, end)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Fetch and analyze cryptocurrency data')
    parser.add_argument('ranges', nargs='*', help='Ranges of coins to process (e.g. 1-50 51-100)')
    parser.add_argument('--fetch', action='store_true', help='Fetch new data')
    parser.add_argument('--analyze', action='store_true', help='Analyze data')
    args = parser.parse_args()

    if args.fetch:
        fetch_and_save_data([parse_batch(batch) for batch in args.ranges])
    if args.analyze:
        analyze_data()

if __name__ == '__main__':
    main()