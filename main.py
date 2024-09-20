import asyncio
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import schedule
import time
from data_processor import fetch_and_save_data, analyze_data
from tg_bot import run_bot
import os

# 设置工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def run_http_server():
    port = int(os.environ.get('PORT', 8000))
    httpd = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"HTTP server is running on http://0.0.0.0:{port}")
    httpd.serve_forever()

def auto_run():
    while True:
        schedule.run_pending()
        time.sleep(1)

def data_processing_job():
    print("Starting data processing job...")
    batches = ['1-50', '51-100', '101-150', '151-200', '201-250', '251-300']
    for batch in batches:
        print(f"Processing batch {batch}")
        fetch_and_save_data([batch])
        time.sleep(60)  # 在每个批次之间等待60秒，以避免可能的API限制
    analyze_data('1-300')  # 分析整个范围的数据
    print("Data processing job completed.")

async def main():
    # 启动 HTTP 服务器
    http_thread = threading.Thread(target=run_http_server)
    http_thread.start()

    # 设置自动运行任务
    schedule.every().day.at("09:00").do(data_processing_job)
    auto_run_thread = threading.Thread(target=auto_run)
    auto_run_thread.start()

    # 启动 Telegram Bot
    bot_task = asyncio.create_task(run_bot())

    # 等待直到程序被中断
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(main())
