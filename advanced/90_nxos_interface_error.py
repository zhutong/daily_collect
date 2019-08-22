# -*- coding:utf-8 -*-

import json
import logging
import re
import os
import sys
import time
from collections import defaultdict

from pprint import pprint as pp

import requests
from config import *


PATH = '/data/'
LAST_ERROR_FN = os.path.join(PATH, 'last_counters.json')


table_header = u'''
    <style>
        h4 {
            margin: 15px 0 0 0;
        }
        table {
            width: 100%;
            max-width: 100%;
            border: 1px solid #aaaaaa;
            border-spacing: 0;
            border-collapse: collapse;
            margin: 3px 0;
        }
        th {
            color: white;
            background-color: #337ab7;
        }
        th,
        td {
            text-align: center;
            line-height: 1.5;
            border: 1px solid #aaaaaa;
        }
        .alarm {
            background: orange;
            color: white;
        }
    </style>
    <h3>N7K & N5K Port Error count</h3>
    <table>
        <thead>
            <th>Hostname</th>
            <th>Port</th>
            <th>Align</th>
            <th>FCS</th>
            <th>TX</th>
            <th>RX</th>
            <th>UnderSize</th>
            <th>OutDrop</th>
        </thead>
        <tbody>
'''


def send_mail(body):
    # print(body)
    # return
    receivers = requests.get(GET_MAIL_LIST_URL).json()['mail_list']
    receivers.append('icbc_mds@cisco.com')
    data = {
        "subject": "Day2: 接口错包",
        'body_html': body,
        "receivers": receivers,
    }
    res = requests.post(SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


def analysis():
    logging.info('Analysis port error counters')
    devices = defaultdict(dict)
    for_report = defaultdict(list)

    try:
        with open(LAST_ERROR_FN) as f:
            last_devices = json.load(f)
    except:
        last_devices = {}

    path = opj(PARSED_CLI_PATH, 'main')
    for fn in os.listdir(path):
        hostname = fn[:-5]
        with open(opj(path, fn)) as f:
            data = json.load(f)
        rows = data.get('show interface counters errors', [])
        for row in rows:
            if_name = row['Interface']
            devices[hostname][if_name] = row
            if hostname in last_devices and if_name in last_devices[hostname]:
                for_report[hostname].append(row)

    with open(LAST_ERROR_FN, 'w') as f:
        json.dump(devices, f, indent=4)

    return for_report


def report(data):
    t = '<tr><td>{hostname}</td><td>{Interface}</td><td>{Align}</td><td>{FCS}</td><td>{TX}</td><td>{RX}</td><td>{UnderSize}</td><td>{OutDrop}</td></tr>'
    lines = []
    for hostname, rows in data.items():
        for r in rows:
            lines.append(t.format(hostname=hostname, **r))
    return table_header + '\n'.join(lines) + '</tbody></table>'


def main():
    send_mail(report(analysis()))