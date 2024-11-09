import asyncio
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import schedule
import time
from data_processor import fetch_and_save_data, analyze_data
from tg_bot import run_bot
import os
import logging
from datetime import datetime
import sys

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

def auto_run():
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduled task: {e}")
            time.sleep(60)  # 出错后等待60秒再继续

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

        # 设置自动运行任务
        schedule.every().day.at("09:00").do(data_processing_job)
        auto_run_thread = threading.Thread(target=auto_run, daemon=True)
        auto_run_thread.start()
        logger.info("Auto-run thread started")

        # 启动 Telegram Bot
        logger.info("Starting Telegram Bot...")
        bot_task = asyncio.create_task(run_bot())

        # 立即运行一次数据处理任务
        logger.info("Running initial data processing job...")
        await asyncio.get_event_loop().run_in_executor(None, data_processing_job)

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
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise
