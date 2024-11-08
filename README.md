# CoinGecko 统计与 Telegram Bot

本项目从 CoinGecko API 获取并分析顶级加密货币，为每个币种计算得分，并将结果保存到 CSV 文件中。此外，它还包含一个 Telegram Bot，每天自动发送前 50 个得分最低的币种信息，并提供一个简单的 HTTP 服务器来展示结果。

## 功能特点

- 从 CoinGecko API 获取顶级币种，支持自定义批次
- 将原始数据保存到 CSV 文件中
- 基于多个因素为每个币种计算得分
- 将分析结果保存到单独的 CSV 文件中
- 命令行界面，支持灵活的批次处理和独立的数据获取与分析操作
- Telegram Bot 自动每天发送前 50 个得分最低的币种信息
- 简单的 HTTP 服务器，用于展示分析结果


## 得分计算

币种得分基于以下八个因素，每个因素的得分范围为 0-10 分，总分为这些因素的总和：

1. 波动率评分 (Volatility Score)
   - 使用 14 天滚动标准差计算
   - 得分 = max(0, min(10, 10 - volatility * 200))
   - 波动率越低，得分越高

2. RSI 评分 (Relative Strength Index)
   - 基于 14 天周期计算
   - 20-30 区间：每增加 1 点减 1 分
   - 70-80 区间：每增加 1 点减 1 分
   - 30-70 区间：越接近 50 分数越高
   - 得分范围：0-10 分

3. 移动平均线评分 (Moving Average)
   - 比较 7 天和 30 天移动平均线
   - 得分 = min(10, MA差值百分比 * 200)
   - 短期均线高于长期均线时得分较高

4. 成交量变化评分 (Volume Change)
   - 基于最近两个时间点的成交量变化
   - 得分 = max(0, min(10, 5 + 变化率 * 10))
   - 变化率在 -0.5 到 1.5 之间线性插值

5. K线影线评分 (Shadow Ratio)
   - 计算最新 K 线的上下影线与实体的比例
   - 得分 = min(10, 影线比例 * 20)
   - 反映价格波动的剧烈程度

6. 市值评分 (Market Cap)
   - 使用对数刻度评分
   - 得分 = min(10, max(0, log10(市值) - 5))
   - 适用于 1e6 到 1e16 之间的市值

7. 价格趋势评分 (Price Trend)
   - 基于 7 天价格变化百分比
   - 得分 = max(0, min(10, 5 + 价格变化百分比))
   - 变化范围在 -5% 到 5% 之间线性插值

8. 成交量趋势评分 (Volume Trend)
   - 基于 7 天成交量变化百分比
   - 得分 = max(0, min(10, 5 + 变化率 / 2))
   - 变化范围在 -10% 到 10% 之间线性插值

总分计算：
- 总分 = 以上八个因素的得分之和
- 得分范围：0-80 分
- 所有指标都经过 safe_score 函数处理，确保在出现 NaN 或 Inf 值时返回 0 分

注意事项：
- 所有数据都会经过清理，去除无效值（如 NaN 和 Inf）
- 如果数据点不足以计算某个指标（如少于 14 天的数据），该币种将被跳过
- 得分仅反映技术面表现，不应作为唯一的投资决策依据

## 系统要求

- Python 3.7+

## 安装

1. 克隆此仓库：
   ```
   git clone https://github.com/0xtaosu/coingecko-statistic.git
   cd coingecko-statistic
   ```

2. 安装所需包：
   ```
   pip install -r requirements.txt
   ```

3. 配置环境变量：
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
python data_processor.py 1-50 51-100 101-150 --fetch --analyze
```

这将处理排名 1-50、51-100、101-150 的币种，获取数据并进行分析。

选项说明：
- `--fetch`: 从 CoinGecko API 获取新数据并保存到 data.csv
- `--analyze`: 分析 data.csv 中的数据并生成 coin_scores.csv

### 单独运行 Telegram Bot

如果你只想运行 Telegram Bot，可以使用以下命令：

```
python tg_bot.py
```


## 代码结构

- `main.py`: 主脚本，用于启动整个系统
- `data_processor.py`: 数据获取和分析的脚本
- `tg_bot.py`: Telegram Bot 脚本
- `requirements.txt`: 项目依赖列表

## 得分计算

币种得分基于以下因素：
1. 波动性（Volatility）
2. 相对强弱指标（RSI）
3. 移动平均线
4. 交易量变化

每个因素贡献 1 分，最高得分为 4 分。

## 注意事项

- 确保您有稳定的互联网连接以从 CoinGecko API 获取数据。
- 处理大批量数据或频繁运行脚本时，请注意 API 速率限制。
- 得分计算使用最近 30 天的数据，这可能会影响新上市或数据不足的币种的得分。
- 得分仅反映特定的技术指标，不应作为唯一的投资决策依据。
- 运行 `main.py` 后，系统将持续运行直到手动停止（使用 Ctrl+C）。

## 贡献

欢迎贡献、提出问题和功能请求。如果您想贡献，请查看 [问题页面](https://github.com/你的用户名/coingecko-statistic/issues)。

## 许可证

[MIT](https://choosealicense.com/licenses/mit/)
