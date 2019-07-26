import json
import logging
from collections import defaultdict

import requests

import config as c


reset_script_file = '/tmp/reset_mts_buffer.txt'
table_file = '/tmp/mts_buffer_table.html'

t0 = '// {h} ({i})\r\n{m} {i}\r\n//{h}//'
t1 = 'debug mts drop node {node} sap {sap} from recv opcode {opc} age 10'
t2 = '<tr><td>{h}</td><td>{slot}</td><td>{node}</td><td>{sap}</td><td>{opc}</td><td>{count}</td></tr>'

body_part = u'''
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
        </style>
        <h4>System Internal MTS Buffers</h4>
        <table>
            <thead>
                <th>Hostname</th>
                <th>Slot</th>
                <th>Node</th>
                <th>SAP</th>
                <th>OP Code</th>
                <th>Count</th>
            </thead>
            <tbody>'''


def __get_device_info():
    rows = requests.get(c.DEVICE_INFO_URL).json()
    devices = {}
    for r in rows['data']:
        devices[r['hostname']] = r
    return devices


def create_report(mts_info):
    device_dict = __get_device_info()
    report_lines = []
    script_lines = []
    for hostname, slot_dict in mts_info.items():
        try:
            ip = device_dict[hostname]['ip']
            method = device_dict[hostname]['method'] or 'ssh'
        except:
            ip = 'unknown'
            method = 'ssh'
        script_lines.append(t0.format(h=hostname, i=ip, m=method))

        for slot, mts_list in slot_dict.items():
            if slot != '0':
                script_lines.append('attach %s' % slot)
            for mts in mts_list:
                script_lines.append(t1.format(h=hostname, **mts))
                report_lines.append(t2.format(h=hostname, slot=slot, **mts))
            if slot != '0':
                script_lines.append('exit\r\n')

    with open(reset_script_file, 'w') as f:
        f.write('\r\n'.join(script_lines))

    table = body_part + '\r\n'.join(report_lines) + '</tbody></table>'
    with open(table_file, 'w') as f:
        f.write(table)

    return table


def send_mail(mail_body):
    receivers = requests.get(c.GET_MAIL_LIST_URL).json()['mail_list']
    receivers.append('icbc_mds@cisco.com')
    data = {
        "subject": "Day2: N7K MTS buffer泄漏",
        'body_html': mail_body,
        "attach": [reset_script_file],
        "receivers": receivers,
    }
    res = requests.post(c.SEND_MAIL_URL, data=json.dumps(data))
    logging.info(res.text)


def main():
    logging.info('Create MTS report')
    mts_info = defaultdict(dict)
    path = c.opj(c.PARSED_CLI_PATH, 'main')
    for fn in c.os.listdir(path):
        hostname = fn[:-5]
        with open(c.opj(path, fn)) as f:
            data = json.load(f)
        for cmd in data:
            if 'mts buffer' in cmd:
                if 'slot' in cmd:
                    slot = cmd.split()[1]
                else:
                    slot = '0'
                mts_info[hostname][slot]=data[cmd]
    send_mail(create_report(mts_info))
