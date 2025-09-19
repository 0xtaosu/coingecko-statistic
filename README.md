# CoinGecko 统计与 Telegram Bot

本项目从 CoinGecko API 获取并分析顶级加密货币，为每个币种计算得分，并将结果保存到 CSV 文件中。此外，它还包含一个 Telegram Bot，每天自动发送前 50 个得分最低的币种信息，并提供一个简单的 HTTP 服务器来展示结果。

## 功能特点

- 从 CoinGecko API 获取顶级币种，支持自定义批次
- 将原始数据保存到 CSV 文件中
- 基于多个因素为每个币种计算得分
- 将分析结果保存到单独的 CSV 文件中
- 命令行界面，支持灵活的批次处理和独立的数据获取与分析操作
- Telegram Bot 自动每天发送前 50 个得分最高的币种信息
- 简单的 HTTP 服务器，用于展示分析结果


## 计算方法

币种得分基于以下七个因素，总分为这些因素的加权总和：

1. 横盘特征评分 (Consolidation Score) - 权重 1.5
   - 使用前90天数据评估横盘特征
   - 计算价格波动范围和稳定性
   - 得分 = max(0, min(10, 10 - consolidation_range * 100))
   - 横盘越稳定，得分越高

2. 成交量稳定性评分 (Volume Stability Score) - 权重 1.0
   - 评估横盘期间的成交量稳定性
   - 使用成交量标准差与均值的比率
   - 得分 = max(0, min(10, 10 - volume_stability * 10))
   - 成交量越稳定，得分越高

3. 突破评分 (Breakout Score) - 权重 1.5
   - 评估最近14天的价格突破情况
   - 对比横盘期间的平均价格
   - 得分 = max(0, min(10, int(breakout_price_change)))
   - 突破幅度越大，得分越高

4. 突破成交量评分 (Breakout Volume Score) - 权重 1.0
   - 评估突破期间的成交量放大情况
   - 对比横盘期间的平均成交量
   - 得分 = max(0, min(10, int(breakout_volume_change * 0.5)))
   - 成交量放大越明显，得分越高

5. RSI评分 (RSI Score) - 权重 1.0
   - 关注RSI从低位回升的趋势
   - 计算最近RSI低点到当前的变化
   - 得分 = max(0, min(10, int(rsi_trend * 0.5)))
   - RSI回升幅度越大，得分越高

6. 移动平均线评分 (MA Score) - 权重 1.0
   - 评估价格对MA20和MA60的突破情况
   - 同时考虑均线趋势
   - 得分 = max(0, min(10, int(5 + ma_trend))) 如果突破均线，否则为0
   - 突破均线且趋势向上时得分较高

7. 市值评分 (Market Cap Score) - 权重 1.0
   - 倾向于选择中小市值代币
   - 得分 = min(10, max(0, int(15 - log10(market_cap))))
   - 市值越小，得分越高（在合理范围内）

总分计算：
- 总分 = 各项得分 * 对应权重的总和
- 横盘和突破特征具有更高权重（1.5）
- 其他指标权重为1.0
- 所有指标都经过数据验证，确保在出现异常值时返回合理结果

筛选标准：
- 要求至少有30天的历史数据
- 优先选择：
  1. 有明显的横盘积累阶段
  2. 最近开始突破的币种
  3. 突破时成交量明显放大
  4. RSI从低位回升
  5. 突破主要均线
  6. 市值适中的代币

注意事项：
- 所有数据都会经过清理，去除无效值
- 如果数据量不足90天，会动态调整计算窗口
- 得分仅反映技术面表现，不应作为唯一的投资决策依据
- 建议结合基本面分析和其他因素进行综合判断

## 每日提醒与网页

项目现在保持简洁：
- 每天 9:30（北京时间）通过 Telegram 发送 Top 50 榜单（基于得分）。
- 本地 HTTP 网页展示榜单及评分细节。

## 系统要求

- Python 3.7+

## 安装

1. 克隆此仓库：
   ```
   git clone https://github.com/0xtaosu/coingecko-statistic.git
   cd coingecko-statistic
   ```
2. 创建和激活虚拟环境：

   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
3. 安装所需包：
   ```
   pip install -r requirements.txt
   ```

4. 配置环境变量：
   在项目根目录创建一个 `.env` 文件，并添加以下内容：
   ```
   COINGECKO_API_KEY=你的CoinGecko API密钥
   TELEGRAM_BOT_TOKEN=你的Telegram Bot Token
   TELEGRAM_CHAT_ID=你的Telegram聊天ID
   ```
   请确保将 `.env` 文件添加到 `.gitignore` 中，以避免将敏感信息提交到版本控制系统。

## 使用方法

### 运行整个系统

使用以下命令启动整个系统，包括数据处理、Telegram Bot 和 HTTP 服务器：
```
python main.py
```

这将启动以下组件：
- HTTP 服务器（在 http://localhost:8000 上运行）
- 每日数据处理任务（每天早上 9:00 运行）
- Telegram Bot（每天早上 9:30 发送更新）

### 单独运行数据处理

如果你想单独运行数据处理，可以使用以下命令：

```
python data_processor.py <批次1> <批次2> ... [--fetch] [--analyze]
```
每个批次应该采用 `起始-结束` 的格式。例如：

```
python data_processor.py 1-50 51-100 101-150 151-200 201-250 251-300 --fetch --analyze
```

这将处理排名 1-50、51-100、101-150、151-200、201-250、251-300 的币种，获取数据并进行分析。

选项说明：
- `--fetch`: 从 CoinGecko API 获取新数据并保存到 data.csv
- `--analyze`: 分析 data.csv 中的数据并生成 coin_scores.csv

### 单独运行 Telegram Bot

如果你只想运行 Telegram Bot，可以使用以下命令：

```
python tg_bot.py
```


## 代码结构

- `main.py`: 主脚本，启动HTTP和调度任务
- `data_processor.py`: 数据获取和分析
- `tg_bot.py`: Telegram Bot（每天9:30发送Top 50）
- `requirements.txt`: 项目依赖列表

## 生成文件说明
- `data.csv`: CoinGecko的180天的数据，价格，交易量和市值
- `coin_scores.csv`: 每个币种的得分

## 注意事项

- 确保您有稳定的互联网连接以从 CoinGecko API 获取数据。
- 处理大批量数据或频繁运行脚本时，请注意 API 速率限制。
- 得分计算使用最近 180 天的数据，这可能会影响新上市或数据不足的币种的得分。
- 得分仅反映特定的技术指标，不应作为唯一的投资决策依据。
- 运行 `main.py` 后，系统将持续运行直到手动停止（使用 Ctrl+C）。

## 贡献

欢迎贡献、提出问题和功能请求。如果您想贡献，请查看 [问题页面](https://github.com/你的用户名/coingecko-statistic/issues)。

## 许可证

[MIT](https://choosealicense.com/licenses/mit/)
