from flask import Flask, jsonify, make_response
import csv
import pandas as pd
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
value = '60458'



CSV_FILE_PATH = 'feed_data.csv'
def find_last_minute_data(value):
    with open(CSV_FILE_PATH, 'r') as file:
        lines = file.readlines()
        
    last_minute_data = None
    current_minute = None

    for line in reversed(lines):
        columns = line.strip().split(',')
        if columns[0] == value:
            timestamp = pd.to_datetime(columns[3])  
            minute = timestamp.strftime('%Y-%m-%d %H:%M')
            if current_minute is None:
                current_minute = minute
                last_minute_data = {
                    'time': timestamp.timestamp() * 1000,  
                    'open': float(columns[1]),
                    'high': float(columns[1]), 
                    'low': float(columns[1]),  
                    'close': float(columns[1]) 
                }
            elif current_minute != minute:
                break  
            else:
                last_minute_data['high'] = max(last_minute_data['high'], float(columns[1]))
                last_minute_data['low'] = min(last_minute_data['low'], float(columns[1]))
                last_minute_data['close'] = float(columns[1])
    
    return last_minute_data


@app.route('/get_ltp')
def get_last_80_lines_route():
    last_minute_data = find_last_minute_data(value)

    if last_minute_data:
        response_data = {
            'time': last_minute_data['time'],  
            'open': last_minute_data['close'],
            'high': last_minute_data['high'],
            'low': last_minute_data['low'],
            'close': last_minute_data['open']
        }
        response = make_response(jsonify(response_data))
    else:
        response_data = {
            'error': 'No data found for the current minute'
        }
        response = make_response(jsonify(response_data), 404)  

    response.headers['Cache-Control'] = 'no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def preprocess_data():
    data = []

    with open(CSV_FILE_PATH, 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            data.append(row)

    df = pd.DataFrame(data)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.set_index('Timestamp', inplace=True)
    return df

@app.route('/get_ohlc')
def get_ohlc():
    df = preprocess_data()
    token_data = df[df['Token'] == value]
    token_data = token_data.copy()
    token_data[token_data.columns[1]] = pd.to_numeric(token_data['LTP'], errors='coerce')
    ohlc_data = token_data['LTP'].resample('1Min').ohlc()
    ohlc_list = []

    for index, row in ohlc_data.iterrows():
        ohlc_dict = {
            'time': int(index.timestamp()) ,  
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close']
        }
        ohlc_list.append(ohlc_dict)

    return jsonify(ohlc_list)


if __name__ == '__main__':
    app.run(debug=True)
