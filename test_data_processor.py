import csv
import json
from datetime import datetime, time, timedelta
import pytz

def process_historical_data(historical_data):
    data = json.loads(historical_data)
    processed_data = {}
    
    # 获取当前日期
    now = datetime.now(pytz.UTC)
    
    # 计算30天前的日期
    thirty_days_ago = now - timedelta(days=30)
    
    for timestamp_ms, price in data['price'].items():
        # 将毫秒时间戳转换为datetime对象
        dt = datetime.fromtimestamp(int(timestamp_ms) // 1000, tz=pytz.UTC)
        
        # 只处理最近30天的数据
        if dt < thirty_days_ago:
            continue
        
        # 获取当天的日期
        date = dt.date()
        
        # 如果这个日期还没有数据，或者当前时间更接近9:00
        if date not in processed_data or abs(dt.time().hour - 9) < abs(processed_data[date][0].time().hour - 9):
            processed_data[date] = (dt, price)
    
    # 将处理后的数据转换为所需的格式
    formatted_data = {dt.strftime('%Y-%m-%d:%H-%M-%S'): price for dt, price in processed_data.values()}
    
    return json.dumps({'price': formatted_data})

def process_csv(input_file, output_file):
    with open(input_file, 'r') as infile, open(output_file, 'w', newline='') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in reader:
            row['historical_data'] = process_historical_data(row['historical_data'])
            writer.writerow(row)

def main():
    input_file = 'data.csv'
    output_file = 'processed_data.csv'
    process_csv(input_file, output_file)
    print(f"Processed data has been written to {output_file}")

if __name__ == "__main__":
    main()
