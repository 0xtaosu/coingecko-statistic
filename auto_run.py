import schedule
import time
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def run_script():
    logger.info("Starting daily update...")
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
    # 设置每天早上9点运行
    schedule.every().day.at("09:00").do(run_script)

    logger.info("Automatic update scheduler started. Will run daily at 09:00.")

    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次是否有待运行的任务

if __name__ == "__main__":
    main()