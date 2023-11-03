# from api_helper import ShoonyaApiPy
import time
from NorenApi import NorenApi

from datetime import datetime
import config
import csv
import threading
import queue
import redis
 
r = redis.Redis(host='localhost', port=6379, db=0)
api = NorenApi()

api.set_token()
 
feed_opened = False
feedJson = []   

last_received_time = time.time()  
subscription_list = []  

tick_queue = queue.Queue()

feedJson = []
previous_ltp_values = {}

def process_tick_data():
    global feedJson
    while True:
        try:
            tick_data = tick_queue.get()
            if 'lp' in tick_data and 'tk' in tick_data:
                tk = tick_data['tk']
                ltp = float(tick_data['lp'])
                timest = datetime.fromtimestamp(int(tick_data['ft'])).isoformat()
                name = tick_data.get('ts', 'N/A')  

                matching_ticks = [item for item in feedJson if item['token'] == tk]
                
                if matching_ticks:
                    matching_tick = matching_ticks[0]
                    matching_tick['ltp'] = ltp
                    matching_tick['name'] = name
                    matching_tick['tt'] = timest
                else:
                    new_tick = {'token': tk, 'ltp': ltp, 'name': name, 'tt': timest}
                    feedJson.append(new_tick)
                    previous_ltp_values[tk] = ltp  
                save_to_csv(tk, ltp, name, timest)
                 
        except queue.Empty:
            pass

def event_handler_feed_update(tick_data):
    global last_received_time   
    tick_queue.put(tick_data)

    last_received_time = time.time()  

def event_handler_order_update(tick_data):
    print(f"Order update {tick_data}")

def open_callback():
    global feed_opened
    feed_opened = True

     
    api.subscribe(subscription_list)

 
api.start_websocket(order_update_callback=event_handler_order_update,
                    subscribe_callback=event_handler_feed_update,
                    socket_open_callback=open_callback)

 
while not feed_opened:
    pass

wb=['39002', '39001', '50799', '50798', '39004', '39003', '50807', '50806', '39006', '39005', '50813', '50812', '39012', '39011', '50839', '50838', '39014', '39013', '50853', '50852', '39016', '39015', '50855', '50854', '39018', '39017', '50865', '50864', '39020', '39019', '50867', '50866', '39022', '39021', '50869', '50868', '39024', '39023', '50871', '50870', '39026', '39025', '50873', '50872', '39034', '39033', '50907', '50906', '39036', '39035', '50909', '50908', '39038', '39037', '50917', '50912', '39040', '39039', '50919', '50918', '39042', '39041', '50921', '50920', '39049', '39045', '50925', '50924', '39051', '39050', '50927', '50926', '39057', '39052', '50929', '50928', '39064', '39058', '50931', '50930']






 
for token in wb:
    subscription_list.append(f'NFO|{token}')
 
tick_thread = threading.Thread(target=process_tick_data)
tick_thread.start()

 
 

previous_ltp_values = {}   

def save_to_csv(tk, ltp, name, timest):
       with open('feed_data.csv', 'a', newline='') as csvfile:   
        fieldnames = ['Token', 'LTP', 'Name', 'Timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames) 
        if csvfile.tell() == 0:
            writer.writeheader() 
        writer.writerow({'Token': tk, 'LTP': ltp, 'Name': name, 'Timestamp': timest})

               
 
while True:
    if time.time() - last_received_time >= 5:
        print("No data received for 5 seconds. Resubscribing at:", time.strftime('%Y-%m-%d %H:%M:%S'))
        api.subscribe(subscription_list)  
        last_received_time = time.time()  

    time.sleep(2)  