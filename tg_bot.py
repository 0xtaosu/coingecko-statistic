import os
import pandas as pd
import asyncio
import argparse
from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, Application
from telegram.error import InvalidToken
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, time

# 加载环境变量
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def get_top_50_coins():
    try:
        df = pd.read_csv('coin_scores.csv')
        df_sorted = df.sort_values(
            ['total_score', 'rank'], 
            ascending=[False, True]  # 总分降序，市值排名升序
        )
        top_50 = df_sorted.head(50)
        
        # 获取比特币的得分作为基准
        btc_score = float(df_sorted[df_sorted['symbol'].str.lower() == 'btc']['total_score'].iloc[0])
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🎯 *Top 50 Coins* ({current_time})\n\n"
        
        # 直接按总分排序展示
        for index, row in top_50.iterrows():
            score = float(row['total_score'])
            rank_marker = "🔥" if int(row['rank']) <= 100 else "⭐"
            
            # 只比较是否强于比特币
            score_marker = "🟢" if score > btc_score else "⚪"
                
            message += (
                f"{rank_marker} *{row['symbol'].upper()}* "
                f"{score_marker} {score:.1f}\n"
            )
        
        # 添加简短说明
        message += (
            f"\n📝 *Legend*:\n"
            f"🔥 Top 100 MC | ⭐ Others\n"
            f"🟢 > BTC ({btc_score:.1f}) | ⚪ ≤ BTC\n"
            f"⚠️ DYOR. Not financial advice."
        )
        
        return message
        
    except Exception as e:
        return f"Error generating report: {str(e)}"


async def send_daily_update(context: Application):
    # 发送Top 50榜单
    market_analysis = get_top_50_coins()
    try:
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=market_analysis,
            parse_mode=ParseMode.MARKDOWN
        )
        print(f"✅ Daily Top 50 update sent at {datetime.now()}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

async def start(update, context):
    welcome_message = (
        "👋 *Welcome to Coin Analysis Bot*\n\n"
        "🔄 Daily update sent at 9:30 AM.\n"
        "📊 Includes Top 50 by score.\n\n"
        "📈 Use /update for immediate list."
    )
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )

async def get_update(update, context):
    """手动触发更新的命令处理函数"""
    await update.message.reply_text("🔄 Generating Top 50 list...")
    # 发送Top 50榜单
    market_analysis = get_top_50_coins()
    await update.message.reply_text(
        market_analysis,
        parse_mode=ParseMode.MARKDOWN
    )

async def manual_send():
    """手动发送消息的函数"""
    bot = Bot(token=TOKEN)
    try:
        # 仅发送Top 50榜单
        market_analysis = get_top_50_coins()
        await bot.send_message(
            chat_id=CHAT_ID,
            text=market_analysis,
            parse_mode=ParseMode.MARKDOWN
        )
        print(f"✅ Manual Top 50 update sent at {datetime.now()}")
    except Exception as e:
        print(f"❌ Error sending message: {str(e)}")

async def run_bot(scheduler_enabled=True):
    """运行机器人，可选择是否启用调度器"""
    if not TOKEN or not CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing. Bot disabled.")
        return

    proxy = None
    application = None

    try:
        application = (
            ApplicationBuilder()
            .token(TOKEN)
            .proxy_url(proxy)
            .build()
        )

        # 添加命令处理器
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("update", get_update))

        # 根据参数决定是否启用调度器
        if scheduler_enabled:
            scheduler = AsyncIOScheduler()
            scheduler.add_job(
                send_daily_update,
                'cron',
                hour=9,
                minute=30,
                args=[application]
            )
            scheduler.start()
            print("📅 Scheduler enabled - Daily updates at 09:30")
        else:
            print("ℹ️ Running in manual mode - Scheduler disabled")

        await application.initialize()
        await application.start()
        print("🤖 Bot is now running!")

        stop_signal = asyncio.Future()
        await stop_signal

    except InvalidToken:
        print("❌ Invalid TELEGRAM_BOT_TOKEN. Bot not started. Check your .env.")
    except Exception as e:
        print(f"❌ Telegram bot failed to start: {e}")
    finally:
        if application is not None:
            try:
                await application.stop()
            except Exception:
                pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram Bot for Coin Analysis')
    parser.add_argument('--manual', action='store_true', 
                       help='Send a single update and exit')
    parser.add_argument('--no-scheduler', action='store_true',
                       help='Run bot without scheduler')
    args = parser.parse_args()

    if args.manual:
        # 手动发送一次消息
        asyncio.run(manual_send())
        print("✨ Manual update completed")
    else:
        # 运行机器人，根据参数决定是否启用调度器
        asyncio.run(run_bot(not args.no_scheduler))
