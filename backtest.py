import logging
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
import numpy as np
from data_processor import DataProcessor
from datetime import datetime
import csv

class DataLoader:
    def __init__(self):
        self.data_file = "data.csv"
        
    def load_data(self):
        """从data.csv加载数据"""
        try:
            # 读取data.csv
            df = pd.read_csv(self.data_file)
            logging.info(f"Loaded {len(df)} coins from data.csv")
            
            coin_data = {}
            for _, row in df.iterrows():
                try:
                    # 解析历史数据
                    historical_data = json.loads(row['historical_data'])
                    
                    # 处理价格、交易量和市值数据
                    prices_df = DataProcessor.process_data({"prices": historical_data['prices']})
                    volumes_df = DataProcessor.process_data({"prices": historical_data['total_volumes']}).rename(columns={'price': 'volume'})
                    market_caps_df = DataProcessor.process_data({"prices": historical_data['market_caps']}).rename(columns={'price': 'market_cap'})
                    
                    # 合并所有数据
                    combined_df = prices_df.join(volumes_df['volume']).join(market_caps_df['market_cap'])
                    
                    symbol = row['symbol'].upper()
                    coin_data[symbol] = {
                        'data': combined_df,
                        'info': {
                            'id': row['id'],
                            'symbol': symbol,
                            'name': row['name']
                        }
                    }
                    
                    logging.info(f"Processed {symbol}")
                    
                except Exception as e:
                    logging.warning(f"Error processing {row['symbol']}: {e}")
                    continue
                    
            return coin_data
            
        except Exception as e:
            logging.error(f"Error loading data: {e}")
            raise

class Backtester:
    def __init__(self, coin_data, initial_capital=10000, stop_loss=0.1, take_profit=0.2):
        self.coin_data = coin_data
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.portfolio_history = []
        self.trades_history = []
        
        # 风险管理参数
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_position_size = 0.1  # 单个仓位最大占比
        self.min_trade_amount = 100   # 最小交易金额
        self.max_positions = 5        # 最大持仓数量
        
        # 记录初始状态
        self.portfolio_history.append({
            'date': pd.Timestamp.now(tz='UTC'),
            'value': initial_capital,
            'cash': initial_capital,
            'positions': {}
        })
        
        logging.info(f"Backtester initialized with {initial_capital:.2f} capital")
        
        # 使用当前日期生成日志文件名
        current_date = datetime.now().strftime('%Y%m%d')
        self.log_file = f"backtest_log_{current_date}.csv"
        self.trade_log_file = f"trade_log_{current_date}.csv"
        
        # 只在文件不存在时初始化日志文件
        self.initialize_log_files()
        
        self.performance_metrics = {}

    def initialize_log_files(self):
        """初始化日志文件，只在文件不存在时创建"""
        # 初始化回测日志
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Total Value', 'Cash', 'Positions', 'Daily Return'])
            
        # 初始化交易日志
        if not os.path.exists(self.trade_log_file):
            with open(self.trade_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Symbol', 'Action', 'Price', 'Quantity', 
                               'Value', 'Stop Loss', 'Take Profit', 'Signal Score'])

    def log_portfolio(self, date, total_value):
        """记录每日投资组合状态"""
        positions_str = '; '.join([
            f"{symbol}: {pos['quantity']:.2f}@{pos['current_price']:.2f}" 
            for symbol, pos in self.positions.items()
        ])
        
        # 计算日收益率
        if len(self.portfolio_history) > 1:
            prev_value = self.portfolio_history[-2]['value']
            daily_return = (total_value - prev_value) / prev_value * 100
        else:
            daily_return = 0
            
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                date,
                f"{total_value:.2f}",
                f"{self.current_capital:.2f}",
                positions_str,
                f"{daily_return:.2f}%"
            ])

    def log_trade(self, date, symbol, action, price, quantity, value, signal_score=None):
        """记录交易详情"""
        with open(self.trade_log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                date,
                symbol,
                action,
                f"{price:.4f}",
                f"{quantity:.4f}",
                f"{value:.2f}",
                f"{price * (1 - self.stop_loss):.4f}",
                f"{price * (1 + self.take_profit):.4f}",
                signal_score if signal_score else "N/A"
            ])

    def run_backtest(self):
        """运行回测"""
        # 获取所有日期
        dates = []
        for symbol in self.coin_data:
            df = self.coin_data[symbol]['data']
            dates.extend(df.index.tolist())
        
        # 去重并排序
        dates = sorted(list(set(dates)))
        
        # 回测每一天
        for current_date in dates:
            logging.info(f"Processing date: {current_date}")
            
            try:
                # 生成交易信号
                signals = self.generate_signals(self.coin_data, dates, current_date)
                
                # 更新持仓
                self.update_positions(current_date)
                
                # 执行交易
                self.execute_trades(signals, current_date)
                
                # 更新投资组合价值
                self.update_portfolio_value(current_date)
                
            except Exception as e:
                logging.error(f"Error processing date {current_date}: {e}")
                continue

        # 在回测结束后计算性能指标
        self.calculate_performance_metrics()
        
        # 输出关键指标
        logging.info(f"""
        回测性能指标:
        总交易次数: {self.performance_metrics['total_trades']}
        胜率: {self.performance_metrics['win_rate']:.2%}
        平均盈利: {self.performance_metrics['average_win']:.2%}
        平均亏损: {self.performance_metrics['average_loss']:.2%}
        盈亏比: {self.performance_metrics['profit_factor']:.2f}
        平均持仓天数: {self.performance_metrics['average_holding_days']:.1f}
        最大回撤: {self.performance_metrics['max_drawdown']:.2%}
        夏普比率: {self.performance_metrics['sharpe_ratio']:.2f}
        总收益率: {self.performance_metrics['total_return']:.2%}
        """)

    def generate_signals(self, coin_data, dates, current_date, lookback_days=30):
        """生成交易信号"""
        signals = {}
        
        for symbol, data in coin_data.items():
            try:
                df = data['data']
                historical_data = df[df.index <= current_date].tail(lookback_days)
                
                if len(historical_data) < lookback_days:
                    continue
                    
                indicators = DataProcessor.calculate_indicators(historical_data)
                if indicators is not None:
                    signals[symbol] = indicators
                    
            except Exception as e:
                logging.warning(f"Error generating signal for {symbol}: {e}")
                continue
                
        return signals

    def update_positions(self, current_date):
        """更新持仓状态"""
        for symbol in list(self.positions.keys()):
            try:
                position = self.positions[symbol]
                current_price = self.coin_data[symbol]['data'].loc[current_date, 'price']
                
                # 更新持仓价值
                position['current_price'] = current_price
                position_value = position['quantity'] * current_price
                
                # 检查止损和止盈
                entry_price = position['entry_price']
                price_change = (current_price - entry_price) / entry_price
                
                if price_change <= -self.stop_loss or price_change >= self.take_profit:
                    self.close_position(symbol, current_price, current_date)
                    
            except Exception as e:
                logging.error(f"Error updating position for {symbol}: {e}")
                continue

    def execute_trades(self, signals, current_date):
        """执行交易"""
        if not signals:
            return
            
        # 按信号强度排序
        sorted_signals = sorted(
            [(symbol, data) for symbol, data in signals.items()],
            key=lambda x: x[1]['total_score'],
            reverse=True
        )
        
        # 执行交易
        for symbol, signal in sorted_signals[:self.max_positions]:
            try:
                if symbol not in self.positions and signal['total_score'] > 7:
                    current_price = self.coin_data[symbol]['data'].loc[current_date, 'price']
                    available_capital = self.current_capital * self.max_position_size
                    quantity = available_capital / current_price
                    
                    if quantity * current_price >= self.min_trade_amount:
                        self.open_position(symbol, quantity, current_price, current_date)
                        
            except Exception as e:
                logging.error(f"Error executing trade for {symbol}: {e}")
                continue

    def open_position(self, symbol, quantity, price, date, signal_score=None):
        """开仓"""
        position_value = quantity * price
        if position_value > self.current_capital:
            return
            
        self.positions[symbol] = {
            'quantity': quantity,
            'entry_price': price,
            'entry_date': date,
            'current_price': price
        }
        
        self.current_capital -= position_value
        
        # 记录交易
        self.trades_history.append({
            'date': date,
            'symbol': symbol,
            'action': 'buy',
            'price': price,
            'quantity': quantity,
            'value': position_value
        })
        
        # 记录到日志
        self.log_trade(date, symbol, 'BUY', price, quantity, position_value, signal_score)
        
        logging.info(f"Opened position: {symbol} at {price:.2f}")

    def close_position(self, symbol, price, date):
        """平仓"""
        position = self.positions[symbol]
        position_value = position['quantity'] * price
        self.current_capital += position_value
        
        # 记录交易
        self.trades_history.append({
            'date': date,
            'symbol': symbol,
            'action': 'sell',
            'price': price,
            'quantity': position['quantity'],
            'value': position_value
        })
        
        # 记录到日志
        self.log_trade(date, symbol, 'SELL', price, position['quantity'], position_value)
        
        del self.positions[symbol]
        logging.info(f"Closed position: {symbol} at {price:.2f}")

    def update_portfolio_value(self, date):
        """更新投资组合价值"""
        total_value = self.current_capital
        
        for symbol, position in self.positions.items():
            try:
                current_price = self.coin_data[symbol]['data'].loc[date, 'price']
                position_value = position['quantity'] * current_price
                total_value += position_value
            except Exception as e:
                logging.warning(f"Error calculating position value for {symbol}: {e}")
                continue
                
        self.portfolio_history.append({
            'date': date,
            'value': total_value,
            'cash': self.current_capital,
            'positions': {s: p.copy() for s, p in self.positions.items()}
        })
        
        # 记录到日志
        self.log_portfolio(date, total_value)
        
        logging.info(f"Portfolio value at {date}: {total_value:.2f}")

    def plot_portfolio_performance(self):
        """绘制投资组合表现"""
        dates = [ph['date'] for ph in self.portfolio_history]
        values = [ph['value'] for ph in self.portfolio_history]
        
        plt.figure(figsize=(12, 6))
        plt.plot(dates, values, label='Portfolio Value')
        plt.axhline(y=self.initial_capital, color='r', linestyle='--', label='Initial Capital')
        
        plt.title('Portfolio Performance')
        plt.xlabel('Date')
        plt.ylabel('Value (USD)')
        plt.legend()
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig('portfolio_performance.png')
        plt.close()

    def calculate_performance_metrics(self):
        """计算回测性能指标"""
        # 准备数据
        trades = pd.DataFrame(self.trades_history)
        if len(trades) == 0:
            logging.warning("No trades to analyze")
            return
            
        # 计算每笔交易的收益
        trades_grouped = trades.groupby(['symbol']).agg({
            'date': list,
            'price': list,
            'value': list,
            'action': list
        })
        
        trade_results = []
        for _, group in trades_grouped.iterrows():
            buys = [(d, p, v) for d, p, v, a in zip(group['date'], group['price'], 
                    group['value'], group['action']) if a == 'buy']
            sells = [(d, p, v) for d, p, v, a in zip(group['date'], group['price'], 
                    group['value'], group['action']) if a == 'sell']
            
            for buy, sell in zip(buys, sells):
                if sell[1] > buy[1]:  # 盈利
                    profit = (sell[1] - buy[1]) / buy[1]
                    trade_results.append({
                        'result': 'win',
                        'profit': profit,
                        'buy_date': buy[0],
                        'sell_date': sell[0],
                        'holding_days': (pd.to_datetime(sell[0]) - pd.to_datetime(buy[0])).days
                    })
                else:  # 亏损
                    loss = (sell[1] - buy[1]) / buy[1]
                    trade_results.append({
                        'result': 'loss',
                        'profit': loss,
                        'buy_date': buy[0],
                        'sell_date': sell[0],
                        'holding_days': (pd.to_datetime(sell[0]) - pd.to_datetime(buy[0])).days
                    })
        
        # 转换为DataFrame
        results_df = pd.DataFrame(trade_results)
        
        # 计算关键指标
        total_trades = len(results_df)
        winning_trades = len(results_df[results_df['result'] == 'win'])
        losing_trades = len(results_df[results_df['result'] == 'loss'])
        
        # 计算收益指标
        portfolio_values = pd.DataFrame([{
            'date': ph['date'],
            'value': ph['value']
        } for ph in self.portfolio_history])
        portfolio_values['daily_return'] = portfolio_values['value'].pct_change()
        
        self.performance_metrics = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'average_win': results_df[results_df['profit'] > 0]['profit'].mean() if winning_trades > 0 else 0,
            'average_loss': results_df[results_df['profit'] < 0]['profit'].mean() if losing_trades > 0 else 0,
            'profit_factor': abs(results_df[results_df['profit'] > 0]['profit'].sum() / 
                               results_df[results_df['profit'] < 0]['profit'].sum()) if losing_trades > 0 else float('inf'),
            'average_holding_days': results_df['holding_days'].mean(),
            'max_drawdown': self.calculate_max_drawdown(),
            'sharpe_ratio': self.calculate_sharpe_ratio(portfolio_values['daily_return']),
            'total_return': (self.portfolio_history[-1]['value'] - self.initial_capital) / self.initial_capital
        }
        
        # 保存性能指标到CSV
        self.save_performance_metrics()
        
    def calculate_max_drawdown(self):
        """计算最大回撤"""
        values = [ph['value'] for ph in self.portfolio_history]
        peak = values[0]
        max_dd = 0
        
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
                
        return max_dd
        
    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.02):
        """计算夏普比率"""
        if len(returns) < 2:
            return 0
        excess_returns = returns - risk_free_rate/252  # 转换为日化无风险收益率
        return np.sqrt(252) * excess_returns.mean() / returns.std() if returns.std() != 0 else 0
        
    def save_performance_metrics(self):
        """保存性能指标到CSV"""
        metrics_file = f"performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            for metric, value in self.performance_metrics.items():
                writer.writerow([metric, f"{value:.4f}" if isinstance(value, float) else value])
                
        logging.info(f"Performance metrics saved to {metrics_file}")
        
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 加载数据
        data_loader = DataLoader()
        coin_data = data_loader.load_data()
        
        if not coin_data:
            raise ValueError("No data loaded")
            
        # 初始化回测器
        backtester = Backtester(
            coin_data=coin_data,
            initial_capital=10000,
            stop_loss=0.1,
            take_profit=0.2
        )
        
        # 运行回测
        backtester.run_backtest()
        
        # 输出结果
        final_value = backtester.portfolio_history[-1]['value']
        total_return = (final_value - backtester.initial_capital) / backtester.initial_capital * 100
        
        logging.info(f"""
        回测完成:
        初始资金: {backtester.initial_capital:,.2f}
        最终价值: {final_value:,.2f}
        总收益率: {total_return:.2f}%
        交易次数: {len(backtester.trades_history)}
        """)
        
        # 绘制结果
        backtester.plot_portfolio_performance()
        
    except Exception as e:
        logging.error(f"Error during backtest: {e}")
        raise

if __name__ == "__main__":
    main()