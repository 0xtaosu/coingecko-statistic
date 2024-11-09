import asyncio
import threading
from flask import Flask, render_template, jsonify, send_file
import schedule
import time
import sys
from data_processor import fetch_and_save_data, analyze_data
from tg_bot import run_bot
import os
import logging
from datetime import datetime, timezone
import pytz
import pandas as pd

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'app_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

@app.route('/')
def index():
    """主页面"""
    try:
        # 读取分析结果
        df = pd.read_csv('coin_scores.csv')
        
        # 转换数据类型
        numeric_columns = [
            'total_score', 'consolidation_score', 'volume_stability_score',
            'breakout_score', 'rsi_score', 'ma_score'
        ]
        
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 按总分排序
        df = df.sort_values('total_score', ascending=False)
        
        # 获取文件最后修改时间
        update_time = datetime.fromtimestamp(
            os.path.getmtime('coin_scores.csv')
        ).strftime('%Y-%m-%d %H:%M:%S')
        
        # 转换为字典列表
        coins = []
        for _, row in df.iterrows():
            coin = {
                'rank': str(row['rank']),
                'symbol': str(row['symbol']).upper(),
                'name': str(row['name']),
                'total_score': float(row['total_score']),
                'consolidation_score': float(row['consolidation_score']),
                'volume_stability_score': float(row['volume_stability_score']),
                'breakout_score': float(row['breakout_score']),
                'rsi_score': float(row['rsi_score']),
                'ma_score': float(row['ma_score'])
            }
            coins.append(coin)
            
        logger.info(f"Successfully loaded {len(coins)} coins")
        
        return render_template('index.html', 
                             coins=coins,
                             update_time=update_time)
        
    except Exception as e:
        logger.error(f"Error loading index page: {e}")
        logger.exception("Detailed error:")
        return "Error loading data", 500

@app.route('/api/coins')
def get_coins():
    """获取币种数据的API端点"""
    try:
        df = pd.read_csv('coin_scores.csv')
        return jsonify(df.to_dict('records'))
    except Exception as e:
        logger.error(f"Error fetching coin data: {e}")
        return jsonify({"error": str(e)}), 500


def get_beijing_time():
    """获取北京时间"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    utc_now = datetime.now(timezone.utc)
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now

def data_processing_job():
    """数据处理任务"""
    try:
        logger.info("Starting data processing job...")
        batches = ['1-50', '51-100', '101-150', '151-200', '201-250', '251-300']
        
        for batch in batches:
            try:
                logger.info(f"Processing batch {batch}")
                fetch_and_save_data([batch])
                time.sleep(60)
            except Exception as e:
                logger.error(f"Error processing batch {batch}: {e}")
                time.sleep(120)
                continue
                
        logger.info("Starting data analysis...")
        analyze_data('1-300')
        logger.info("Data processing job completed successfully")
        
    except Exception as e:
        logger.error(f"Error in data processing job: {e}")

def run_flask():
    """运行Flask服务器"""
    try:
        port = int(os.environ.get('PORT', 8000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Error in Flask server: {e}")
        raise

def auto_run():
    """调度任务运行器"""
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduled task: {e}")
            time.sleep(60)

async def main():
    try:
        # 启动 Flask 服务器
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask server thread started")

        # 设置自动运行任务 - 北京时间早上9点
        schedule.every().day.at("01:00").do(data_processing_job)
        
        auto_run_thread = threading.Thread(target=auto_run, daemon=True)
        auto_run_thread.start()
        
        # 记录时间信息
        current_beijing_time = get_beijing_time()
        logger.info(f"Application started at Beijing time: {current_beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("Task scheduled for 09:00 Beijing time (01:00 UTC)")

        # 启动 Telegram Bot
        logger.info("Starting Telegram Bot...")
        bot_task = asyncio.create_task(run_bot())

        # 等待直到程序被中断
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("Received cancellation signal")
            raise
            
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        raise
    finally:
        logger.info("Shutting down application...")

if __name__ == "__main__":
    try:
        os.environ['TZ'] = 'Asia/Shanghai'
        if hasattr(time, 'tzset'):
            time.tzset()
            
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise