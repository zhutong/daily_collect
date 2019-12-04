import json
import logging

import requests

def main():

    url = 'http://76.7.3.54/apps/device_center/api/filter_device?query=vz-|pz-%20sw'
    devices = requests.get(url).json()['filtered']

    params = {
        "type": "model",
        "collect_devices": devices
    }
    url = 'http://84.7.34.27:8061/apps/data_model/api/v1/api_worker/R-S_state_interface?metrics=all&demand=lasted&times=1&limit=all'
    data = requests.post(url, json=params).json()

    URL = 'http://127.0.0.1:9116/apps/port_statistic/api/update_hw'
    logging.info(requests.post(URL, json=data))
