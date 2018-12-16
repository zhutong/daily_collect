import json
import logging

from config import *


def parse_port_channel():
    path = opj(PARSED_CLI_PATH, 'main')
    results = {}
    for fn in os.listdir(path):
        hostname = fn[:-5]
        with open(opj(path, fn)) as f:
            data = json.load(f)
        pc = data.get('show port-channel summary')
        if pc:
            results[hostname] = pc
        pc = data.get('show etherchannel summary')
        if pc:
            results[hostname] = pc
    return results


def main():
    logging.info('Analysis port channel')
    pc_data = parse_port_channel()
    with open('/tmp/port_channel.json', 'w') as f:
        json.dump(pc_data, f, indent=4)
