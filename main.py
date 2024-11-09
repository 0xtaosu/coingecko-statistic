import asyncio
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import schedule
import time
import sys
from data_processor import fetch_and_save_data, analyze_data
from tg_bot import run_bot
import os
import logging
from datetime import datetime, timezone
import pytz

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

# 设置工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s" % (
            self.address_string(),
            self.log_date_time_string(),
            format%args
        ))
        
    def do_GET(self):
        try:
            super().do_GET()
        except Exception as e:
            logger.error(f"Error handling GET request: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")

def run_http_server():
    try:
        port = int(os.environ.get('PORT', 8000))
        server_address = ('0.0.0.0', port)
        httpd = HTTPServer(server_address, CustomHTTPRequestHandler)
        logger.info(f"HTTP server is running on http://0.0.0.0:{port}")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"Error in HTTP server: {e}")
        raise

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    utc_now = datetime.now(timezone.utc)
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now

def auto_run():
    """使用北京时间运行调度任务"""
    while True:
        try:
            # 获取北京时间
            beijing_now = get_beijing_time()
            
            # 运行待处理的任务
            schedule.run_pending()
            
            # 记录下一次运行时间
            next_run = schedule.next_run()
            if next_run:
                logger.debug(f"Next run scheduled at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduled task: {e}")
            time.sleep(60)

def data_processing_job():
    try:
        logger.info("Starting data processing job...")
        batches = ['1-50', '51-100', '101-150', '151-200', '201-250', '251-300']
        
        for batch in batches:
            try:
                logger.info(f"Processing batch {batch}")
                fetch_and_save_data([batch])
                time.sleep(60)  # 批次间隔
            except Exception as e:
                logger.error(f"Error processing batch {batch}: {e}")
                time.sleep(120)  # 出错后等待更长时间
                continue
                
        logger.info("Starting data analysis...")
        analyze_data('1-300')
        logger.info("Data processing job completed successfully")
        
    except Exception as e:
        logger.error(f"Error in data processing job: {e}")
        
async def main():
    try:
        # 启动 HTTP 服务器
        http_thread = threading.Thread(target=run_http_server, daemon=True)
        http_thread.start()
        logger.info("HTTP server thread started")

        # 设置自动运行任务 - 北京时间早上9点 (UTC+8 = 01:00)
        schedule.every().day.at("01:00").do(data_processing_job)  # UTC时间1点 = 北京时间9点
        
        auto_run_thread = threading.Thread(target=auto_run, daemon=True)
        auto_run_thread.start()
        
        # 记录当前北京时间和下次运行时间
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
        # 确保使用 UTC+8 时区
        os.environ['TZ'] = 'Asia/Shanghai'
        if hasattr(time, 'tzset'):
            time.tzset()
            
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise
