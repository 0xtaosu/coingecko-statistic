# CoinGecko 统计

本项目从 CoinGecko API 获取并分析顶级加密货币，为每个币种计算得分，并将结果保存到 CSV 文件中。

## 功能特点

- 从 CoinGecko API 获取顶级币种，支持自定义批次
- 将原始数据保存到 CSV 文件中
- 基于多个因素为每个币种计算得分
- 将分析结果保存到单独的 CSV 文件中
- 命令行界面，支持灵活的批次处理和独立的数据获取与分析操作

## 系统要求

- Python 3.6+

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

3. 配置 API 密钥：
   在项目根目录创建一个 `.env` 文件，并添加以下内容：
   ```
   COINGECKO_API_KEY=你的API密钥
   ```
   请确保将 `.env` 文件添加到 `.gitignore` 中，以避免将敏感信息提交到版本控制系统。

## 使用方法

从命令行运行脚本，指定要处理的批次和操作：

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

## 代码结构

- `data_processor.py`：包含所有逻辑的主脚本。
- `get_coin_history(coin_id)`：获取指定币种的历史价格数据。
- `process_data(data)`：处理原始数据，选择每天最接近9:00的数据点。
- `analyze_coin(coin_id)`：分析单个币种并计算得分。
- `calculate_rsi(df)`：计算给定币种的 RSI。
- `fetch_and_save_data(batches)`：获取数据并保存到 data.csv。
- `analyze_data()`：分析 data.csv 中的数据并生成 coin_scores.csv。

## 得分计算

本项目使用多个因素来计算币种的得分，每个因素贡献1分，最高得分为4分。计算因素如下：

1. 波动性（Volatility）：如果波动性低于0.05，得1分。
2. 相对强弱指标（RSI）：如果RSI在30到70之间，得1分。
3. 移动平均线：如果7天移动平均线高于30天移动平均线，得1分。
4. 交易量变化：如果交易量变化为正，得1分。

RSI的计算过程如下：
1. 获取币种最近30天的历史价格数据，每天选取最接近9:00的数据点。
2. 计算每日价格变化。
3. 分别计算上涨和下跌的平均值。
4. 计算相对强度（RS）= 平均上涨 / 平均下跌。
5. 计算 RSI = 100 - (100 / (1 + RS))。

## 工作流程

1. 脚本解析命令行参数以确定要处理的批次和操作。
2. 如果指定了 `--fetch`：
   a. 对于每个批次，从 CoinGecko API 获取币种数据。
   b. 获取每个币种最近30天的历史价格数据。
   c. 将原始数据保存到 data.csv 文件。
3. 如果指定了 `--analyze`：
   a. 从 data.csv 读取币种数据。
   b. 对每个币种进行分析：
      - 处理数据，选择每天最接近9:00的数据点。
      - 计算波动性、RSI、移动平均线和交易量变化。
      - 根据这些因素计算得分。
   c. 将分析结果保存到 coin_scores.csv 文件。

## 输出

脚本生成两个 CSV 文件：

1. `data.csv`：包含从 CoinGecko API 获取的原始数据。
2. `coin_scores.csv`：包含分析结果，具有以下列：
   - id：币种的唯一标识符
   - symbol：币种的符号
   - name：币种的名称
   - score：币种的综合得分

## 注意事项

- 确保您有稳定的互联网连接以从 CoinGecko API 获取数据。
- 处理大批量数据或频繁运行脚本时，请注意 API 速率限制。
- 得分计算使用最近30天的数据，这可能会影响新上市或数据不足的币种的得分。
- 得分仅反映特定的技术指标，不应作为唯一的投资决策依据。

## 贡献

欢迎贡献、提出问题和功能请求。如果您想贡献，请查看 [问题页面](https://github.com/你的用户名/coingecko-statistic/issues)。

## 许可证

[MIT](https://choosealicense.com/licenses/mit/)

