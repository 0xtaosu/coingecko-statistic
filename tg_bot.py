import os
import pandas as pd
import asyncio
import argparse
from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, Application
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, time
from backtest import Backtester, DataLoader

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

def get_trading_signals():
    """获取交易建议"""
    try:
        # 加载数据
        data_loader = DataLoader()
        coin_data = data_loader.load_data()
        
        # 初始化回测器
        backtester = Backtester(
            coin_data=coin_data,
            initial_capital=10000,
            stop_loss=0.1,
            take_profit=0.2
        )
        
        # 获取当前日期的信号
        current_date = pd.Timestamp.now(tz='UTC')
        signals = backtester.generate_signals(coin_data, [current_date], current_date)
        
        # 生成交易建议消息
        message = "🎯 *Trading Signals*\n\n"
        
        # 按信号强度排序
        sorted_signals = sorted(
            [(symbol, data) for symbol, data in signals.items()],
            key=lambda x: x[1]['total_score'],
            reverse=True
        )
        
        # 生成买入建议
        buy_suggestions = []
        for symbol, signal in sorted_signals[:5]:  # 取前5个最强信号
            if signal['total_score'] > 7:  # 与回测系统保持一致的阈值
                price = coin_data[symbol]['data'].iloc[-1]['price']
                stop_loss = price * (1 - backtester.stop_loss)
                take_profit = price * (1 + backtester.take_profit)
                
                buy_suggestions.append(
                    f"📈 *{symbol}*\n"
                    f"Score: {signal['total_score']:.1f}\n"
                    f"Entry: ${price:.4f}\n"
                    f"Stop Loss: ${stop_loss:.4f}\n"
                    f"Take Profit: ${take_profit:.4f}\n"
                )
        
        if buy_suggestions:
            message += "*🟢 Buy Suggestions:*\n"
            message += "\n".join(buy_suggestions)
        else:
            message += "🔍 No strong buy signals at the moment.\n"
        
        message += "\n⚠️ *Risk Management*:\n"
        message += "• Max position size: 10% of portfolio\n"
        message += "• Min trade amount: $100\n"
        message += "• Max positions: 5\n\n"
        message += "📊 DYOR. Not financial advice."
        
        return message
        
    except Exception as e:
        return f"Error generating trading signals: {str(e)}"

def get_latest_trading_signals():
    """从最新的日志文件中获取交易信号"""
    try:
        # 获取当前日期的日志文件名
        current_date = datetime.now().strftime('%Y%m%d')
        trade_log_file = f"trade_log_{current_date}.csv"
        
        if not os.path.exists(trade_log_file):
            return "No trading signals available for today."
            
        # 读取交易日志
        df = pd.read_csv(trade_log_file)
        
        # 只获取最新的买入信号
        latest_signals = df[df['Action'] == 'BUY'].tail(5)
        
        if len(latest_signals) == 0:
            return "No buy signals available for today."
            
        # 生成消息
        message = "🎯 *Latest Trading Signals*\n\n"
        
        for _, signal in latest_signals.iterrows():
            message += (
                f"📈 *{signal['Symbol']}*\n"
                f"Entry: ${float(signal['Price']):.4f}\n"
                f"Stop Loss: ${float(signal['Stop Loss']):.4f}\n"
                f"Take Profit: ${float(signal['Take Profit']):.4f}\n"
                f"Score: {float(signal['Signal Score']):.1f}\n\n"
            )
            
        message += (
            "⚠️ *Risk Management*:\n"
            "• Max position size: 10%\n"
            "• Min trade amount: $100\n"
            "• Max positions: 5\n"
            "• Stop Loss: -10%\n"
            "• Take Profit: +20%\n\n"
            "📊 DYOR. Not financial advice."
        )
        
        return message
        
    except Exception as e:
        logger.error(f"Error reading trading signals: {e}")
        return "Error getting trading signals."

async def send_daily_update(context: Application):
    # 发送市场分析
    market_analysis = get_top_50_coins()
    try:
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=market_analysis,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # 发送交易信号
        trading_signals = get_latest_trading_signals()
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=trading_signals,
            parse_mode=ParseMode.MARKDOWN
        )
        
        print(f"✅ Daily update and trading signals sent at {datetime.now()}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

async def start(update, context):
    welcome_message = (
        "👋 *Welcome to Coin Analysis Bot*\n\n"
        "🔄 Daily updates will be sent at 9:30 AM.\n"
        "📊 Analysis includes:\n"
        "- Top 50 coins by score\n"
        "- Detailed technical indicators\n"
        "- Market cap ranking\n\n"
        "📈 Use /update for immediate analysis."
    )
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )

async def get_update(update, context):
    """手动触发更新的命令处理函数"""
    await update.message.reply_text("🔄 Generating analysis...")
    
    # 发送市场分析
    market_analysis = get_top_50_coins()
    await update.message.reply_text(
        market_analysis,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # 发送交易建议
    trading_signals = get_trading_signals()
    await update.message.reply_text(
        trading_signals,
        parse_mode=ParseMode.MARKDOWN
    )

async def manual_send():
    """手动发送消息的函数"""
    bot = Bot(token=TOKEN)
    try:
        # 发送市场分析
        market_analysis = get_top_50_coins()
        await bot.send_message(
            chat_id=CHAT_ID,
            text=market_analysis,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # 发送交易建议
        trading_signals = get_trading_signals()
        await bot.send_message(
            chat_id=CHAT_ID,
            text=trading_signals,
            parse_mode=ParseMode.MARKDOWN
        )
        
        print(f"✅ Manual update and trading signals sent at {datetime.now()}")
    except Exception as e:
        print(f"❌ Error sending message: {str(e)}")

async def run_bot(scheduler_enabled=True):
    """运行机器人，可选择是否启用调度器"""
    proxy = None
    
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
    await application.stop()

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