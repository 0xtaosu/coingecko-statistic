import schedule
import time
import subprocess
import logging
import pytz
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建北京时区对象
beijing_tz = pytz.timezone('Asia/Shanghai')

def run_script():
    beijing_time = datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"Starting daily update... (Beijing time: {beijing_time})")
    try:
        # 执行获取新数据的命令
        subprocess.run(["python", "data_processor.py", "1-50 51-100 101-150 151-200 201-250 251-300", "--fetch"], check=True)
        logger.info("Data fetching completed.")

        # 执行分析数据的命令
        subprocess.run(["python", "data_processor.py", "1-300", "--analyze"], check=True)
        logger.info("Data analysis completed.")

        logger.info("Daily update finished successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred during the daily update: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

def main():
    # 计算北京时间9:00对应的UTC时间
    beijing_time = datetime.now(beijing_tz).replace(hour=9, minute=0, second=0, microsecond=0)
    utc_time = beijing_time.astimezone(pytz.UTC)
    
    # 设置每天在计算出的UTC时间运行
    schedule.every().day.at(utc_time.strftime("%H:%M")).do(run_script)

    logger.info(f"Automatic update scheduler started. Will run daily at 09:00 Beijing time (UTC: {utc_time.strftime('%H:%M')}).")

    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次是否有待运行的任务

if __name__ == "__main__":
    main()