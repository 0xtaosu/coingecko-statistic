import os
import pandas as pd
import schedule
import time
from telegram.ext import Updater, CommandHandler
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取Telegram Bot Token
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def get_top_50_coins():
    # 读取CSV文件
    df = pd.read_csv('coin_scores.csv')
    
    # 按score升序排序
    df_sorted = df.sort_values('score')
    
    # 选取前50个结果
    top_50 = df_sorted.head(50)
    
    # 格式化消息
    message = "Top 50 Coins by Score (Ascending):\n\n"
    for index, row in top_50.iterrows():
        message += f"{row['symbol']} ({row['name']}): {row['score']:.2f}\n"
    
    return message

def send_daily_update(context):
    message = get_top_50_coins()
    context.bot.send_message(chat_id=CHAT_ID, text=message)

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Bot is running. You will receive daily updates at 9:30 AM.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    # 设置每天9:30发送更新
    schedule.every().day.at("09:30").do(send_daily_update, updater.job_queue)

    # 启动bot
    updater.start_polling()

    # 运行调度器
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()