import json
import logging

import requests

from config import *

DEVICE_CENTER_URL = APP_URL + 'device_center/api/update_failed_cli'


def main():
    failed = []
    for fn in os.listdir(ANALIZED_DATA_PATH):
        if fn.startswith('login'):
            failed.append(fn.split('__')[1][:-5])
    data = dict(failed=failed)
    res = requests.post(DEVICE_CENTER_URL, data=json.dumps(data))
    if res.status_code != 200:
        logging.error('DeviceCenter CLI state update failed: %s', res.text)
    else:
        logging.info('DeviceCenter CLI state updated successfully')
