import json
import logging
import time

import requests
from tornado.log import enable_pretty_logging


def main():
    if not DEV:
        # url = 'http://76.7.3.54/apps/device_center/api/filter_device?query=vz-|pz-%20sw'
        # devices = requests.get(url).json()['filtered']

        # url = 'http://84.7.67.61/apps/data_model/api/v1/api_worker/R-S_state_interface?metrics=all&demand=lasted&times=1&limit=all'
        # param = {
        #     "type": "model",
        #     "collect_devices": devices,
        #     "tool": "day2"
        # }

        t = int(time.time()) - 8*3600
        url = 'http://84.7.67.61/apps/data_model/api/v1/api_worker/R-S_state_interface?metrics=all&demand=period&start_time=%d&limit=all' % t
        param = dict(type='model',
                     devices_regex='SW VZ|PZ',
                     tool='day2')

        res = requests.post(url, json=param)
        data = res.text

        with open('/tmp/hw_port.json', 'w') as f:
            f.write(data)

        URL = 'http://76.7.3.54/apps/port_statistic/api/update_hw'
    else:
        with open('/Users/zhutong/Desktop/hw_port.json') as f:
            data = f.read()

        URL = 'http://127.0.0.1:9116/apps/port_statistic/api/update_hw'
    logging.info(requests.post(URL, data=data))


DEV = False
enable_pretty_logging()
main()
