from NorenApi import NorenApi
import config
import time

api=NorenApi()
# Record the start time
start_time = time.time()

ret = api.login(config.username,config.pwd,config.factor2,config.vc,config.app_key,config.imei)

 