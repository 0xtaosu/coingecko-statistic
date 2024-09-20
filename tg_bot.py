import os
import pandas as pd
import asyncio
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, time

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

async def send_daily_update(bot):
    message = get_top_50_coins()
    await bot.send_message(chat_id=CHAT_ID, text=message)
    print(f"Daily update sent at {datetime.now()}")

async def start(update, context):
    await update.message.reply_text("Bot is running. You will receive daily updates at 9:30 AM.")

async def main():
    # 禁用代理
    proxy = None
    
    application = ApplicationBuilder().token(TOKEN).proxy_url(proxy).build()

    application.add_handler(CommandHandler("start", start))

    # 创建调度器
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_update, 'cron', hour=9, minute=30, args=[application.bot])
    scheduler.start()

    # 启动bot
    await application.start()
    await application.updater.start_polling()
    print("Bot is now running!")

    # 保持bot运行
    try:
        await application.updater.stop()
        await application.stop()
    except asyncio.CancelledError:
        pass

if __name__ == '__main__':
    asyncio.run(main())